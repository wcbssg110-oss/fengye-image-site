# -*- coding: utf-8 -*-
import urllib.request, urllib.parse, re, html as htmlmod

def search_google(query):
    url = 'https://www.google.com/search?q=' + urllib.parse.quote(query) + '&num=20&hl=zh-CN'
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        'Accept': 'text/html,application/xhtml+xml',
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
    print('Google HTML length:', len(html))
    # Google 结果在 <div class="g"> 中
    blocks = re.findall(r'<div class="g"[\s\S]*?</div>\s*</div>', html)
    print('Google result blocks:', len(blocks))
    # 提取所有 douyin 链接
    dy_links = re.findall(r'(https?://[^\s"\'<>]*?(?:v\.douyin\.com|douyin\.com/video|douyin\.com/note|z\.douyin\.com|www\.douyin\.com)[^\s"\'<>]*)', html)
    clean = list(set(re.sub(r'&amp;.*$', '', l) for l in dy_links))
    print('Douyin links:', len(clean))
    for l in clean[:15]:
        print(' ', l[:100])
    # 提取标题和链接
    results = []
    for m in re.finditer(r'<div class="g"[\s\S]*?<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', html):
        href = m.group(1)
        title = htmlmod.unescape(re.sub(r'<[^>]+>', '', m.group(2))).strip()
        if 'douyin' in href.lower() or '抖音' in title:
            results.append((title[:60], href[:100]))
    print(f'\nRelevant results: {len(results)}')
    for t, h in results[:10]:
        print(f'  {t} | {h}')
    return html

print('=== Google: 抖音 健身 视频 ===')
try:
    search_google('抖音 健身 视频')
except Exception as e:
    print('Error:', e)

print('\n=== Google: site:douyin.com 健身 ===')
try:
    search_google('site:douyin.com 健身')
except Exception as e:
    print('Error:', e)
