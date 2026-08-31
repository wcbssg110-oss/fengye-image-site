# -*- coding: utf-8 -*-
"""GitHub Actions 定时任务：检查搜索队列，搜索抖音视频，更新网站"""
import base64, json, urllib.request, urllib.parse, re, os, sys
from datetime import datetime, timezone, timedelta

TOKEN = os.environ.get('GITHUB_TOKEN', '')
OWNER = 'wcbssg110-oss'
REPO = '-1'

def github_api(path, method='GET', body=None):
    url = f'https://api.github.com/repos/{OWNER}/{REPO}/contents/{path}'
    data = json.dumps(body).encode('utf-8') if body else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header('Authorization', 'token ' + TOKEN)
    req.add_header('User-Agent', 'fengye-image')
    req.add_header('Accept', 'application/vnd.github.v3+json')
    if data:
        req.add_header('Content-Type', 'application/json')
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode('utf-8'))

def http_get(url, timeout=10):
    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    })
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode('utf-8', errors='ignore')

def search_videos(keyword):
    """用多个搜索引擎搜索抖音视频"""
    videos = []
    seen = set()

    search_queries = [
        f'抖音 {keyword} 视频 iesdouyin.com',
        f'{keyword} 抖音 热门视频',
        f'site:iesdouyin.com {keyword}',
    ]

    for q in search_queries:
        # Bing 搜索
        try:
            url = 'https://www.bing.com/search?q=' + urllib.parse.quote(q) + '&count=20&setlang=zh-CN'
            html = http_get(url, 8)
            # 提取所有 iesdouyin / douyin video 链接
            links = re.findall(r'(https?://(?:www\.iesdouyin\.com/share/video|v\.douyin\.com|www\.douyin\.com/video)/[^\s"\'<>]+)', html)
            for link in links:
                link = re.sub(r'&(?:amp|quot);.*$', '', link)
                if link not in seen:
                    seen.add(link)
                    videos.append({'url': link, 'title': keyword + ' 相关视频', 'author': '抖音用户', 'publishTime': '', 'playNum': 0, 'playText': ''})
        except Exception as e:
            print(f'Bing search failed: {e}', file=sys.stderr)

        # Google 搜索（GitHub Actions 在国外，能访问 Google）
        try:
            url = 'https://www.google.com/search?q=' + urllib.parse.quote(q) + '&num=20&hl=zh-CN'
            html = http_get(url, 8)
            links = re.findall(r'(https?://(?:www\.iesdouyin\.com/share/video|v\.douyin\.com|www\.douyin\.com/video)/[^\s"\'<>]+)', html)
            for link in links:
                link = re.sub(r'&(?:amp|quot);.*$', '', link)
                if link not in seen:
                    seen.add(link)
                    videos.append({'url': link, 'title': keyword + ' 相关视频', 'author': '抖音用户', 'publishTime': '', 'playNum': 0, 'playText': ''})
        except Exception as e:
            print(f'Google search failed: {e}', file=sys.stderr)

        if len(videos) >= 10:
            break

    return videos[:15]

def main():
    if not TOKEN:
        print('No GITHUB_TOKEN')
        return

    # 读取队列
    try:
        qdata = github_api('search-queue.json')
        queue = json.loads(base64.b64decode(qdata['content']).decode('utf-8'))
    except Exception as e:
        print(f'Queue read failed: {e}')
        return

    pending = [q for q in queue if q.get('status') == 'pending']
    if not pending:
        print('No pending requests')
        return

    # 只处理第一个
    task = pending[0]
    keyword = task['keyword']
    print(f'Processing: {keyword}')

    # 搜索视频
    videos = search_videos(keyword)
    print(f'Found {len(videos)} videos')

    if not videos:
        print('No videos found, removing from queue')
        queue = [q for q in queue if q.get('id') != task['id']]
        github_api('search-queue.json', 'PUT', {
            'message': f'搜索无结果：{keyword}',
            'content': base64.b64encode(json.dumps(queue, ensure_ascii=False, indent=2).encode('utf-8')).decode('ascii'),
            'sha': qdata['sha'],
            'branch': 'main',
        })
        return

    # 构建 dyData
    tz = timezone(timedelta(hours=8))
    dy_data = {
        'keyword': keyword,
        'sort': task.get('sort', 'default'),
        'timeRange': task.get('timeRange', 'all'),
        'duration': task.get('duration', 'all'),
        'updatedAt': datetime.now(tz).isoformat(),
        'videos': [{
            'title': v.get('title', keyword + ' 视频'),
            'author': v.get('author', '抖音用户'),
            'url': v['url'],
            'cover': '',
            'playText': v.get('playText', ''),
            'playNum': v.get('playNum', 0),
            'likeText': '', 'likeNum': 0,
            'favText': '', 'favNum': 0,
            'commentText': '', 'commentNum': 0,
            'publishTime': v.get('publishTime', ''),
            'durationSec': 0,
        } for v in videos],
    }

    # 更新 index.html
    idx = github_api('index.html')
    html = base64.b64decode(idx['content']).decode('utf-8')
    new_dy = '  let dyData = ' + json.dumps(dy_data, ensure_ascii=False, indent=4) + ';'
    pattern = r'  let dyData = \{[\s\S]*?\n  \};'
    if re.search(pattern, html):
        html_new = re.sub(pattern, new_dy, html, count=1)
    else:
        pattern2 = r'let dyData = \{[\s\S]*?\};'
        m = re.search(pattern2, html)
        if m:
            html_new = html[:m.start()] + new_dy + html[m.end():]
        else:
            print('dyData not found in index.html')
            return

    github_api('index.html', 'PUT', {
        'message': f'抖音热榜更新：{keyword} ({len(videos)}条)',
        'content': base64.b64encode(html_new.encode('utf-8')).decode('ascii'),
        'sha': idx['sha'],
        'branch': 'main',
    })

    # 从队列移除
    queue = [q for q in queue if q.get('id') != task['id']]
    github_api('search-queue.json', 'PUT', {
        'message': f'处理完成：{keyword}',
        'content': base64.b64encode(json.dumps(queue, ensure_ascii=False, indent=2).encode('utf-8')).decode('ascii'),
        'sha': qdata['sha'],
        'branch': 'main',
    })

    print(f'Done: {keyword}, {len(videos)} videos updated')

if __name__ == '__main__':
    main()
