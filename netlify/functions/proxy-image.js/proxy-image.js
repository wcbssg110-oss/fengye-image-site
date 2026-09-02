// Netlify Function: gpt-image-2 图生图/文生图代理
// 解决浏览器跨域（CORS）限制：网页 -> 本站函数 -> api.ej2075.com（服务端到服务端）
const https = require('https');
const { URL } = require('url');

const TARGET = 'https://api.ej2075.com';

function corsHeaders() {
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST, OPTIONS',
    'Access-Control-Allow-Headers': 'Authorization, Content-Type',
    'Access-Control-Max-Age': '86400',
  };
}

exports.handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 204, headers: corsHeaders(), body: '' };
  }
  if (event.httpMethod !== 'POST') {
    return {
      statusCode: 405,
      headers: Object.assign(corsHeaders(), { 'Content-Type': 'application/json' }),
      body: JSON.stringify({ error: 'method not allowed' }),
    };
  }

  const endpoint = (event.queryStringParameters && event.queryStringParameters.edits === '0')
    ? '/v1/images/generations'
    : '/v1/images/edits';
  const targetUrl = new URL(endpoint, TARGET);
  const auth = event.headers['authorization'] || '';
  const body = event.isBase64Encoded
    ? Buffer.from(event.body || '', 'base64')
    : Buffer.from(event.body || '', 'utf8');

  return new Promise((resolve) => {
    const req = https.request(

      {
        method: 'POST',
        hostname: targetUrl.hostname,
        path: targetUrl.pathname,
        headers: {
          Authorization: auth,
          'Content-Type': event.headers['content-type'] || 'application/octet-stream',
          'Content-Length': body.length,
        },
        timeout: 180000,
      },
      (resp) => {
        const chunks = [];
        resp.on('data', (c) => chunks.push(c));
        resp.on('end', () => {
          const buf = Buffer.concat(chunks);
          resolve({
            statusCode: resp.statusCode || 502,
            headers: Object.assign(corsHeaders(), {
              'Content-Type': resp.headers['content-type'] || 'application/json',
            }),
            body: buf.toString('base64'),
            isBase64Encoded: true,
          });
        });
      }
    );
    req.on('timeout', () => req.destroy(new Error('upstream timeout')));
    req.on('error', (e) => {
      resolve({
        statusCode: 502,
        headers: Object.assign(corsHeaders(), { 'Content-Type': 'application/json' }),
        body: JSON.stringify({ error: String(e && e.message || e) }),
      });
    });
    req.end(body);
  });
};
