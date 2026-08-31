# -*- coding: utf-8 -*-
import io

path = r'C:/Users/Administrator/Doubao/chats/2026-08-31/new-chat-1/fengye-image-site/index.html'
with io.open(path, encoding='utf-8') as f:
    content = f.read()

# 查找并修复 dyVideoUrl 函数
old = """  function dyVideoUrl(url){
    if(!url) return '#';
    var idx = url.indexOf('iesdouyin.com/share/video/');
    if(idx >= 0) {
      var rest = url.substring(idx + 28);
      var id = rest.split('/').split('?');
      if(id) return 'https://www.douyin.com/video/' + id;
    }
    return url;
  }"""

new = """  function dyVideoUrl(url){
    if(!url) return '#';
    var idx = url.indexOf('iesdouyin.com/share/video/');
    if(idx >= 0) {
      var rest = url.substring(idx + 28);
      var id = rest.split('/')[0].split('?')[0];
      if(id) return 'https://www.douyin.com/video/' + id;
    }
    return url;
  }"""

if old in content:
    content = content.replace(old, new)
    with io.open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Fixed')
else:
    print('Old not found, searching...')
    idx = content.find('function dyVideoUrl')
    print(repr(content[idx:idx+300]))
