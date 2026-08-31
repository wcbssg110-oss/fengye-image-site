# -*- coding: utf-8 -*-
import urllib.request, urllib.parse, re

url = 'https://www.bing.com/search?q=' + urllib.parse.quote('site:douyin.com 健身') + '&count=20&setlang=zh-CN'
req = urllib.request.Request(url, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9',
})
with urllib.request.urlopen(req, timeout=15) as resp:
    html = resp.read().decode('utf-8', errors='ignore')
    print('HTML length:', len(html))
    blocks = re.findall(r'<li class="b_algo"[\s\S]*?</li>', html)
    print('b_algo blocks:', len(blocks))
    if blocks:
        print('First block sample:', blocks[0][:600])
    links = re.findall(r'href="(https?://[^"]*douyin\.com[^"]*)"', html)
    print('douyin links:', len(links))
    for l in links[:8]:
        print(' ', l)
    # 也看看有没有 h2 > a
    h2as = re.findall(r'<h2><a[^>]*href="([^"]+)"[^>]*>([\s\S]*?)</a>', html)
    print('h2 links:', len(h2as))
    for href, title in h2as[:5]:
        print(' ', href, '|', re.sub(r'<[^>]+>', '', title)[:50])
