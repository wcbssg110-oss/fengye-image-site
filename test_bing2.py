# -*- coding: utf-8 -*-
import urllib.request, urllib.parse, re, base64

url = 'https://www.bing.com/search?q=' + urllib.parse.quote('site:douyin.com 健身') + '&count=20&setlang=zh-CN'
req = urllib.request.Request(url, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9',
})
with urllib.request.urlopen(req, timeout=15) as resp:
    html = resp.read().decode('utf-8', errors='ignore')
    blocks = re.findall(r'<li class="b_algo"[\s\S]*?</li>', html)
    print('blocks:', len(blocks))
    if blocks:
        # 打印第一个块的所有链接
        block = blocks[0]
        print('=== Block 0 full ===')
        print(block[:1500])
        print()
        # 提取所有 a 标签的 href
        all_links = re.findall(r'<a[^>]*href="([^"]+)"', block)
        print('All links in block 0:')
        for l in all_links:
            print(' ', l[:120])
        # 提取标题
        titles = re.findall(r'<h2[^>]*>([\s\S]*?)</h2>', block)
        print('Titles:', [re.sub(r'<[^>]+>', '', t).strip()[:80] for t in titles])
