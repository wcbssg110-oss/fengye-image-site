# -*- coding: utf-8 -*-
import urllib.request, urllib.parse, re

def search_baidu(query):
    url = 'https://www.baidu.com/s?wd=' + urllib.parse.quote(query) + '&rn=20'
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'zh-CN,zh;q=0.9',
        'Cookie': 'BAIDUID=test123',
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
    print('Baidu HTML length:', len(html))
    # 百度搜索结果通常在 <div class="result"> 或 <h3 class="t"> 中
    blocks = re.findall(r'<div[^>]*class="[^"]*result[^"]*"[\s\S]*?</div>\s*</div>', html)
    if not blocks:
        blocks = re.findall(r'<h3[^>]*class="t"[\s\S]*?</h3>', html)
    print('Result blocks:', len(blocks))
    # 提取所有 douyin 链接
    dy_links = re.findall(r'(https?://[^\s"\'<>]*douyin[^\s"\'<>]*)', html)
    print('Douyin links:', len(dy_links))
    for l in list(set(dy_links))[:15]:
        print(' ', l[:100])
    # 提取所有视频链接
    video_links = re.findall(r'(https?://[^\s"\'<>]*(?:douyin\.com/video|v\.douyin|z\.douyin)[^\s"\'<>]*)', html)
    print('Video links:', len(video_links))
    for l in list(set(video_links))[:10]:
        print(' ', l[:100])
    return html

print('=== 百度搜索: 抖音 健身 视频 ===')
try:
    html = search_baidu('抖音 健身 视频')
except Exception as e:
    print('Error:', e)

print('\n=== 百度搜索: douyin.com 健身 ===')
try:
    search_baidu('douyin.com 健身')
except Exception as e:
    print('Error:', e)
