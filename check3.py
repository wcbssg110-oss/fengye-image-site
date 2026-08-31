# -*- coding: utf-8 -*-
import io, re
p = r'C:/Users/Administrator/Doubao/chats/2026-08-31/new-chat-1/fengye-image-site/index.html'
data = io.open(p, encoding='utf-8').read()
scripts = re.findall(r'<script>(.*?)</script>', data, re.S)
io.open(r'C:/Users/Administrator/Doubao/chats/2026-08-31/new-chat-1/fengye-image-site/_check.js', 'w', encoding='utf-8').write('\n;\n'.join(scripts))
keys = ['dy-request', 'dyCopyRequest', 'dyCopyLink', 'dyFromHash', 'dyUpdateHash',
        'dyBuildRequestText', 'dyShowRequest', '一键复制搜索条件', '复制页面链接',
        '#douyin?', 'dyFromHash();']
for k in keys:
    print(k, '->', data.count(k))
