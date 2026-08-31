# -*- coding: utf-8 -*-
import urllib.request, urllib.parse, re

def search_ddg(query):
    url = 'https://html.duckduckgo.com/html/?q=' + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
    print(f'DDG HTML length: {len(html)}')
    # DDG 结果在 <div class="result"> 中
    results = re.findall(r'<a[^>]*class="result__a"[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', html)
    print(f'Results: {len(results)}')
    dy_links = []
    for href, title in results:
        title_clean = re.sub(r'<[^>]+>', '', title).strip()
        # DDG 链接是重定向，需要提取真实 URL
        real_url = href
        if 'uddg=' in href:
            match = re.search(r'uddg=([^&]+)', href)
            if match:
                real_url = urllib.parse.unquote(match.group(1))
        if 'douyin' in real_url.lower():
            dy_links.append((title_clean[:50], real_url[:100]))
    print(f'Douyin results: {len(dy_links)}')
    for t, u in dy_links[:10]:
        print(f'  {t} | {u}')
    # 也从整个页面提取 v.douyin 链接
    v_links = re.findall(r'(https?://v\.douyin\.com/[^\s"\'<>]+)', html)
    print(f'v.douyin links in page: {len(list(set(v_links)))}')
    for l in list(set(v_links))[:5]:
        print(f'  {l}')

queries = [
    '抖音 健身 视频',
    'v.douyin.com 健身',
    '健身 抖音 热门视频',
]
for q in queries:
    print(f'\n=== {q} ===')
    try:
        search_ddg(q)
    except Exception as e:
        print(f'Error: {e}')
