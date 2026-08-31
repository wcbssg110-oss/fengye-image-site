# -*- coding: utf-8 -*-
import io, re
p = r'C:/Users/Administrator/Doubao/chats/2026-08-31/new-chat-1/fengye-image-site/index.html'
data = io.open(p, encoding='utf-8').read()
scripts = re.findall(r'<script>(.*?)</script>', data, re.S)
io.open(r'C:/Users/Administrator/Doubao/chats/2026-08-31/new-chat-1/fengye-image-site/_check.js', 'w', encoding='utf-8').write('\n;\n'.join(scripts))
keys = ['id="dy-sort"', 'id="dy-time"', 'id="dy-duration"',
        'data-sort="likes"', 'data-time="week"',
        'function dySearch', 'function dySortVideos', 'function dyInTimeRange',
        'id="douyin-panel"', 'data-panel="douyin"']
for k in keys:
    print(k, '->', data.count(k))
