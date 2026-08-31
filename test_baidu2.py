# -*- coding: utf-8 -*-
import urllib.request, urllib.parse, re, html as htmlmod

def search_baidu(query):
    url = 'https://www.baidu.com/s?wd=' + urllib.parse.quote(query) + '&rn=30'
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    })
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode('utf-8', errors='ignore')

html = search_baidu('抖音 健身 热门视频')
print('HTML length:', len(html))

# 百度结果块：<div class="result c-container ">
blocks = re.findall(r'<div[^>]*class="[^"]*result[^"]*"[^>]*>([\s\S]*?)</div>\s*</div>', html)
print('Result blocks:', len(blocks))

# 尝试另一种匹配
if not blocks:
    blocks = re.findall(r'<h3[^>]*class="t"[^>]*>([\s\S]*?)</h3>', html)
    print('h3 blocks:', len(blocks))

# 提取每个结果的标题和所有 douyin 链接
results = []
# 匹配 result 块
result_pattern = re.compile(r'<div[^>]*class="[^"]*c-container[^"]*"[^>]*>([\s\S]*?)(?=<div[^>]*class="[^"]*c-container|$)', re.MULTILINE)
for m in result_pattern.finditer(html):
    block = m.group(1)
    # 标题
    title_match = re.search(r'<h3[^>]*>[\s\S]*?<a[^>]*>([\s\S]*?)</a>', block)
    title = htmlmod.unescape(re.sub(r'<[^>]+>', '', title_match.group(1))).strip() if title_match else ''
    # 摘要
    desc_match = re.search(r'<span[^>]*class="[^"]*content-right[^"]*"[^>]*>([\s\S]*?)</span>', block)
    if not desc_match:
        desc_match = re.search(r'<div[^>]*class="[^"]*c-abstract[^"]*"[^>]*>([\s\S]*?)</div>', block)
    desc = htmlmod.unescape(re.sub(r'<[^>]+>', '', desc_match.group(1))).strip() if desc_match else ''
    # 块中所有 douyin 链接
    dy_links = re.findall(r'(https?://[^\s"\'<>]*?(?:v\.douyin\.com|douyin\.com/video|douyin\.com/note|z\.douyin\.com)[^\s"\'<>]*)', block)
    # 清理链接（去掉 &quot; 等后缀）
    clean_links = []
    for l in dy_links:
        l = re.sub(r'&quot;.*$', '', l)
        l = re.sub(r'&amp;.*$', '', l)
        if l not in clean_links:
            clean_links.append(l)
    if clean_links:
        results.append({'title': title, 'links': clean_links, 'desc': desc[:100]})

print(f'\nResults with douyin video links: {len(results)}')
for i, r in enumerate(results[:10]):
    print(f'\n[{i+1}] {r["title"][:60]}')
    print(f'    Links: {r["links"]}')
    print(f'    Desc: {r["desc"][:80]}')
