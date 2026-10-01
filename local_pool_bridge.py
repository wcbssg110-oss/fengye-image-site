"""Local-only adapter for Fengye and the existing GMI pool; no registration jobs."""
import asyncio
import base64
import json
import os
import re
import secrets
import sys
import uuid
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, os.environ.get('GMI_POOL_ROOT', r'D:\gmi-pool'))
from server import db, pool
from server.gmi_api import GmiClient, GmiError
from video_models import build_video

STATE = ROOT / '.local-pool'
STATE.mkdir(exist_ok=True)
TOKEN_FILE = STATE / 'token'
if not TOKEN_FILE.exists():
    TOKEN_FILE.write_text(secrets.token_urlsafe(32), encoding='utf-8')
TOKEN = TOKEN_FILE.read_text(encoding='utf-8').strip()
JOB_FILE = STATE / 'jobs.json'
JOBS = json.loads(JOB_FILE.read_text(encoding='utf-8')) if JOB_FILE.exists() else {}
ORIGINS = ['https://wcbssg110-oss.github.io', 'http://127.0.0.1:8792', 'http://localhost:8792']
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS,
                   allow_methods=['GET', 'POST', 'OPTIONS'],
                   allow_headers=['Content-Type', 'X-Pool-Token'])
LOCK = asyncio.Lock()

@app.middleware('http')
async def authorize(request: Request, call_next):
    origin = request.headers.get('origin')
    if origin and origin not in ORIGINS:
        return JSONResponse({'error': '不允许此网站访问本机号池'}, status_code=403)
    if request.url.path.startswith('/api/') and request.method != 'OPTIONS':
        if not secrets.compare_digest(request.headers.get('x-pool-token', ''), TOKEN):
            return JSONResponse({'error': '请从本机页面复制连接码并保存'}, status_code=401)
    response = await call_next(request)
    response.headers['Cache-Control'] = 'no-store'
    return response

@app.exception_handler(GmiError)
async def upstream_error(request, exc):
    return JSONResponse({'error': str(exc)}, status_code=502)

@app.exception_handler(pool.NoKeyError)
async def no_account(request, exc):
    return JSONResponse({'error': str(exc)}, status_code=503)

@app.exception_handler(pool.InsufficientBalance)
async def no_balance(request, exc):
    return JSONResponse({'error': str(exc)}, status_code=402)

def save_jobs():
    tmp = JOB_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(JOBS), encoding='utf-8')
    tmp.replace(JOB_FILE)

@app.get('/')
async def site():
    content = (ROOT / 'index.html').read_text(encoding='utf-8')
    config = {'base': 'http://127.0.0.1:8792', 'token': TOKEN}
    injected = '<script>window.FENGYE_LOCAL_POOL=' + json.dumps(config) + ';' \
        "localStorage.setItem('fengye_pool_enabled','1');localStorage.setItem('llt_image_provider','gmi');" \
        "localStorage.setItem('llt_model','gemini-3-pro-image');</script>"
    return Response(content.replace('<head>', '<head>' + injected, 1), media_type='text/html')

@app.get('/api/pool-connection')
async def connection():
    stats = pool.stats()
    return {'ok': True, 'service': 'fengye-gmi-pool-bridge', 'stats': stats}

def prompt_check(body):
    prompt = str(body.get('prompt') or '').strip()
    if not prompt or len(prompt) > 2000:
        raise HTTPException(400, '提示词须为 1–2000 字符')
    return prompt

async def pool_api(method, path, body=None):
    async with httpx.AsyncClient(timeout=180,trust_env=False) as client:
        response=await client.request(method,'http://127.0.0.1:8790'+path,json=body)
        data=response.json()
        if not response.is_success:raise HTTPException(response.status_code,data.get('detail') or data.get('error') or '号池调用失败')
        return data

async def submit_image(body, refs):
    model = body.get('model', 'gemini-3-pro-image')
    if model not in ('gemini-3-pro-image', 'gemini-3.1-flash-image-preview'):
        raise HTTPException(400, '本机号池仅支持配置的 Gemini 图片模型')
    payload = {'prompt': prompt_check(body), 'image_size': body.get('image_size', '2K'),
               'aspect_ratio': body.get('aspect_ratio', '1:1')}
    if payload['image_size'] not in ('1K', '2K', '4K'):
        raise HTTPException(400, '图片分辨率须为 1K、2K 或 4K')
    if payload['aspect_ratio'] not in ('1:1','3:2','2:3','3:4','4:3','4:5','5:4','9:16','16:9','21:9'):
        raise HTTPException(400, '图片比例不受支持')
    if len(refs) > 14:
        raise HTTPException(400, '最多 14 张参考图')
    if refs:
        # contents is the documented path for inline reference images.
        parts = [{'text': payload.pop('prompt')}]
        for ref in refs:
            parts.append({'inlineData': ref} if isinstance(ref, dict)
                         else {'fileData': {'fileUri': ref, 'mimeType': 'image/jpeg'}})
        payload['contents'] = [{'role': 'user', 'parts': parts}]
    result=await pool_api('POST','/v1/requests',{'model':model,'payload':payload})
    return result['id']

async def poll(task_id):
    task = db.get_task(task_id)
    if not task:
        raise HTTPException(404, '任务不存在')
    if task['status'] in ('queued','running'):
        await pool_api('GET','/v1/video/generations/'+task_id)
        task=db.get_task(task_id)
    media = task.get('media') or []
    if isinstance(media, str):
        media = json.loads(media)
    return task, media

@app.post('/api/gmi-image')
async def image_submit(request: Request):
    refs = []
    if 'multipart/form-data' in request.headers.get('content-type',''):
        form = await request.form()
        body = dict(form)
        for value in form.getlist('image'):
            raw = await value.read(7 * 1024 * 1024 + 1)
            if len(raw) > 7 * 1024 * 1024 or not value.content_type.startswith('image/'):
                raise HTTPException(400, '参考图须为图片且不超过 7MB')
            refs.append({'mimeType': value.content_type, 'data': base64.b64encode(raw).decode()})
    else:
        body = await request.json()
    count = int(body.get('n', 1))
    if not 1 <= count <= 4:
        raise HTTPException(400, '每次生成 1–4 张图片')
    job = 'images_' + uuid.uuid4().hex
    JOBS[job] = []
    for _ in range(count):
        JOBS[job].append(await submit_image(body, refs))
        save_jobs()
    return {'id': job, 'status': 'queued'}

@app.get('/api/gmi-image')
async def image_status(task_id: str):
    ids = JOBS.get(task_id)
    if not ids:
        raise HTTPException(404, '图片任务不存在')
    results = [await poll(tid) for tid in ids]
    failed = next((t for t, _ in results if t['status'] == 'failed'), None)
    if failed:
        return {'id': task_id, 'status': 'failed', 'error': failed.get('error')}
    if any(t['status'] != 'completed' for t, _ in results):
        return {'id': task_id, 'status': 'running'}
    urls = []
    for t, media in results:
        for index, url in enumerate(media):
            urls.append({'url': await cache_media(t['id'], index, url, '.png')})
    return {'id': task_id, 'status': 'completed', 'data': urls}

@app.post('/api/gmi-video')
async def video_submit(request: Request):
    body = await request.json()
    for key in ('first_frame','last_frame','image','first_clip'):
        if body.get(key): body[key] = await resolve_media(body[key])
    for key in ('reference_images','reference_videos'):
        if body.get(key): body[key] = [await resolve_media(u) for u in body[key]]
    try:
        model, payload = build_video(body)
    except (ValueError, TypeError) as exc:
        raise HTTPException(400, str(exc))
    result=await pool_api('POST','/v1/requests',{'model':model,'payload':payload})
    return {'request_id':result['id'],'status':'queued','estimated_cost_usd':result['estimated_cost_usd'],
            'balance_usd':result['balance_usd']}

@app.post('/api/gmi-quote')
async def price_quote(request: Request):
    body=await request.json()
    body['prompt']=body.get('prompt') or '费用预估'
    try: model,payload=build_video(body)
    except (ValueError,TypeError) as exc: raise HTTPException(400,str(exc))
    return await pool_api('POST','/v1/quote',{'model':model,'payload':payload})

async def resolve_media(value):
    local = re.fullmatch(r'http://127\.0\.0\.1:8792/media/(gmi_[a-f0-9]{24})-(\d+)\.(png|mp4)', value)
    if local:
        _, media = await poll(local[1])
        index = int(local[2])
        if index >= len(media): raise HTTPException(400, '素材不存在')
        return media[index]
    if not isinstance(value, str) or not value.startswith('https://'):
        raise HTTPException(400, '素材须上传成功后再提交')
    return value

@app.post('/api/gmi-upload')
async def upload(request: Request):
    form = await request.form()
    file = form.get('file')
    if not file or not hasattr(file, 'read'): raise HTTPException(400, '请选择素材文件')
    ext = Path(file.filename or '').suffix.lower().lstrip('.')
    mime = {'jpg':'image/jpeg','jpeg':'image/jpeg','png':'image/png','mp4':'video/mp4'}
    if ext not in mime: raise HTTPException(400, '支持 JPG、PNG 图片和 MP4 视频')
    limit = (10 if ext != 'mp4' else 50) * 1024 * 1024
    raw = await file.read(limit+1)
    if not raw or len(raw)>limit: raise HTTPException(400, '图片上限 10MB，视频上限 50MB')
    if ext == 'png' and not raw.startswith(b'\x89PNG\r\n\x1a\n'): raise HTTPException(400, 'PNG 文件格式错误')
    if ext in ('jpg','jpeg') and not raw.startswith(b'\xff\xd8\xff'): raise HTTPException(400, 'JPEG 文件格式错误')
    if ext == 'mp4' and b'ftyp' not in raw[:64]: raise HTTPException(400, 'MP4 文件格式错误')
    account = pool.pick_account()
    client = GmiClient()
    try:
        signed = await client.request('POST', '/ie/requestqueue/apikey/upload-url',
            token=account['api_key'], json_body={'file_type': ext})
    finally:
        await client.close()
    async with httpx.AsyncClient(timeout=180, trust_env=True) as http:
        resp = await http.put(signed['upload_url'], content=raw, headers={'Content-Type':mime[ext]})
        if not resp.is_success: raise HTTPException(502, '素材上传失败，请重试')
    return {'url':signed['public_url'], 'name':file.filename}

@app.get('/api/gmi-video')
async def video_status(task_id: str):
    task, media = await poll(task_id)
    out = {'request_id': task_id, 'status': task['status'], 'error': task.get('error'),
           'charge':None}
    if task['status'] == 'completed' and media:
        out['outcome'] = {'video_url': await cache_media(task_id, 0, media[0], '.mp4')}
    return out

MEDIA = STATE / 'media'
MEDIA.mkdir(exist_ok=True)
async def cache_media(task_id, index, url, ext):
    name = f'{task_id}-{index}{ext}'
    target = MEDIA / name
    if not target.exists():
        tmp = target.with_suffix(ext + '.' + uuid.uuid4().hex + '.tmp')
        try:
            async with httpx.AsyncClient(timeout=300, follow_redirects=True, trust_env=True) as client:
                async with client.stream('GET', url) as resp:
                    resp.raise_for_status()
                    with tmp.open('wb') as f:
                        async for chunk in resp.aiter_bytes():
                            f.write(chunk)
            tmp.replace(target)
        finally:
            tmp.unlink(missing_ok=True)
    return f'http://127.0.0.1:8792/media/{name}'

app.mount('/media', StaticFiles(directory=MEDIA), name='media')
@app.get('/flow-api.js')
async def flow_script():
    return FileResponse(ROOT / 'flow-api.js', media_type='application/javascript')

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=8792)
