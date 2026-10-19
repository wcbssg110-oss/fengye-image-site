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
_generation_slots = asyncio.Semaphore(100)


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
            'error': task.get('error', ''), 'failed_phase': task.get('failed_phase', '')}


def image_urls(raw):
    urls = []
    def walk(value):
        if isinstance(value, list):
            for item in value:
                walk(item)
        elif isinstance(value, dict):
            if value.get('role') == 'user':
                return
            inline = value.get('inlineData') or value.get('inline_data')
            if isinstance(inline, dict) and inline.get('data'):
                mime = inline.get('mimeType') or inline.get('mime_type') or 'image/png'
                if mime.startswith('image/'):
                    urls.append('data:' + mime + ';base64,' + inline['data'])
            file = value.get('fileData') or value.get('file_data')
            if isinstance(file, dict):
                uri = file.get('fileUri') or file.get('file_uri') or ''
                if uri.startswith('https://'):
                    urls.append(uri)
            if value.get('b64_json'):
                urls.append('data:image/png;base64,' + value['b64_json'])
            for key, item in value.items():
                if key in ('url', 'image_url', 'media_url') and isinstance(item, str):
                    if item.startswith(('https://', 'data:image/')):
                        urls.append(item)
                elif key not in ('inlineData', 'inline_data', 'b64_json', 'fileData', 'file_data',
                                  'payload', 'input', 'contents', 'next_turn_contents'):
                    walk(item)
    outcome = raw.get('outcome') or {}
    if isinstance(outcome, dict):
        # GMI echoes the original reference image in user turns. Only model turns are output.
        for turn in outcome.get('next_turn_contents') or []:
            if isinstance(turn, dict) and turn.get('role') == 'model':
                walk(turn)
    if not urls:
        for key in ('outcome', 'output', 'data', 'candidates'):
            if raw.get(key) is not None:
                walk(raw[key])
    return list(dict.fromkeys(urls))


async def cache_image(task_id, url):
    folder = config.DATA_DIR / 'gmi-image-media'
    folder.mkdir(exist_ok=True)
    if url.startswith('data:image/'):
        header, encoded = url.split(',', 1)
        content = base64.b64decode(encoded, validate=True)
    else:
        from urllib.parse import urlparse
        import httpx
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname != 'storage.googleapis.com':
            return url
        async with httpx.AsyncClient(timeout=120, trust_env=config.TRUST_ENV) as client:
            response = await client.get(url)
            response.raise_for_status()
            content = response.content
    if content.startswith(b'\x89PNG\r\n\x1a\n'):
        ext = '.png'
    elif content.startswith(b'\xff\xd8\xff'):
        ext = '.jpg'
    elif content.startswith(b'RIFF') and content[8:12] == b'WEBP':
        ext = '.webp'
    else:
        raise gmi_http.ApiError(502, 'GMI返回内容不是有效图片，未覆盖已有成品')
    filename = task_id + ext
    (folder / filename).write_bytes(content)
    return '/media/gmi-images/' + filename


def preserve_view_prompt(prompt):
    return (
        '执行局部换鞋编辑，禁止重绘整张照片。输入图像有严格顺序：'
        '图一是唯一的底图，定义画面构图、相机视角、脚部姿势和透视；'
        '图二只提供鞋款的材质、颜色、结构，不提供穿着姿势或拍摄角度。'
        '将图二鞋款按图一原鞋的方向和透视适配到图一。'
        '保留图一脚踝位置、脚尖朝向、双脚间距、脚跟位置、鞋底接地线，'
        '不要旋转脚，不要把侧面鞋改为正面，不要移动、缩放或裁切人物。'
        '袜子、腿、手、衣服、背景、地面、光照和相机位置保持图一不变；'
        '只修改原鞋覆盖区域。鞋款自然适配原脚，不能为了展示鞋款改变姿势。'
        '仅输出一张编辑后的图一照片，不要拼图、对比图、产品陈列或新增人物。'
        '\n用户要求：' + (prompt or '将图二鞋款替换到图一中。')
    )


async def upload_reference(key, inline):
    import httpx
    from urllib.parse import urlparse
    content = base64.b64decode(inline['data'], validate=True)
    if content.startswith(b'\x89PNG\r\n\x1a\n'):
        ext, mime = 'png', 'image/png'
    elif content.startswith(b'\xff\xd8\xff'):
        ext, mime = 'jpeg', 'image/jpeg'
    elif content.startswith(b'RIFF') and content[8:12] == b'WEBP':
        ext, mime = 'webp', 'image/webp'
    else:
        raise gmi_http.ApiError(400, '参考图文件不是有效的PNG、JPEG或WebP图片')
    # Signing allocates an upload object, not a billable generation; safe to retry.
    for attempt in range(3):
        try:
            signed = await gmi_http.request('POST', '/ie/requestqueue/apikey/upload-url',
                                            token=key, body={'file_type': ext}, timeout=60)
            break
        except gmi_http.ApiError as error:
            if error.status not in (429, 502, 503, 504) or attempt == 2:
                raise
            await asyncio.sleep(1 + attempt)
    upload_url = signed.get('upload_url', '')
    public_url = signed.get('public_url', '')
    for url in (upload_url, public_url):
        parsed = urlparse(url)
        if parsed.scheme != 'https' or parsed.hostname != 'storage.googleapis.com':
            raise gmi_http.ApiError(502, 'GMI返回了无法验证的素材存储地址，已停止上传')
    for attempt in range(3):
        try:
            async with httpx.AsyncClient(timeout=180, trust_env=config.TRUST_ENV) as client:
                response = await client.put(upload_url, content=content, headers={'Content-Type': mime})
                response.raise_for_status()
            return public_url
        except httpx.HTTPStatusError as error:
            status = error.response.status_code
            if status not in (408, 429, 500, 502, 503, 504) or attempt == 2:
                raise gmi_http.ApiError(502, '参考图上传失败（HTTP ' + str(status) + '），尚未提交生图请求') from None
        except httpx.TransportError as error:
            if attempt == 2:
                raise gmi_http.ApiError(502, '参考图上传连接失败（' + type(error).__name__ + '），尚未提交生图请求') from None
        # PUT to the same signed object is idempotent; never retry generation POST here.
        await asyncio.sleep(1 + attempt)



def record_credit_rejection(email):
    row = gmi_http.stored(email)
    if not row:
        return
    # Only native-route credit rejection triggers a temporary generation cooldown.
    # Never infer or overwrite an account balance from generation errors.
    gmi_http.metadata(email, {'last_generation_rejection': {
        'http': 402, 'transport': 'gemini_native', 'checked_at': time.time(),
        'reason': '本次生成请求额度校验未通过，暂停生成调度30分钟；未据此修改余额'}})


def pick_available(excluded=(), task_id=None):
    with gmi.connect() as c:
        task_table(c)
        active = [gmi.unseal(r[0]) for r in c.execute('SELECT payload FROM gmi_image_tasks')]
    busy = {t['email'] for t in active if t.get('id') != task_id
            and t['status'] in ('queued','uploading','submitting','running')}
    rows = [r for r in gmi.records() if r.get('api_key') and r['state'] == 'ready'
            and r['email'] not in busy and r['email'] not in excluded
            and not r.get('scheduler_disabled')
            and ((r.get('last_generation_rejection') or {}).get('transport') != 'gemini_native'
                 or time.time() - float((r.get('last_generation_rejection') or {}).get('checked_at', 0)) >= 1800)
            and all(float((r.get('balance') or {}).get(field) or 0)>=0 for field in ('cash_usd','credit_usd','total_usd'))
            and (not r.get('balance') or float(r['balance'].get('total_usd',0)) > 0)]
    rows.sort(key=lambda r: float((r.get('balance') or {}).get('total_usd',0)),reverse=True)
    return rows[0] if rows else None


async def run_task(task, payload=None):
    if payload is not None:
        task['pending_payload'] = payload
        task['status'] = 'queued'
        save_task(task)
    async with _generation_slots:
        await _run_task(task, payload)


async def _run_task(task, payload=None):
    try:
        if payload is not None:
            original_payload = dict(payload)
            excluded = set()
            while True:
                task['status'] = 'uploading'
                save_task(task)
                payload = dict(original_payload)
                contents = payload.pop('contents', [])
                refs = [part['inline_data'] for turn in contents for part in turn.get('parts', [])
                        if 'inline_data' in part]
                try:
                    native = task.get('model', MODEL) == MODEL
                    if refs and not native:
                        payload['image'] = [await upload_reference(task['key'], ref) for ref in refs]
                    task['reference_count'] = len(refs)
                    task['prompt'] = payload.get('prompt', '')
                    task['status'] = 'submitting'
                    save_task(task)
                    if native:
                        # GMI's queue route can reject valid ALL_IE promotional credit.
                        # Its documented Gemini-native route accepts the same key/credit.
                        native_parts = [{'text': payload.get('prompt', '')}]
                        native_parts.extend({'inlineData': {'mimeType': ref.get('mime_type') or ref.get('mimeType') or 'image/png',
                                                             'data': ref['data']}} for ref in refs)
                        native_body = {'contents': [{'role': 'user', 'parts': native_parts}],
                                       'generationConfig': {'imageConfig': {
                                           'imageSize': payload.get('image_size', '2K'),
                                           'aspectRatio': payload.get('aspect_ratio', '1:1')}}}
                        task['transport'] = 'gemini_native'
                        save_task(task)
                        raw = await gmi_http.request('POST', '/ie/requestqueue/apikey/requests/v1/models/' + MODEL + ':generateContent',
                                                     token=task['key'], body=native_body, timeout=900)
                        task['native_response_id'] = raw.get('responseId')
                    else:
                        raw = await gmi_http.request('POST', '/ie/requestqueue/apikey/requests',
                                                     token=task['key'], body={'model': task.get('model', MODEL), 'payload': payload}, timeout=900)
                    task['upstream_id'] = raw.get('request_id') or raw.get('id')
                    task.pop('pending_payload', None)
                    save_task(task)
                    break
                except gmi_http.ApiError as error:
                    if error.status != 402:
                        raise
                    excluded.add(task['email'])
                    async with _selection_lock:
                        record_credit_rejection(task['email'])
                        task.setdefault('credit_rejections', []).append(task['email'])
                        row = pick_available(excluded, task['id'])
                        if not row:
                            raise gmi_http.ApiError(503, '本轮可用账号均未通过生成额度校验；已有余额保留，未将账号标记为零')
                        task.update(email=row['email'], key=row['api_key'], status='queued')
                        save_task(task)
        else:
            raw = {}
        for attempt in range(600):
            urls = image_urls(raw)
            status = str(raw.get('status', '')).lower()
            if urls:
                url = await cache_image(task['id'], urls[0])
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
        phase = task.get('status', '')
        task['failed_phase'] = phase
        if phase == 'uploading':
            message = '参考图上传失败，尚未提交生图请求，可稍后重试。'
        elif task.get('upstream_id'):
            message = 'GMI任务已提交，但查询或下载异常，请保留任务编号，勿重复生成。'
        else:
            message = 'GMI提交连接异常，请保留任务编号核对上游记录，勿重复提交。'
        if isinstance(error, gmi_http.ApiError):
            message = str(error)
            if phase == 'uploading' and '尚未提交' not in message:
                message = '参考图上传失败，尚未提交生图请求：' + message
        task.update(status='failed', error=message, error_type=type(error).__name__)
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
        if task['status'] in ('queued', 'uploading', 'submitting', 'running'):
            if task.get('upstream_id'):
                spawn(run_task(task))
            elif task['status'] in ('queued', 'uploading') and task.get('pending_payload'):
                spawn(run_task(task, task['pending_payload']))
            else:
                task.update(status='failed', error='服务重启时提交中断，请核对上游记录，未自动重复提交')
                save_task(task)


@router.get('/api/gmi-scheduler')
async def scheduler_status(request: Request):
    guard(request)
    rows = gmi.records()
    stopped = sum(bool(r.get('scheduler_disabled')) or bool(r.get('balance') and float(r['balance'].get('total_usd',0)) <= 0) for r in rows)
    return {'total': len(rows), 'stopped_zero': stopped,
            'strategy': '空闲优先，最多100个并发；402冷却30分钟并换号，不改余额；超时不重发',
            'has_available': pick_available() is not None}


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
            await upload.close()
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
    edit_mode = data.get('edit_mode', '')
    if edit_mode not in ('', 'preserve_view'):
        raise HTTPException(400, '不支持的编辑模式')
    if edit_mode == 'preserve_view':
        if not parts or len(parts) != 3:
            raise HTTPException(400, '保留模板角度模式需要恰好两张图片：模板图、鞋款图')
        from PIL import Image
        from io import BytesIO
        first = base64.b64decode(parts[1]['inline_data']['data'], validate=True)
        try:
            with Image.open(BytesIO(first)) as original:
                target = original.width / original.height
        except Exception:
            raise HTTPException(400, '无法读取模板尺寸')
        choices = ('1:1','4:5','5:4','3:4','4:3','9:16','16:9','21:9')
        ratio = min(choices, key=lambda x: abs(int(x.split(':')[0])/int(x.split(':')[1])-target))
        prompt = preserve_view_prompt(prompt)
    payload = {'prompt': prompt, 'image_size': tier, 'aspect_ratio': ratio}
    if parts:
        payload['contents'] = [{'role': 'user', 'parts': parts}]
    async with _selection_lock:
        row = pick_available()
        if not row:
            raise HTTPException(503, 'GMI号池暂无空闲且有余额的账号，请稍后重试或检查余额')
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
