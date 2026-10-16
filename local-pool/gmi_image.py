"""Fengye image adapter for the GMI accounts hosted on port 8791.

Install alongside server/gmi.py; API keys stay encrypted on the local server.
"""
import asyncio
import base64
import secrets
import time
import re

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse
from . import config, gmi, gmi_http

router = APIRouter()
MODEL = 'gemini-nano-banana-2.1'
_workers = set()
_selection_lock = asyncio.Lock()


def guard(request):
    # The public website needs CORS access; require the panel token even on localhost.
    supplied = request.headers.get('x-pool-token', '')
    if not config.PANEL_TOKEN or not secrets.compare_digest(supplied, config.PANEL_TOKEN):
        raise HTTPException(401, 'GMI号池连接码不正确')


def task_table(c):
    c.execute('CREATE TABLE IF NOT EXISTS gmi_image_tasks '
              '(id TEXT PRIMARY KEY, payload BLOB NOT NULL, updated REAL NOT NULL)')


def save_task(task):
    with gmi.connect() as c:
        task_table(c)
        c.execute('INSERT INTO gmi_image_tasks VALUES(?,?,?) ON CONFLICT(id) '
                  'DO UPDATE SET payload=excluded.payload,updated=excluded.updated',
                  (task['id'], gmi.seal(task), time.time()))


def load_task(task_id):
    with gmi.connect() as c:
        task_table(c)
        row = c.execute('SELECT payload FROM gmi_image_tasks WHERE id=?', (task_id,)).fetchone()
    if not row:
        raise HTTPException(404, '图片任务不存在')
    return gmi.unseal(row[0])


def public_task(task, base=''):
    return {'task_id': task['id'], 'status': task['status'], 'model': MODEL,
            'data': [{'url': base.rstrip('/') + u if u.startswith('/') else u}
                     for u in task.get('urls', [])],
            'error': task.get('error', '')}


def image_urls(raw):
    urls = []
    def walk(value):
        if isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            inline = value.get('inlineData') or value.get('inline_data')
            if isinstance(inline, dict) and inline.get('data'):
                mime = inline.get('mimeType') or inline.get('mime_type') or 'image/png'
                if mime.startswith('image/'):
                    urls.append('data:' + mime + ';base64,' + inline['data'])
            if value.get('b64_json'):
                urls.append('data:image/png;base64,' + value['b64_json'])
            for key, item in value.items():
                if key in ('url', 'image_url', 'media_url') and isinstance(item, str):
                    if item.startswith(('https://', 'data:image/')):
                        urls.append(item)
                elif key not in ('inlineData', 'inline_data', 'b64_json'):
                    walk(item)
    # Never inspect echoed input payloads: reference images are not generated output.
    for key in ('outcome', 'output', 'data', 'candidates'):
        if raw.get(key) is not None:
            walk(raw[key])
    return list(dict.fromkeys(urls))


async def run_task(task, payload=None):
    try:
        if payload is not None:
            task['status'] = 'submitting'
            save_task(task)
            raw = await gmi_http.request('POST', '/ie/requestqueue/apikey/requests',
                                         token=task['key'], body={'model': MODEL, 'payload': payload}, timeout=180)
            task['upstream_id'] = raw.get('request_id') or raw.get('id')
            save_task(task)
        else:
            raw = {}
        for attempt in range(600):
            urls = image_urls(raw)
            status = str(raw.get('status', '')).lower()
            if urls:
                # One request produces one image; prefer inline output over remote copies.
                url = next((u for u in urls if u.startswith('data:image/')), urls[0])
                if url.startswith('data:image/'):
                    header, encoded = url.split(',', 1)
                    ext = '.jpg' if 'jpeg' in header else ('.webp' if 'webp' in header else '.png')
                    folder = config.DATA_DIR / 'gmi-image-media'
                    folder.mkdir(exist_ok=True)
                    filename = task['id'] + ext
                    (folder / filename).write_bytes(base64.b64decode(encoded, validate=True))
                    url = '/media/gmi-images/' + filename
                task.update(status='completed', urls=[url])
                break
            if status in ('failed', 'error', 'cancelled', 'canceled'):
                raise gmi_http.ApiError(502, 'GMI生图失败：' + str(raw.get('error') or raw.get('message') or status)[:200])
            if status in ('success', 'succeeded', 'completed'):
                raise gmi_http.ApiError(502, 'GMI任务已结束但未返回图片，请调整绘图提示词')
            if not task.get('upstream_id'):
                raise gmi_http.ApiError(502, 'GMI未返回任务编号，请核对上游记录，勿重复提交')
            task['status'] = 'running'
            save_task(task)
            await asyncio.sleep(2)
            try:
                raw = await gmi_http.request('GET', '/ie/requestqueue/apikey/requests/' + task['upstream_id'], token=task['key'], timeout=60)
            except gmi_http.ApiError as error:
                if error.status in (429, 502, 503, 504) and attempt < 599:
                    await asyncio.sleep(3)
                    continue
                raise
        else:
            raise gmi_http.ApiError(504, '等待图片超时，请保留任务编号核对上游记录')
    except Exception as error:
        task.update(status='failed', error=str(error) if isinstance(error, gmi_http.ApiError)
                    else 'GMI连接异常，请保留任务编号核对上游记录，勿重复提交')
    finally:
        save_task(task)


def spawn(coro):
    worker = asyncio.create_task(coro)
    _workers.add(worker)
    worker.add_done_callback(_workers.discard)


async def recover_tasks():
    with gmi.connect() as c:
        task_table(c)
        tasks = [gmi.unseal(row[0]) for row in c.execute('SELECT payload FROM gmi_image_tasks')]
    for task in tasks:
        if task['status'] in ('queued', 'submitting', 'running'):
            if task.get('upstream_id'):
                spawn(run_task(task))
            else:
                task.update(status='failed', error='服务重启时提交中断，请核对上游记录，未自动重复提交')
                save_task(task)


@router.get('/api/gmi-image-connection')
async def connection(request: Request):
    guard(request)
    rows = [r for r in gmi.records() if r.get('api_key') and r['state'] == 'ready']
    return {'ok': True, 'accounts': len(rows), 'model': MODEL, 'service': 'gmi-8791'}


@router.post('/api/gmi-image')
async def generate(request: Request):
    guard(request)
    if request.headers.get('content-type', '').startswith('multipart/form-data'):
        form = await request.form()
        data = dict(form)
        parts = [{'text': str(form.get('prompt') or '请根据参考图生成图片')}]
        for upload in form.getlist('image'):
            if not hasattr(upload, 'read') or not str(upload.content_type).startswith('image/'):
                raise HTTPException(400, '参考图必须是图片文件')
            content = await upload.read(20_000_001)
            if len(content) > 20_000_000:
                raise HTTPException(413, '单张参考图不能超过20MB')
            parts.append({'inline_data': {'mime_type': upload.content_type,
                                         'data': base64.b64encode(content).decode()}})
        if len(parts) > 17:
            raise HTTPException(400, '最多支持16张参考图')
    else:
        data = await request.json()
        parts = None
    if data.get('model') not in ('nano-banana-2.1', MODEL):
        raise HTTPException(400, '8791生图接口仅支持Nano Banana 2.1，请选择对应模型')
    try:
        count = int(data.get('n', 1))
    except (ValueError, TypeError):
        raise HTTPException(400, 'n必须为1')
    if count != 1:
        raise HTTPException(400, '每个任务生成1张图片，请由网站拆分多张任务')
    prompt = str(data.get('prompt') or '').strip()
    if not prompt and not parts:
        raise HTTPException(400, '请填写绘图提示词')
    tier = data.get('image_size', '2K')
    ratio = data.get('aspect_ratio', '1:1')
    if tier not in ('1K', '2K', '4K') or ratio not in ('1:1','4:5','5:4','3:4','4:3','9:16','16:9','21:9'):
        raise HTTPException(400, '不支持的图片分辨率或比例')
    payload = {'prompt': prompt, 'image_size': tier, 'aspect_ratio': ratio}
    if parts:
        payload['contents'] = [{'role': 'user', 'parts': parts}]
    async with _selection_lock:
        with gmi.connect() as c:
            task_table(c)
            active = [gmi.unseal(r[0]) for r in c.execute('SELECT payload FROM gmi_image_tasks')]
        busy = {t['email'] for t in active if t['status'] in ('queued', 'submitting', 'running')}
        rows = [r for r in gmi.records() if r.get('api_key') and r['state'] == 'ready'
                and r['email'] not in busy
                and (not r.get('balance') or float(r['balance'].get('total_usd', 0)) > 0)]
        if not rows:
            raise HTTPException(503, 'GMI号池暂无空闲且有余额的账号，请稍后重试或检查余额')
        rows.sort(key=lambda r: float((r.get('balance') or {}).get('total_usd', 0)), reverse=True)
        row = rows[0]
        task = {'id': 'gmi8791_' + secrets.token_hex(12), 'email': row['email'],
                'key': row['api_key'], 'status': 'queued', 'created': time.time()}
        save_task(task)
    spawn(run_task(task, payload))
    return public_task(task, str(request.base_url))


@router.get('/api/gmi-image')
async def query(request: Request, task_id: str):
    guard(request)
    return public_task(load_task(task_id), str(request.base_url))


@router.get('/media/gmi-images/{filename}')
async def media(filename: str):
    # Unguessable task IDs allow <img> and downloads without exposing pool credentials.
    if not re.fullmatch(r'gmi8791_[0-9a-f]{24}\.(png|jpg|webp)', filename):
        raise HTTPException(404, '图片不存在')
    path = config.DATA_DIR / 'gmi-image-media' / filename
    if not path.is_file():
        raise HTTPException(404, '图片不存在')
    return FileResponse(str(path))
