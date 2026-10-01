const {buildVideo}=require('../../video-contract.cjs');
// Netlify Function: server-side proxy for GMI Cloud video generation.
// The shared credential is read only from the GMI_API_KEY environment variable.
const https = require('https');

const HOST = 'console.gmicloud.ai';
const QUEUE_PATH = '/api/v1/ie/requestqueue/apikey/requests';
const ALLOWED_MODELS = new Set([
  'seedance-2-5-260628',
  'kling-3.0-turbo-t2v',
  'kling-3.0-turbo-i2v',
  'wan2.7-t2v',
  'wan2.7-i2v'
]);

function json(statusCode, value) {
  return {
    statusCode,
    headers: { 'Content-Type': 'application/json; charset=utf-8', 'Cache-Control': 'no-store' },
    body: JSON.stringify(value)
  };
}

function requestGmi(method, path, apiKey, payload) {
  return new Promise((resolve) => {
    const body = payload == null ? Buffer.alloc(0) : Buffer.from(JSON.stringify(payload), 'utf8');
    const headers = { Authorization: 'Bearer ' + apiKey, Accept: 'application/json' };
    if (payload != null) {
      headers['Content-Type'] = 'application/json';
      headers['Content-Length'] = body.length;
    }
    const req = https.request({ method, hostname: HOST, path, headers, timeout: 30000 }, (resp) => {
      const chunks = [];
      resp.on('data', (chunk) => chunks.push(chunk));
      resp.on('end', () => {
        const raw = Buffer.concat(chunks).toString('utf8');
        let data;
        try { data = JSON.parse(raw); } catch (_) { data = { error: raw.slice(0, 1200) || 'Invalid response from GMI Cloud' }; }
        resolve({ statusCode: resp.statusCode || 502, data });
      });
    });
    req.on('timeout', () => req.destroy(new Error('GMI Cloud request timed out')));
    req.on('error', (error) => resolve({ statusCode: 502, data: { error: String(error && error.message || error) } }));
    req.end(body);
  });
}

function validPublicImageUrl(value) {
  if (typeof value !== 'string' || value.length > 2048) return false;
  try {
    const url = new URL(value);
    return url.protocol === 'https:' && Boolean(url.hostname) && !url.username && !url.password;
  } catch (_) { return false; }
}

exports.handler = async (event) => {
  if (event.httpMethod !== 'GET' && event.httpMethod !== 'POST') return json(405, { error: 'method not allowed' });

  const apiKey = (process.env.GMI_API_KEY || '').trim();
  if (!apiKey) return json(503, { error: 'GMI_API_KEY is not configured in the site environment' });

  if (event.httpMethod === 'GET') {
    const taskId = String((event.queryStringParameters || {}).task_id || '');
    if (!/^[A-Za-z0-9_-]{1,160}$/.test(taskId)) return json(400, { error: 'invalid task id' });
    const result = await requestGmi('GET', QUEUE_PATH + '/' + encodeURIComponent(taskId), apiKey);
    return json(result.statusCode, result.data);
  }

  let incoming;
  try {
    const raw = event.isBase64Encoded ? Buffer.from(event.body || '', 'base64').toString('utf8') : (event.body || '');
    incoming = JSON.parse(raw);
  } catch (_) { return json(400, { error: 'request body must be valid JSON' }); }
  if (!incoming || typeof incoming !== 'object' || Array.isArray(incoming)) return json(400, { error: 'request body must be a JSON object' });

  let model,payload;
  try {({model,payload}=buildVideo(incoming));}catch(e){return json(400,{error:e.message});}
  const result = await requestGmi('POST', QUEUE_PATH, apiKey, { model, payload });
  return json(result.statusCode, result.data);
};
