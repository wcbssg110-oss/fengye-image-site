"""Local-only adapter for Fengye and the existing GMI pool; no registration jobs."""
import asyncio
import base64
import contextvars
import json
import os
import re
import secrets
import sys
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent
BRIDGE_PORT = int(os.environ.get('FENGYE_BRIDGE_PORT', '8793'))
BRIDGE_BASE = f'http://127.0.0.1:{BRIDGE_PORT}'
# ── 对外基址（2026-10-07）──────────────────────────────────
# 桥接可以放到公网（Cloudflare Tunnel / frp / nginx 反代）让云端页面直接调。
# 对外基址**按请求头自动判定**：只要进来的 Host 不是 127.0.0.1/localhost，
# 就用 `X-Forwarded-Proto + Host` 当基址回给前端 —— 本地请求照旧回 127.0.0.1，
# 隧道请求自动回隧道地址，两边都不用改配置。
# 需要固定对外地址时再用 FENGYE_BRIDGE_PUBLIC_BASE 覆盖（例 https://gmi.wcbssg.xyz）。
# 为什么必须这样：回给前端的 /media/xxx.png 如果还是 http://127.0.0.1:8793/…，
# 云端页面（https 的 github.io）既跨不过混合内容、也连不到你的 127.0.0.1。
PUBLIC_BASE = os.environ.get('FENGYE_BRIDGE_PUBLIC_BASE', '').strip().rstrip('/')
# 额外允许的浏览器 Origin（逗号分隔）。公网域名自己开页面时把自己加进来即可；
# 不填也行 —— 同站 Origin（host 与请求 Host 一致）已经默认放行。
EXTRA_ORIGINS = [o.strip().rstrip('/') for o in
                 os.environ.get('FENGYE_BRIDGE_EXTRA_ORIGINS', '').split(',') if o.strip()]

# 当前请求的对外基址（由 authorize 中间件按 Host 头写入）
_REQ_BASE: contextvars.ContextVar[str] = contextvars.ContextVar('bridge_req_base', default='')
_LOOPBACK_HOSTS = ('127.0.0.1', 'localhost', '::1')


def bridge_base() -> str:
    """回给前端的基址：本次请求经隧道进来就用隧道地址，否则本机地址。"""
    return _REQ_BASE.get() or PUBLIC_BASE or BRIDGE_BASE

sys.path.insert(0, os.environ.get('GMI_POOL_ROOT', r'D:\gmi-pool'))
from server import db, pool
from server.gmi_api import GmiClient, GmiError
from server.video_errors import failure_message
from video_models import build_video

STATE = ROOT / '.local-pool'
STATE.mkdir(exist_ok=True)
TOKEN_FILE = STATE / 'token'
if not TOKEN_FILE.exists():
    TOKEN_FILE.write_text(secrets.token_urlsafe(32), encoding='utf-8')
TOKEN = TOKEN_FILE.read_text(encoding='utf-8').strip()
JOB_FILE = STATE / 'jobs.json'
JOBS = json.loads(JOB_FILE.read_text(encoding='utf-8')) if JOB_FILE.exists() else {}
ERROR_FILE = STATE / 'job-errors.json'
JOB_ERRORS = json.loads(ERROR_FILE.read_text(encoding='utf-8')) if ERROR_FILE.exists() else {}
# A request with no upstream id cannot be resubmitted safely after a process exit.
INTERRUPTED_JOBS = {job for job, ids in JOBS.items() if not ids and job not in JOB_ERRORS}
ORIGINS = ['https://wcbssg110-oss.github.io', BRIDGE_BASE, f'http://localhost:{BRIDGE_PORT}',
           'http://127.0.0.1:8792', 'http://localhost:8792']
if PUBLIC_BASE:
    ORIGINS.append(PUBLIC_BASE)
ORIGINS += [o for o in EXTRA_ORIGINS if o not in ORIGINS]
app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=ORIGINS,
                   allow_methods=['GET', 'POST', 'OPTIONS'],
                   allow_headers=['Content-Type', 'X-Pool-Token', 'Cache-Control', 'Pragma'],
                   allow_private_network=True)
LOCK = asyncio.Lock()
BACKGROUND_JOBS = set()
# 终态任务缓存：task_id -> {'names': [...], 'data': [...]}
# 用于让已完成的轮询直接命中本地结果，不再每 2s 去查一次 GMI 上游。
# 与 JOBS 一样落盘：桥接重启后老任务仍能秒回，不会退回「慢慢显示」。
COMPLETED_FILE = STATE / 'completed.json'
COMPLETED = json.loads(COMPLETED_FILE.read_text(encoding='utf-8')) if COMPLETED_FILE.exists() else {}

def save_completed():
    COMPLETED_FILE.write_text(json.dumps(COMPLETED, ensure_ascii=False), encoding='utf-8')

@app.middleware('http')
async def authorize(request: Request, call_next):
    origin = request.headers.get('origin')
    raw_host = request.headers.get('host') or ''
    host = raw_host.split(':')[0].strip().lower()
    # ① 判定本次请求的对外基址：Host 不是回环 → 说明是经隧道/反代进来的，
    #    用转发头拼出对外地址，后面回给前端的 /media 链接就自动是公网地址。
    if host and host not in _LOOPBACK_HOSTS:
        proto = (request.headers.get('x-forwarded-proto') or '').split(',')[0].strip() or 'https'
        _REQ_BASE.set(f'{proto}://{raw_host}')
    else:
        _REQ_BASE.set('')
    # ② Origin 白名单：已有的 ORIGINS 之外，同站（Origin 的 host == 请求 Host）
    #    也放行 —— 这样用隧道域名打开页面时不用改配置。
    same_site = False
    if origin:
        try:
            same_site = (urlparse(origin).hostname or '').lower() == host
        except ValueError:
            same_site = False
    if origin and origin not in ORIGINS and not same_site:
        return JSONResponse({'error': '不允许此网站访问本机号池'}, status_code=403)
    if request.url.path.startswith('/api/') and request.method != 'OPTIONS':
        if not secrets.compare_digest(request.headers.get('x-pool-token', ''), TOKEN):
            headers={'Access-Control-Allow-Origin':origin,'Vary':'Origin'} if (origin in ORIGINS or same_site) else {}
            return JSONResponse({'error': '请从本机页面复制连接码并保存'}, status_code=401,headers=headers)
    try:
        response = await call_next(request)
    except httpx.TimeoutException:
        response = JSONResponse({'error':'号池提交等待超时，请查询已有任务，不要重复生成'},status_code=504)
    except Exception:
        response = JSONResponse({'error':'号池服务处理失败，请查询已有任务或查看服务日志'},status_code=500)
    if origin in ORIGINS or same_site:
        response.headers['Access-Control-Allow-Origin'] = origin
        response.headers['Vary'] = 'Origin' 
    response.headers['Cache-Control'] = 'no-store'
    if origin in ORIGINS and request.headers.get('access-control-request-private-network')=='true':
        response.headers['Access-Control-Allow-Private-Network']='true'
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

def save_errors():
    tmp = ERROR_FILE.with_suffix('.tmp')
    tmp.write_text(json.dumps(JOB_ERRORS, ensure_ascii=False), encoding='utf-8')
    tmp.replace(ERROR_FILE)

@app.get('/')
async def site():
    content = (ROOT / 'index.html').read_text(encoding='utf-8')
    config = {'base': bridge_base(), 'token': TOKEN}
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


def describe_error(exc):
    """把裸异常名翻译成能指导用户动作的话。

    历史症状：号池把一批出图串行排队超过 15 分钟，前端只看到 `ReadTimeout`
    三个字，既不知道是自己点多了还是服务挂了，也没提示别重复提交。
    """
    if isinstance(exc, httpx.TimeoutException):
        return ('本机号池 15 分钟内没受理这一单（多半是批量出图排队，'
                '或号池同时在跑注册任务）。先点「找回已生成图片」，别重复提交；'
                '再减少一次出图数量后重试。')
    if isinstance(exc, httpx.ConnectError):
        return '连不上本机号池（127.0.0.1:8790），请确认号池服务正在运行。'
    return str(exc) or type(exc).__name__


def media_proxy_candidates():
    """GMI 的成图直链在 storage.googleapis.com 上，**直连是不通的**。

    实测：不带代理 `curl` 该直链 21 秒后返回 000；走 ikuuu 内核
    (127.0.0.1:12000) 或系统代理都是 0.4 秒 200。所以素材必须由桥接
    自己经代理拉回来再吐给浏览器 —— 绝不能把 GCS 直链塞进前端 <img>，
    否则号池那边明明出图了，网页上永远是空白框。

    本机回环（127.0.0.1:8790）反过来绝对不能走代理，那条路径在 pool_api 里
    已经写死 trust_env=False。
    """
    out = []
    for key in ('FENGYE_MEDIA_PROXY', 'HTTPS_PROXY', 'https_proxy',
                'HTTP_PROXY', 'http_proxy', 'ALL_PROXY', 'all_proxy'):
        value = (os.environ.get(key) or '').strip()
        if value and value not in out:
            out.append(value)
    for port in (os.environ.get('GMI_PROXY_PORTS') or '12000').split(','):
        candidate = 'http://127.0.0.1:' + port.strip()
        if candidate not in out:
            out.append(candidate)
    if 'http://127.0.0.1:12000' not in out:
        out.append('http://127.0.0.1:12000')
    return out

async def pool_api(method, path, body=None):
    # 本机回环请求必须绕过系统/环境里的 http_proxy —— 代理会把 127.0.0.1:8790
    # 一起劫持掉，表现为 502 "upstream connect failed"，进而让前端永远卡在 queued。
    async with httpx.AsyncClient(timeout=httpx.Timeout(900, connect=10), trust_env=False,
                                 proxy=None) as client:
        response=await client.request(method,'http://127.0.0.1:8790'+path,json=body,
                                      headers={'X-Skip-Proxy':'1'})
        data=response.json()
        if not response.is_success:raise HTTPException(response.status_code,data.get('detail') or data.get('error') or '号池调用失败')
        return data

async def submit_image(body, refs):
    model = body.get('model', 'gemini-3-pro-image')
    if model.startswith('gpt-image-2.5-'):
        if model not in tuple('gpt-image-2.5-' + variant + '-' + mode for variant in ('sunburst','flare') for mode in ('generate','edit')):
            raise HTTPException(400, '不支持的 GPT Image 模型')
        payload = dict(body.get('payload') or {})
        if payload.get('quality') not in ('low','medium','high','xhigh','max'):
            raise HTTPException(400, '请指定图片质量')
        prompt_check(payload)
        payload['n'] = 1
        result = await pool_api('POST','/v1/requests',{'model':model,'payload':payload})
        return result['id']
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
    count = int((body.get('payload') or body).get('n', 1))
    if not 1 <= count <= 4:
        raise HTTPException(400, '每次生成 1–4 张图片')
    job = 'images_' + uuid.uuid4().hex
    JOBS[job] = []
    save_jobs()
    async def dispatch():
        try:
            for _ in range(count):
                JOBS[job].append(await submit_image(body, refs))
                save_jobs()
        except Exception as exc:
            JOB_ERRORS[job] = describe_error(exc)
            save_errors()
    background = asyncio.create_task(dispatch())
    BACKGROUND_JOBS.add(background)
    background.add_done_callback(BACKGROUND_JOBS.discard)
    return {'id': job, 'status': 'queued'}

@app.get('/api/gmi-image')
async def image_status(task_id: str):
    # ⚠️ 终态短路（关键性能修复）：completed 是不可逆的终态，一旦结果
    # 已缓存（本地 `/media/` 文件已落盘），就直接返回，**绝不再查 GMI 上游**。
    # 原实现每次 GET 都跑一遍 `poll(tid)`（境外网络往返），前端 2s 一次
    # 轮询就层层堆积 —— 页面表现为「图已生成完，却还在慢慢显示」。
    cached = COMPLETED.get(task_id)
    if cached and cached.get('names'):
        urls = [{'url': f'{bridge_base()}/media/{name}'}
                for name in cached['names'] if (MEDIA / name).exists()]
        if len(urls) == len(cached['names']):
            return {'id': task_id, 'status': 'completed', 'data': urls}

    ids = JOBS.get(task_id)
    if task_id in JOB_ERRORS:
        return {'id':task_id,'status':'failed','error':JOB_ERRORS[task_id]}
    if task_id in INTERRUPTED_JOBS:
        return {'id':task_id,'status':'failed','recoverable':True,
                'error':'连接服务曾中断，提交结果尚未确认；请先找回已生成图片，避免重复生成。'}
    if ids == []:
        return {'id':task_id,'status':'queued'}
    if ids is None:
        raise HTTPException(404, '图片任务不存在')
    results = [await poll(tid) for tid in ids]
    failed = next((t for t, _ in results if t['status'] == 'failed'), None)
    if failed:
        return {'id': task_id, 'status': 'failed', 'error': failed.get('error')}
    if any(t['status'] != 'completed' for t, _ in results):
        return {'id': task_id, 'status': 'running'}
    urls = []
    names = []
    for t, media in results:
        for index, url in enumerate(media):
            # 绝不能把 GCS 直链原样返回：浏览器在国内加载不出来，任务卡会
            # 显示「已完成（N 张）」却是一片空白。一律先落到本地 /media/ 再给前端。
            try:
                local = await cache_media(t['id'], index, url, '.png')
            except HTTPException:
                local = url
            urls.append({'url': local})
            names.append(local.rsplit('/', 1)[-1])
    # 记下终态，后续轮询直接命中缓存，不再触碰上游。
    # ⚠️ 只有真正拿到图才写缓存：`names` 为空说明上游返回了空结果
    # （常见于 `JOBS[task] == []` 的坏任务），写进去会让前端永远空白。
    if names:
        COMPLETED[task_id] = {'names': names, 'data': urls}
        save_completed()
    return {'id': task_id, 'status': 'completed', 'data': urls}

@app.get('/api/gmi-results')
async def recovered_images():
    results = []
    for job, ids in list(JOBS.items())[-100:]:
        for tid in ids:
            task = db.get_task(tid)
            if not task or task['status'] != 'completed':
                continue
            media = task.get('media') or []
            if isinstance(media, str): media = json.loads(media)
            for index, url in enumerate(media):
                results.append({'task_id':tid, 'url':await cache_media(tid,index,url,'.png')})
    return {'data':results}

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
    # 接受本机地址、8792 备用口、以及对外基址三种前缀（对外基址见 bridge_base()）
    bases = sorted({BRIDGE_BASE, 'http://127.0.0.1:8792', bridge_base()}, key=len, reverse=True)
    local = re.fullmatch(
        r'(?:' + '|'.join(re.escape(b) for b in bases) +
        r')/media/(gmi_[a-f0-9]{24})-(\d+)\.(png|mp4)', value)
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
    limit = 10 * 1024 * 1024
    raw = await file.read(limit+1)
    if not raw or len(raw)>limit: raise HTTPException(400, '图片上限 10MB，视频上限 10MB')
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
    # 上传目标同样是 GCS，直连不通 → 按候选代理逐个试（见 media_proxy_candidates）
    errors = []
    for proxy in media_proxy_candidates() + [None]:
        try:
            async with httpx.AsyncClient(timeout=180, trust_env=False, proxy=proxy) as http:
                resp = await http.put(signed['upload_url'], content=raw,
                                      headers={'Content-Type': mime[ext]})
            if resp.is_success:
                return {'url': signed['public_url'], 'name': file.filename}
            errors.append(f'{proxy or "直连"}: HTTP {resp.status_code}')
        except Exception as exc:  # noqa: BLE001
            errors.append(f'{proxy or "直连"}: {type(exc).__name__} {exc}'.strip())
    raise HTTPException(502, '素材上传失败（直链不通、代理也没通）：' + '；'.join(errors[:3]))

@app.get('/api/gmi-video')
async def video_status(task_id: str):
    task, media = await poll(task_id)
    out = {'request_id': task_id, 'status': task['status'], 'error': failure_message(task.get('error')) if task['status'] == 'failed' else '',
           'charge':None}
    if task['status'] == 'completed' and media:
        out['outcome'] = {'video_url': await cache_media(task_id, 0, media[0], '.mp4')}
    return out

MEDIA = STATE / 'media'
MEDIA.mkdir(exist_ok=True)
def image_content_type(path):
    with path.open('rb') as source:
        header = source.read(16)
    if header.startswith(b'\x89PNG\r\n\x1a\n'): return 'image/png'
    if header.startswith(b'\xff\xd8\xff'): return 'image/jpeg'
    if header[:6] in (b'GIF87a', b'GIF89a'): return 'image/gif'
    if header[:4] == b'RIFF' and header[8:12] == b'WEBP': return 'image/webp'
    raise HTTPException(502, '没有取得有效图片，请重试下载；无需重新生成')

async def cache_media(task_id, index, url, ext):
    """把上游素材落到本地 `/media/` 再返回本地地址。

    必须落地的原因见 media_proxy_candidates()：GCS 直链浏览器直连不通。
    代理按候选列表逐个试，最后再试一次直连；全失败才报错，并把各自的原因带出来。
    """
    name = f'{task_id}-{index}{ext}'
    target = MEDIA / name
    if target.exists() and target.stat().st_size:
        return f'{bridge_base()}/media/{name}'
    tmp = target.with_suffix(ext + '.' + uuid.uuid4().hex + '.tmp')
    errors = []
    try:
        for proxy in media_proxy_candidates() + [None]:
            label = proxy or '直连'
            try:
                async with httpx.AsyncClient(timeout=300, follow_redirects=True,
                                             trust_env=False, proxy=proxy) as client:
                    async with client.stream('GET', url) as resp:
                        resp.raise_for_status()
                        with tmp.open('wb') as sink:
                            async for chunk in resp.aiter_bytes():
                                sink.write(chunk)
                if tmp.exists() and tmp.stat().st_size:
                    break
                errors.append(label + ': 空响应')
            except Exception as exc:  # noqa: BLE001
                errors.append(f'{label}: {type(exc).__name__} {exc}'.strip())
            finally:
                if not (tmp.exists() and tmp.stat().st_size):
                    tmp.unlink(missing_ok=True)
        if not (tmp.exists() and tmp.stat().st_size):
            raise HTTPException(502, '素材下载失败（直链不通、代理也没通）：'
                                     + '；'.join(errors[:3]))
        if ext == '.png':
            try:
                image_content_type(tmp)
            except HTTPException:
                pass  # 上游偶尔回 jpg/webp，按扩展名存下来就行，别判成失败
        tmp.replace(target)
    finally:
        tmp.unlink(missing_ok=True)
    return f'{bridge_base()}/media/{name}'

@app.post('/api/gmi-download')
async def download_image(request: Request):
    body = await request.json()
    url = str(body.get('url') or '')
    # Only fetch media already returned by a completed pool task, never arbitrary URLs.
    with db.connect() as conn:
        tasks = conn.execute("SELECT id, media FROM tasks WHERE status='completed' AND model LIKE 'gemini%image%' ORDER BY created_at DESC").fetchall()
    for task in tasks:
        for index, remote in enumerate(json.loads(task['media'] or '[]')):
            local_name = f"{task['id']}-{index}.png"
            local_urls = (f'{bridge_base()}/media/{local_name}', f'http://127.0.0.1:8792/media/{local_name}')
            if url == remote or url in local_urls:
                await cache_media(task['id'], index, remote, '.png')
                target = MEDIA / local_name
                mime = image_content_type(target)
                ext = {'image/png':'.png','image/jpeg':'.jpg','image/gif':'.gif','image/webp':'.webp'}[mime]
                return FileResponse(target, media_type=mime, filename=task['id'] + ext)
    raise HTTPException(400, '只能下载号池中已生成的图片，请先找回生成结果')

app.mount('/media', StaticFiles(directory=MEDIA), name='media')
@app.get('/flow-api.js')
async def flow_script():
    return FileResponse(ROOT / 'flow-api.js', media_type='application/javascript')

if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='127.0.0.1', port=BRIDGE_PORT)
