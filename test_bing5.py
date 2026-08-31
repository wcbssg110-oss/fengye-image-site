# -*- coding: utf-8 -*-
import urllib.request, urllib.parse, re, html as htmlmod

def search_bing(query):
    url = 'https://www.bing.com/search?q=' + urllib.parse.quote(query) + '&count=30&setlang=zh-CN'
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode('utf-8', errors='ignore')

# 测试不同关键词
queries = [
    '抖音 健身 视频',
    '健身 抖音 热门',
    'v.douyin.com 健身',
    '抖音健身视频大全',
]

for q in queries:
    print(f'\n=== {q} ===')
    try:
        html = search_bing(q)
        # 从整个页面提取所有抖音视频链接
        video_pattern = r'(https?://(?:v\.douyin\.com|www\.douyin\.com/video|z\.douyin\.com|www\.douyin\.com/note)/[^\s"\'<>]+)'
        links = re.findall(video_pattern, html)
        clean = list(set(re.sub(r'&(?:amp|quot|#39);.*$', '', l) for l in links))
        print(f'Video links found: {len(clean)}')
        for l in clean[:10]:
            print(f'  {l[:100]}')
        # 也看看所有 douyin 链接
        all_dy = re.findall(r'(https?://[^\s"\'<>]*douyin[^\s"\'<>]*)', html)
        all_clean = list(set(re.sub(r'&(?:amp|quot);.*$', '', l) for l in all_dy))
        print(f'All douyin links: {len(all_clean)}')
        video_like = [l for l in all_clean if any(x in l for x in ['/video/', '/note/', 'v.douyin', 'z.douyin'])]
        print(f'Video-like links: {len(video_like)}')
    except Exception as e:
        print(f'Error: {e}')
