# -*- coding: utf-8 -*-
import urllib.request, urllib.parse, re

def search_bing(query):
    url = 'https://www.bing.com/search?q=' + urllib.parse.quote(query) + '&count=30&setlang=zh-CN'
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
    blocks = re.findall(r'<li class="b_algo"[\s\S]*?</li>', html)
    results = []
    for block in blocks:
        h2_match = re.search(r'<h2[^>]*>[\s\S]*?<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', block)
        if h2_match:
            href = h2_match.group(1)
            title = re.sub(r'<[^>]+>', '', h2_match.group(2)).strip()
            desc_match = re.search(r'<p[^>]*>([\s\S]*?)</p>', block)
            desc = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip() if desc_match else ''
            results.append((title, href, desc))
    return results

queries = [
    'v.douyin.com 健身',
    'douyin.com/video 健身',
    '抖音视频分享 健身',
    'site:v.douyin.com 健身',
]

for q in queries:
    print(f'\n=== {q} ===')
    try:
        results = search_bing(q)
        video_links = [r for r in results if '/video/' in r[1] or 'v.douyin' in r[1] or 'z.douyin' in r[1]]
        print(f'Total: {len(results)}, Video links: {len(video_links)}')
        for title, href, desc in results[:10]:
            is_video = '/video/' in href or 'v.douyin' in href or 'z.douyin' in href
            print(f'  [{ "V" if is_video else " " }] {title[:45]} | {href[:90]}')
    except Exception as e:
        print(f'  Error: {e}')
