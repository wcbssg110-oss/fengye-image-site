// Netlify Function: 接收搜索请求 + 自动处理队列 v3
const https = require('https');

const GITHUB_API = 'api.github.com';
const REPO_OWNER = 'wcbssg110-oss';
const REPO_NAME = '-1';
const QUEUE_PATH = 'search-queue.json';

function corsHeaders() {
  return {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Headers': 'Content-Type',
    'Access-Control-Allow-Methods': 'POST, GET, OPTIONS',
    'Content-Type': 'application/json',
  };
}

function httpsGet(url, timeoutMs) {
  return new Promise((resolve, reject) => {
    const req = https.get(url, {
      headers: {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'zh-CN,zh;q=0.9',
      },
      timeout: timeoutMs,
    }, (res) => {
      let chunks = '';
      res.on('data', (c) => (chunks += c));
      res.on('end', () => resolve(chunks));
    });
    req.on('error', reject);
    req.on('timeout', () => { req.destroy(); reject(new Error('timeout')); });
  });
}

function httpsRequest(options, body) {
  return new Promise((resolve, reject) => {
    const data = body ? JSON.stringify(body) : null;
    const opts = { ...options };
    if (data) {
      opts.headers = opts.headers || {};
      opts.headers['Content-Type'] = 'application/json';
      opts.headers['Content-Length'] = Buffer.byteLength(data);
    }
    const req = https.request(opts, (res) => {
      let chunks = '';
      res.on('data', (c) => (chunks += c));
      res.on('end', () => resolve({ status: res.statusCode, data: chunks }));
    });
    req.on('error', reject);
    if (data) req.write(data);
    req.end();
  });
}

function githubGet(path, token) {
  return httpsRequest({
    hostname: GITHUB_API,
    path: `/repos/${REPO_OWNER}/${REPO_NAME}/contents/${path}`,
    method: 'GET',
    headers: { 'Authorization': 'token ' + token, 'User-Agent': 'fengye-image', 'Accept': 'application/vnd.github.v3+json' },
  });
}

function githubPut(path, token, body) {
  return httpsRequest({
    hostname: GITHUB_API,
    path: `/repos/${REPO_OWNER}/${REPO_NAME}/contents/${path}`,
    method: 'PUT',
    headers: { 'Authorization': 'token ' + token, 'User-Agent': 'fengye-image', 'Accept': 'application/vnd.github.v3+json' },
  }, body);
}

async function searchVideos(keyword) {
  const videos = [];
  const seen = new Set();
  const queries = [
    '抖音 ' + keyword + ' 视频 iesdouyin.com',
    keyword + ' 抖音 热门视频',
  ];
  for (const q of queries) {
    try {
      const url = 'https://www.google.com/search?q=' + encodeURIComponent(q) + '&num=20&hl=zh-CN';
      const html = await httpsGet(url, 2000);
      const links = html.match(/https?:\/\/(?:www\.iesdouyin\.com\/share\/video|v\.douyin\.com|www\.douyin\.com\/video)\/[^\s"'<>]+/g) || [];
      for (const link of links) {
        const clean = link.replace(/&(?:amp|quot);.*$/, '');
        if (!seen.has(clean)) {
          seen.add(clean);
          videos.push({ url: clean, title: keyword + ' 相关视频', author: '抖音用户', publishTime: '', playNum: 10000, playText: '' });
        }
      }
    } catch (e) {}
    if (videos.length < 5) {
      try {
        const url = 'https://www.bing.com/search?q=' + encodeURIComponent(q) + '&count=20&setlang=zh-CN';
        const html = await httpsGet(url, 2000);
        const links = html.match(/https?:\/\/(?:www\.iesdouyin\.com\/share\/video|v\.douyin\.com|www\.douyin\.com\/video)\/[^\s"'<>]+/g) || [];
        for (const link of links) {
          const clean = link.replace(/&(?:amp|quot);.*$/, '');
          if (!seen.has(clean)) {
            seen.add(clean);
            videos.push({ url: clean, title: keyword + ' 相关视频', author: '抖音用户', publishTime: '', playNum: 10000, playText: '' });
          }
        }
      } catch (e) {}
    }
    if (videos.length >= 10) break;
  }
  return videos.slice(0, 15);
}

async function processQueue(token) {
  const qRes = await githubGet(QUEUE_PATH, token);
  if (qRes.status !== 200) return { message: 'No queue file' };
  const qData = JSON.parse(qRes.data);
  let queue = JSON.parse(Buffer.from(qData.content, 'base64').toString('utf-8'));
  const pending = queue.filter(q => q.status === 'pending');
  if (!pending.length) return { message: 'No pending requests' };

  const task = pending[0];
  const keyword = task.keyword;
  const videos = await searchVideos(keyword);

  if (!videos.length) {
    queue = queue.filter(q => q.id !== task.id);
    await githubPut(QUEUE_PATH, token, {
      message: '搜索无结果：' + keyword,
      content: Buffer.from(JSON.stringify(queue, null, 2)).toString('base64'),
      sha: qData.sha, branch: 'main',
    });
    return { message: 'No videos found for ' + keyword };
  }

  const dyData = {
    keyword: keyword,
    sort: task.sort || 'default',
    timeRange: task.timeRange || 'all',
    duration: task.duration || 'all',
    updatedAt: new Date().toISOString(),
    videos: videos.map(v => ({
      title: v.title, author: v.author, url: v.url, cover: '',
      playText: v.playText, playNum: v.playNum,
      likeText: '', likeNum: 0, favText: '', favNum: 0,
      commentText: '', commentNum: 0,
      publishTime: v.publishTime, durationSec: 0,
    })),
  };

  const idxRes = await githubGet('index.html', token);
  const idxData = JSON.parse(idxRes.data);
  let html = Buffer.from(idxData.content, 'base64').toString('utf-8');
  const newDy = '  let dyData = ' + JSON.stringify(dyData, null, 4) + ';';
  const pattern = /  let dyData = \{[\s\S]*?\n  \};/;
  if (pattern.test(html)) {
    html = html.replace(pattern, newDy);
  } else {
    const broad = /let dyData = \{[\s\S]*?\};/;
    const m = html.match(broad);
    if (m) html = html.slice(0, m.index) + newDy + html.slice(m.index + m[0].length);
  }

  await githubPut('index.html', token, {
    message: '抖音热榜更新：' + keyword + ' (' + videos.length + '条)',
    content: Buffer.from(html).toString('base64'),
    sha: idxData.sha, branch: 'main',
  });

  queue = queue.filter(q => q.id !== task.id);
  await githubPut(QUEUE_PATH, token, {
    message: '处理完成：' + keyword,
    content: Buffer.from(JSON.stringify(queue, null, 2)).toString('base64'),
    sha: qData.sha, branch: 'main',
  });

  return { ok: true, keyword, count: videos.length };
}

exports.handler = async (event) => {
  if (event.httpMethod === 'OPTIONS') {
    return { statusCode: 200, headers: corsHeaders(), body: '' };
  }

  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    return { statusCode: 500, headers: corsHeaders(), body: JSON.stringify({ error: '未配置 GITHUB_TOKEN' }) };
  }

  // GET 请求：只返回队列状态
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
  }

  const keyword = body.keyword.trim();
  const sort = body.sort || 'default';
  const timeRange = body.timeRange || 'all';
  const duration = body.duration || 'all';

  try {
    const getRes = await githubGet(QUEUE_PATH, token);
    let queue = [];
    let sha = null;
    if (getRes.status === 200) {
      const data = JSON.parse(getRes.data);
      sha = data.sha;
      try { queue = JSON.parse(Buffer.from(data.content, 'base64').toString('utf-8')); } catch (e) { queue = []; }
    }

    const now = Date.now();
    const existing = queue.find(q => q.keyword === keyword && now - q.createdAt < 5 * 60 * 1000);
    if (existing) {
      return { statusCode: 200, headers: corsHeaders(), body: JSON.stringify({ ok: true, queued: false, message: '该关键词正在搜索中，请稍候' }) };
    }

    queue.push({
      id: now + '-' + Math.random().toString(36).substr(2, 6),
      keyword, sort, timeRange, duration,
      createdAt: now, status: 'pending',
    });
    queue = queue.slice(-20);

    await githubPut(QUEUE_PATH, token, {
      message: '搜索请求：' + keyword,
      content: Buffer.from(JSON.stringify(queue, null, 2)).toString('base64'),
      sha: sha, branch: 'main',
    });

    return {
      statusCode: 200,
      headers: corsHeaders(),
      body: JSON.stringify({ ok: true, queued: true, message: '搜索请求已提交，正在处理中，约30-60秒后自动刷新' }),
    };
  } catch (e) {
    return { statusCode: 500, headers: corsHeaders(), body: JSON.stringify({ error: e.message }) };
  }
};
