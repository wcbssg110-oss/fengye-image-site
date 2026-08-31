# -*- coding: utf-8 -*-
import io

path = r'C:/Users/Administrator/Doubao/chats/2026-08-31/new-chat-1/fengye-image-site/index.html'
with io.open(path, encoding='utf-8') as f:
    content = f.read()

# 简单替换
old = "rest.split('/').split('?')"
new = "rest.split('/')[0].split('?')[0]"

if old in content:
    content = content.replace(old, new)
    with io.open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Fixed')
else:
    print('Not found')
    # 检查实际内容
    idx = content.find('rest.split')
    print(repr(content[idx:idx+50]))
