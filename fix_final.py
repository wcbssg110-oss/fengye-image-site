# -*- coding: utf-8 -*-
import io, re

path = r'C:/Users/Administrator/Doubao/chats/2026-08-31/new-chat-1/fengye-image-site/index.html'
with io.open(path, encoding='utf-8') as f:
    content = f.read()

# 用正则匹配整个 dyVideoUrl 函数并替换
pattern = r'function dyVideoUrl\(url\)\{[^}]+\}'
replacement = """function dyVideoUrl(url){
    if(!url) return '#';
    var idx = url.indexOf('iesdouyin.com/share/video/');
    if(idx >= 0) {
      var rest = url.substring(idx + 28);
      var parts = rest.split('/');
      var id = parts[0].split('?')[0];
      if(id) return 'https://www.douyin.com/video/' + id;
    }
    return url;
  }"""

new_content, count = re.subn(pattern, replacement, content, count=1)
print('Replacements:', count)

if count > 0:
    with io.open(path, 'w', encoding='utf-8') as f:
        f.write(new_content)
    print('Fixed')
    # 验证
    idx = new_content.find('function dyVideoUrl')
    print('New code:', repr(new_content[idx:idx+300]))
else:
    print('Not found')
