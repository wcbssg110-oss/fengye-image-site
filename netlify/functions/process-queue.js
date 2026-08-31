// Netlify Function: 处理搜索队列 v2，搜索抖音视频并更新网站
const https = require('https');

const GITHUB_API = 'api.github.com';
const REPO_OWNER = 'wcbssg110-oss';
const REPO_NAME = '-1';

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
    // Google 搜索（Netlify 在国外，能访问）
    try {
      const url = 'https://www.google.com/search?q=' + encodeURIComponent(q) + '&num=20&hl=zh-CN';
      const html = await httpsGet(url, 3500);
      const links = html.match(/https?:\/\/(?:www\.iesdouyin\.com\/share\/video|v\.douyin\.com|www\.douyin\.com\/video)\/[^\s"'<>]+/g) || [];
      for (const link of links) {
        const clean = link.replace(/&(?:amp|quot);.*$/, '');
        if (!seen.has(clean)) {
          seen.add(clean);
          videos.push({ url: clean, title: keyword + ' 相关视频', author: '抖音用户', publishTime: '', playNum: 10000, playText: '' });
        }
      }
    } catch (e) { /* google failed */ }

    // Bing 搜索
    if (videos.length < 5) {
      try {
        const url = 'https://www.bing.com/search?q=' + encodeURIComponent(q) + '&count=20&setlang=zh-CN';
        const html = await httpsGet(url, 3500);
        const links = html.match(/https?:\/\/(?:www\.iesdouyin\.com\/share\/video|v\.douyin\.com|www\.douyin\.com\/video)\/[^\s"'<>]+/g) || [];
        for (const link of links) {
          const clean = link.replace(/&(?:amp|quot);.*$/, '');
          if (!seen.has(clean)) {
            seen.add(clean);
            videos.push({ url: clean, title: keyword + ' 相关视频', author: '抖音用户', publishTime: '', playNum: 10000, playText: '' });
          }
        }
      } catch (e) { /* bing failed */ }
    }

    if (videos.length >= 10) break;
  }
  return videos.slice(0, 15);
}

exports.handler = async (event) => {
  const token = process.env.GITHUB_TOKEN;
  if (!token) {
    return { statusCode: 500, body: JSON.stringify({ error: 'No GITHUB_TOKEN' }) };
  }

  try {
    // 读取队列
    const qRes = await githubGet('search-queue.json', token);
    if (qRes.status !== 200) {
      return { statusCode: 200, body: JSON.stringify({ message: 'No queue file' }) };
    }
    const qData = JSON.parse(qRes.data);
    let queue = JSON.parse(Buffer.from(qData.content, 'base64').toString('utf-8'));
    const pending = queue.filter(q => q.status === 'pending');

    if (!pending.length) {
      return { statusCode: 200, body: JSON.stringify({ message: 'No pending requests' }) };
    }

    const task = pending[0];
    const keyword = task.keyword;

    // 搜索视频
    const videos = await searchVideos(keyword);

    if (!videos.length) {
      // 无结果，从队列移除
      queue = queue.filter(q => q.id !== task.id);
      await githubPut('search-queue.json', token, {
        message: '搜索无结果：' + keyword,
        content: Buffer.from(JSON.stringify(queue, null, 2)).toString('base64'),
        sha: qData.sha,
        branch: 'main',
      });
      return { statusCode: 200, body: JSON.stringify({ message: 'No videos found for ' + keyword }) };
    }

    // 构建 dyData
    const now = new Date().toISOString();
    const dyData = {
      keyword: keyword,
      sort: task.sort || 'default',
      timeRange: task.timeRange || 'all',
      duration: task.duration || 'all',
      updatedAt: now,
      videos: videos.map(v => ({
        title: v.title, author: v.author, url: v.url, cover: '',
        playText: v.playText, playNum: v.playNum,
        likeText: '', likeNum: 0, favText: '', favNum: 0,
        commentText: '', commentNum: 0,
        publishTime: v.publishTime, durationSec: 0,
      })),
    };

    // 更新 index.html
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
      sha: idxData.sha,
      branch: 'main',
    });

    // 从队列移除
    queue = queue.filter(q => q.id !== task.id);
    await githubPut('search-queue.json', token, {
      message: '处理完成：' + keyword,
      content: Buffer.from(JSON.stringify(queue, null, 2)).toString('base64'),
      sha: qData.sha,
      branch: 'main',
    });

    return {
      statusCode: 200,
      body: JSON.stringify({ ok: true, keyword, count: videos.length, message: 'Updated ' + videos.length + ' videos' }),
    };
  } catch (e) {
    return { statusCode: 500, body: JSON.stringify({ error: e.message }) };
  }
};
