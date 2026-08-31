# -*- coding: utf-8 -*-
import io, re

path = r'C:/Users/Administrator/Doubao/chats/2026-08-31/new-chat-1/fengye-image-site/index.html'
with io.open(path, encoding='utf-8') as f:
    content = f.read()

# 用正则替换
pattern = r"rest\.split\('/'\)\.split\('\?'\)"
replacement = "rest.split('/')[0].split('?')[0]"

new_content, count = re.subn(pattern, replacement, content)
print('Replacements:', count)

if count > 0:
    with io.open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('Fixed')
else:
    # 检查实际内容
    idx = content.find('rest.split')
    print('Actual:', repr(content[idx:idx+60]))
    # 检查字符编码
    for i, c in enumerate(content[idx:idx+40]):
        print(i, repr(c), ord(c))
