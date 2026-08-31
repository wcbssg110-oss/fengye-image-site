# -*- coding: utf-8 -*-
import urllib.request, urllib.parse, re

def search_bing(query):
    url = 'https://www.bing.com/search?q=' + urllib.parse.quote(query) + '&count=20&setlang=zh-CN'
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
    # 提取所有结果
    blocks = re.findall(r'<li class="b_algo"[\s\S]*?</li>', html)
    results = []
    for block in blocks:
        # 提取 h2 中的链接和标题
        h2_match = re.search(r'<h2[^>]*>[\s\S]*?<a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', block)
        if h2_match:
            href = h2_match.group(1)
            title = re.sub(r'<[^>]+>', '', h2_match.group(2)).strip()
            # 提取摘要
            desc_match = re.search(r'<p[^>]*>([\s\S]*?)</p>', block)
            desc = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip() if desc_match else ''
            results.append((title, href, desc))
    return results

queries = [
    '抖音 健身 热门视频',
    'douyin.com 健身',
    '抖音健身视频点赞最多',
]

for q in queries:
    print(f'\n=== Query: {q} ===')
    try:
        results = search_bing(q)
        print(f'Results: {len(results)}')
        douyin_count = 0
        for title, href, desc in results[:8]:
            is_douyin = 'douyin' in href.lower()
            if is_douyin: douyin_count += 1
            print(f'  [{ "DY" if is_douyin else "  " }] {title[:50]} | {href[:80]}')
        print(f'  Douyin links: {douyin_count}')
    except Exception as e:
        print(f'  Error: {e}')
