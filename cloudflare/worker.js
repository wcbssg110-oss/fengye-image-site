import videoContract from '../video-contract.cjs';
const ALLOWED_ORIGINS = new Set([
  'https://wcbssg110-oss.github.io',
  'http://127.0.0.1:8791',
  'http://localhost:8791',
  'http://127.0.0.1:8792',
  'http://localhost:8792',
]);
const VIDEO_HOST = 'console.gmicloud.ai';
const VIDEO_QUEUE = '/api/v1/ie/requestqueue/apikey/requests';
const IMAGE_HOST = 'api.gmi-serving.com';
const VIDEO_MODELS = new Set([
  'seedance-2-5-260628',
  'kling-3.0-turbo-t2v',
  'kling-3.0-turbo-i2v',
  'wan2.7-t2v',
  'wan2.7-i2v',
]);

function json(status, value, origin) {
  return new Response(JSON.stringify(value), {
    status,
    headers: responseHeaders(origin, 'application/json; charset=utf-8'),
  });
}

function responseHeaders(origin, contentType) {
  const headers = new Headers({
    'Cache-Control': 'no-store',
    'Vary': 'Origin',
  });
  if (contentType) headers.set('Content-Type', contentType);
  if (ALLOWED_ORIGINS.has(origin)) {
    headers.set('Access-Control-Allow-Origin', origin);
    headers.set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS');
    headers.set('Access-Control-Allow-Headers', 'Content-Type, X-Site-Password, X-GMI-API-Key, X-OpenAI-API-Key');
    headers.set('Access-Control-Max-Age', '86400');
  }
  return headers;
}

function validTaskId(value) {
  return /^[A-Za-z0-9_-]{1,160}$/.test(value);
}

function validPublicImageUrl(value) {
  if (typeof value !== 'string' || value.length > 2048) return false;
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && Boolean(url.hostname) && !url.username && !url.password;
  } catch (_) {
    return false;
  }
}

async function analyzeVideoPrompt(request, apiKey, origin) {
  let incoming;
  try { incoming = await request.json(); }
  catch (_) { return json(400, { error: 'request body must be valid JSON' }, origin); }
  const images = incoming && Array.isArray(incoming.images) ? incoming.images : [];
  if (!images.length || images.length > 8 || !images.every(validPublicImageUrl)) {
    return json(400, { error: '请提供 1 到 8 张可公开访问的 HTTPS 参考图' }, origin);
  }
  const idea = typeof incoming.idea === 'string' ? incoming.idea.trim().slice(0, 1500) : '';
  const content = [{
    type: 'input_text',
    text: `请分析参考图，提炼主体、场景、动作、镜头语言、光线和视觉风格，写出一段适合 Seedance 2.5、可灵或 Wan 的中文视频生成提示词。只输出可直接用于生成的提示词，不要解释，不要添加时长或时间轴。${idea ? `\n用户补充想法：${idea}` : ''}`,
  }, ...images.map(image_url => ({ type: 'input_image', image_url, detail: 'low' }))];
  const upstream = await fetch('https://api.openai.com/v1/responses', {
    method: 'POST',
    headers: { Authorization: `Bearer ${apiKey}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ model: 'gpt-5-mini', input: [{ role: 'user', content }] }),
  });
  const outHeaders = responseHeaders(origin, upstream.headers.get('Content-Type') || 'application/json');
  if (!upstream.ok) return new Response(upstream.body, { status: upstream.status, headers: outHeaders });
  const result = await upstream.json();
  const outputText = typeof result.output_text === 'string' ? result.output_text : (result.output || [])
    .flatMap(item => item.content || []).filter(part => part.type === 'output_text').map(part => part.text || '').join('\n');
  return json(200, { prompt: outputText.trim() }, origin);
}

async function forward(url, method, apiKey, request, origin, contentType) {
  const headers = new Headers({
    Authorization: `Bearer ${apiKey}`,
    Accept: 'application/json',
  });
  if (method === 'POST') {
    headers.set('Content-Type', contentType || 'application/json');
  }
  const upstream = await fetch(url, {
    method,
    headers,
    body: method === 'POST' ? request.body : undefined,
    redirect: 'manual',
  });
  const outHeaders = responseHeaders(origin, upstream.headers.get('Content-Type') || 'application/json');
  return new Response(upstream.body, { status: upstream.status, headers: outHeaders });
}

async function uploadRequest(request, apiKey, origin) {
  if(request.method!=='POST')return json(405,{error:'method not allowed'},origin);
  const form=await request.formData(),file=form.get('file');
  if(!file||typeof file.arrayBuffer!=='function')return json(400,{error:'请选择素材'},origin);
  const ext=file.name.split('.').pop().toLowerCase(), mime={png:'image/png',jpg:'image/jpeg',jpeg:'image/jpeg',mp4:'video/mp4'};
  if(!mime[ext]||file.size>10*1024*1024)return json(400,{error:'图片支持JPG/PNG且≤10MB；视频支持MP4且≤10MB'},origin);
  const sign=await fetch('https://'+VIDEO_HOST+'/api/v1/ie/requestqueue/apikey/upload-url',{method:'POST',headers:{Authorization:'Bearer '+apiKey,'Content-Type':'application/json'},body:JSON.stringify({file_type:ext})});
  const data=await sign.json();if(!sign.ok)return json(sign.status,data,origin);
  const result=await fetch(data.upload_url,{method:'PUT',headers:{'Content-Type':mime[ext]},body:file.stream()});
  if(!result.ok)return json(502,{error:'素材上传失败'},origin);
  return json(200,{url:data.public_url,name:file.name},origin);
}

async function videoRequest(request, url, apiKey, origin) {
  if (request.method === 'GET') {
    const taskId = url.searchParams.get('task_id') || '';
    if (!validTaskId(taskId)) return json(400, { error: 'invalid task id' }, origin);
    const target = `https://${VIDEO_HOST}${VIDEO_QUEUE}/${encodeURIComponent(taskId)}`;
    return forward(target, 'GET', apiKey, request, origin);
  }

  let incoming;
  try {
    incoming = await request.json();
  } catch (_) {
    return json(400, { error: 'request body must be valid JSON' }, origin);
  }
  if (!incoming || typeof incoming !== 'object' || Array.isArray(incoming)) {
    return json(400, { error: 'request body must be a JSON object' }, origin);
  }

  let model,payload;
  try {({model,payload}=videoContract.buildVideo(incoming));}
  catch(e){return json(400,{error:e.message},origin);}

  const target = `https://${VIDEO_HOST}${VIDEO_QUEUE}`;
  const headers = new Headers({
    Authorization: `Bearer ${apiKey}`,
    Accept: 'application/json',
    'Content-Type': 'application/json',
  });
  const upstream = await fetch(target, {
    method: 'POST',
    headers,
    body: JSON.stringify({ model, payload }),
  });
  return new Response(upstream.body, {
    status: upstream.status,
    headers: responseHeaders(origin, upstream.headers.get('Content-Type') || 'application/json'),
  });
}

async function imageRequest(request, url, apiKey, origin) {
  let target;
  if (request.method === 'GET') {
    const taskId = url.searchParams.get('task_id') || '';
    if (!validTaskId(taskId)) return json(400, { error: 'invalid task id' }, origin);
    target = url.searchParams.get('queue') === '1' ? `https://${VIDEO_HOST}${VIDEO_QUEUE}/${encodeURIComponent(taskId)}` : `https://${IMAGE_HOST}/v1/tasks/${encodeURIComponent(taskId)}`;
    return forward(target, 'GET', apiKey, request, origin);
  }
  if (url.searchParams.get('queue') === '1') {
    let incoming;
    try { incoming = await request.json(); } catch (_) { return json(400, {error:'invalid JSON'}, origin); }
    if (!/^gpt-image-2\.5-(sunburst|flare)-(generate|edit)$/.test(incoming.model || '')) return json(400, {error:'unsupported image model'}, origin);
    const payload = incoming.payload;
    if (!payload || !['low','medium','high','xhigh','max'].includes(payload.quality) || !/^\d+x\d+$/.test(payload.size || '')) return json(400, {error:'explicit size and quality required'}, origin);
    const upstream = await fetch(`https://${VIDEO_HOST}${VIDEO_QUEUE}`, {method:'POST', headers:{Authorization:`Bearer ${apiKey}`, 'Content-Type':'application/json'}, body:JSON.stringify(incoming)});
    return new Response(upstream.body, {status:upstream.status, headers:responseHeaders(origin, upstream.headers.get('Content-Type'))});
  }
  const edits = url.searchParams.get('edits') === '1';
  target = `https://${IMAGE_HOST}${edits ? '/v1/images/edits' : '/v1/images/generations'}`;
  const contentType = request.headers.get('Content-Type') || 'application/json';
  if (!contentType.startsWith('multipart/form-data') && !contentType.startsWith('application/json')) {
    return json(415, { error: 'unsupported content type' }, origin);
  }
  const length = Number(request.headers.get('Content-Length') || 0);
  if (length > 25 * 1024 * 1024) return json(413, { error: 'image request is too large' }, origin);
  return forward(target, 'POST', apiKey, request, origin, contentType);
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const origin = request.headers.get('Origin') || '';
    if (origin && !ALLOWED_ORIGINS.has(origin)) return json(403, { error: 'origin not allowed' }, '');

    if (request.method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: responseHeaders(origin) });
    }
    if (!['GET', 'POST'].includes(request.method)) return json(405, { error: 'method not allowed' }, origin);
    if (url.pathname !== '/api/gmi-video' && url.pathname !== '/api/gmi-image' && url.pathname !== '/api/openai-prompt' && url.pathname !== '/api/gmi-upload') {
      return json(404, { error: 'not found' }, origin);
    }
    if (url.pathname === '/api/openai-prompt') {
      const openaiKey = (request.headers.get('X-OpenAI-API-Key') || '').trim();
      if (!openaiKey) return json(401, { error: '请先填写 OpenAI API Key' }, origin);
      if (openaiKey.length > 4096 || /[\r\n\0]/.test(openaiKey)) return json(400, { error: 'OpenAI API Key 格式无效' }, origin);
      try { return await analyzeVideoPrompt(request, openaiKey, origin); }
      catch (_) { return json(502, { error: 'OpenAI connection failed' }, origin); }
    }
    const personalKey = (request.headers.get('X-GMI-API-Key') || '').trim();
    let apiKey = personalKey;
    if (personalKey && (personalKey.length > 4096 || /[\r\n\0]/.test(personalKey))) {
      return json(400, { error: 'GMI API Key 格式无效' }, origin);
    }
    if (!apiKey) {
      const sitePassword = env.SITE_ACCESS_PASSWORD || '';
      if (!env.GMI_API_KEY || !sitePassword || sitePassword.length < 16) {
        return json(401, { error: '请在视频画布填写你自己的 GMI Cloud API Key' }, origin);
      }
      if (request.headers.get('X-Site-Password') !== sitePassword) {
        return json(401, { error: '需要有效的网站访问密码' }, origin);
      }
      apiKey = env.GMI_API_KEY.trim();
    }

    try {
      if (url.pathname === '/api/gmi-upload') return await uploadRequest(request, apiKey, origin);
      if (url.pathname === '/api/gmi-video') return await videoRequest(request, url, apiKey, origin);
      if (request.method === 'GET' || request.method === 'POST') return await imageRequest(request, url, apiKey, origin);
    } catch (_) {
      return json(502, { error: 'GMI Cloud connection failed' }, origin);
    }
    return json(405, { error: 'method not allowed' }, origin);
  },
};
