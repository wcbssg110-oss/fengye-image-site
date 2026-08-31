# -*- coding: utf-8 -*-
import urllib.request, urllib.parse, re, json

# 测试抖音网页版搜索
keyword = '健身'
url = 'https://www.douyin.com/search/' + urllib.parse.quote(keyword) + '?type=video'
req = urllib.request.Request(url, headers={
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-CN,zh;q=0.9',
    'Referer': 'https://www.douyin.com/',
    'Cookie': '',
})
try:
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode('utf-8', errors='ignore')
    print('Douyin search HTML length:', len(html))
    # 查找视频数据（通常在 RENDER_DATA 或 __RENDER_DATA__ 中）
    render_match = re.search(r'window\._ROUTER_DATA\s*=\s*(\{[\s\S]*?\});', html)
    if render_match:
        print('Found _ROUTER_DATA, length:', len(render_match.group(1)))
        try:
            data = json.loads(render_match.group(1))
            print('Keys:', list(data.keys())[:10])
        except:
            print('Failed to parse JSON')
    else:
        print('No _ROUTER_DATA found')
    # 查找 RENDER_DATA
    render2 = re.search(r'window\.__RENDER_DATA__\s*=\s*[\'"]([^\'"]+)[\'"]', html)
    if render2:
        print('Found __RENDER_DATA__, length:', len(render2.group(1)))
    # 查找所有 aweme_id 或 video_id
    ids = re.findall(r'(?:aweme_id|video_id)["\s:]+(\d{15,25})', html)
    print('Video IDs found:', len(ids))
    for vid in list(set(ids))[:10]:
        print(f'  https://www.douyin.com/video/{vid}')
    # 查找所有 /video/ 链接
    video_links = re.findall(r'(/video/\d+)', html)
    print('Video links:', len(list(set(video_links))))
    for l in list(set(video_links))[:10]:
        print(f'  https://www.douyin.com{l}')
except Exception as e:
    print('Error:', e)
    import traceback
    traceback.print_exc()
