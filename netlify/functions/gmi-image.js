// Netlify Function: proxy Nano Banana Pro image requests to GMI Cloud.
// The shared GMI API key is read from Netlify's GMI_API_KEY environment variable.
const https = require('https');

const TARGET_HOST = 'api.gmi-serving.com';

function corsHeaders() {
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Max-Age': '86400',
  };
}

exports.handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 204, headers: corsHeaders(), body: '' };
  }
  if (event.httpMethod !== 'POST' && event.httpMethod !== 'GET') {
    return {
      statusCode: 405,
      headers: Object.assign(corsHeaders(), { 'Content-Type': 'application/json' }),
      body: JSON.stringify({ error: 'method not allowed' }),
    };
  }

  const apiKey = (process.env.GMI_API_KEY || '').trim();
  if (!apiKey) {
    return {
      statusCode: 503,
      headers: Object.assign(corsHeaders(), { 'Content-Type': 'application/json' }),
      body: JSON.stringify({ error: 'GMI_API_KEY is not configured in the site environment' }),
    };
  }

  const query = event.queryStringParameters || {};
  let path;
  let body = Buffer.alloc(0);
  const headers = { Authorization: 'Bearer ' + apiKey };
  if (event.httpMethod === 'GET') {
    const taskId = String(query.task_id || '');
    if (!/^[a-zA-Z0-9_-]{1,160}$/.test(taskId)) {
      return {
        statusCode: 400,
        headers: Object.assign(corsHeaders(), { 'Content-Type': 'application/json' }),
        body: JSON.stringify({ error: 'invalid task id' }),
      };
    }
    path = '/v1/tasks/' + encodeURIComponent(taskId);
  } else {
    const edits = query.edits === '1';
    path = edits ? '/v1/images/edits' : '/v1/images/generations';
    body = event.isBase64Encoded
      ? Buffer.from(event.body || '', 'base64')
      : Buffer.from(event.body || '', 'utf8');
    headers['Content-Type'] = event.headers['content-type'] || event.headers['Content-Type'] || 'application/json';
    headers['Content-Length'] = body.length;
  }

  return new Promise((resolve) => {
    const req = https.request({
      method: event.httpMethod,
      hostname: TARGET_HOST,
      path,
      headers,
      timeout: 180000,
    }, (resp) => {
      const chunks = [];
      resp.on('data', (chunk) => chunks.push(chunk));
      resp.on('end', () => {
        const responseBody = Buffer.concat(chunks);
        resolve({
          statusCode: resp.statusCode || 502,
          headers: Object.assign(corsHeaders(), {
            'Content-Type': resp.headers['content-type'] || 'application/json',
          }),
          body: responseBody.toString('base64'),
          isBase64Encoded: true,
        });
      });
    });
    req.on('timeout', () => req.destroy(new Error('GMI Cloud request timed out')));
    req.on('error', (error) => {
      resolve({
        statusCode: 502,
        headers: Object.assign(corsHeaders(), { 'Content-Type': 'application/json' }),
        body: JSON.stringify({ error: String(error && error.message || error) }),
      });
    });
    req.end(body);
  });
};
