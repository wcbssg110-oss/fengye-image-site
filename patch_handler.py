# -*- coding: utf-8 -*-
import io

path = r'C:/Users/Administrator/Doubao/chats/2026-08-31/new-chat-1/fengye-image-site/netlify/functions/submit-search.js'
with io.open(path, encoding='utf-8') as f:
    content = f.read()

old = """  // GET 请求：返回队列状态，同时自动处理待处理项
  if (event.httpMethod === 'GET') {
    try {
      const res = await githubGet(QUEUE_PATH, token);
      if (res.status === 200) {
        const data = JSON.parse(res.data);
        const queue = JSON.parse(Buffer.from(data.content, 'base64').toString('utf-8'));
        const pending = queue.filter(q => q.status === 'pending');
        // 如果有待处理项，自动处理一个
        if (pending.length > 0) {
          try {
            const result = await processQueue(token);
            return { statusCode: 200, headers: corsHeaders(), body: JSON.stringify({ queue: [], processed: result }) };
          } catch (e) {
            return { statusCode: 200, headers: corsHeaders(), body: JSON.stringify({ queue, processError: e.message }) };
          }
        }
        return { statusCode: 200, headers: corsHeaders(), body: JSON.stringify({ queue }) };
      }
      return { statusCode: 200, headers: corsHeaders(), body: JSON.stringify({ queue: [] }) };
    } catch (e) {
      return { statusCode: 200, headers: corsHeaders(), body: JSON.stringify({ queue: [] }) };
    }
  }

  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, headers: corsHeaders(), body: JSON.stringify({ error: 'Method Not Allowed' }) };
  }

  let body;
  try {
    body = JSON.parse(event.body || '{}');
  } catch (e) {
    return { statusCode: 400, headers: corsHeaders(), body: JSON.stringify({ error: '无效的请求体' }) };
  }

  if (!body.keyword || !body.keyword.trim()) {
    return { statusCode: 400, headers: corsHeaders(), body: JSON.stringify({ error: '请输入关键词' }) };
  }"""

new = """  // GET 请求：只返回队列状态
  if (event.httpMethod === 'GET') {
    try {
      const res = await githubGet(QUEUE_PATH, token);
      if (res.status === 200) {
        const data = JSON.parse(res.data);
        const queue = JSON.parse(Buffer.from(data.content, 'base64').toString('utf-8'));
        return { statusCode: 200, headers: corsHeaders(), body: JSON.stringify({ queue }) };
      }
      return { statusCode: 200, headers: corsHeaders(), body: JSON.stringify({ queue: [] }) };
    } catch (e) {
      return { statusCode: 200, headers: corsHeaders(), body: JSON.stringify({ queue: [] }) };
    }
  }

  if (event.httpMethod !== 'POST') {
    return { statusCode: 405, headers: corsHeaders(), body: JSON.stringify({ error: 'Method Not Allowed' }) };
  }

  let body;
  try {
    body = JSON.parse(event.body || '{}');
  } catch (e) {
    return { statusCode: 400, headers: corsHeaders(), body: JSON.stringify({ error: '无效的请求体' }) };
  }

  // POST {"action":"process"} 触发队列处理
  if (body.action === 'process') {
    try {
      const result = await processQueue(token);
      return { statusCode: 200, headers: corsHeaders(), body: JSON.stringify(result) };
    } catch (e) {
      return { statusCode: 500, headers: corsHeaders(), body: JSON.stringify({ error: e.message }) };
    }
  }

  if (!body.keyword || !body.keyword.trim()) {
    return { statusCode: 400, headers: corsHeaders(), body: JSON.stringify({ error: '请输入关键词' }) };
  }"""

if old in content:
    content = content.replace(old, new)
    with io.open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Replaced successfully')
else:
    print('Old string not found')
