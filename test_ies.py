# -*- coding: utf-8 -*-
import urllib.request, urllib.parse, re

def search_bing(query):
    url = 'https://www.bing.com/search?q=' + urllib.parse.quote(query) + '&count=30&setlang=zh-CN'
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode('utf-8', errors='ignore')

queries = [
    'iesdouyin.com 健身',
    'site:iesdouyin.com 健身',
    '抖音分享 健身 视频',
]

for q in queries:
    print(f'\n=== {q} ===')
    try:
        html = search_bing(q)
        # 提取所有 iesdouyin / douyin 视频链接
        pattern = r'(https?://(?:www\.iesdouyin\.com/share/video|v\.douyin\.com|www\.douyin\.com/video|z\.douyin\.com)/[^\s"\'<>]+)'
        links = re.findall(pattern, html)
        clean = list(set(re.sub(r'&(?:amp|quot);.*$', '', l) for l in links))
        print(f'Video links: {len(clean)}')
        for l in clean[:10]:
            print(f'  {l[:100]}')
        # 提取搜索结果标题
        blocks = re.findall(r'<li class="b_algo"[\s\S]*?</li>', html)
        print(f'Result blocks: {len(blocks)}')
        for block in blocks[:5]:
            h2 = re.search(r'<h2[^>]*>[\s\S]*?<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', block)
            if h2:
                title = re.sub(r'<[^>]+>', '', h2.group(2)).strip()
                print(f'  Title: {title[:50]} | {h2.group(1)[:70]}')
    except Exception as e:
        print(f'Error: {e}')
