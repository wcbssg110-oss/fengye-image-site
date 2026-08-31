# -*- coding: utf-8 -*-
import io, re

path = r'C:/Users/Administrator/Doubao/chats/2026-08-31/new-chat-1/fengye-image-site/index.html'
with io.open(path, encoding='utf-8') as f:
    content = f.read()

# 1. 在 dyEsc 函数后添加链接转换函数
old_func = "  function dyEsc(s){ return String(s == null ? '' : s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\"/g,'&quot;'); }"
new_func = old_func + """
  function dyVideoUrl(url){
    if(!url) return '#';
    // iesdouyin分享链接转抖音官网视频页
    var m = url.match(/iesdouyin\\.com\\/share\\/video\\/(\\d+)/);
    if(m) return 'https://www.douyin.com/video/' + m[1];
    return url;
  }"""
content = content.replace(old_func, new_func)

# 2. 修改视频卡片渲染：整个卡片可点击，链接转换
old_card = """      return '<article class="dy-card">' +
        '<div class="dy-cover">' +
          '<span class="dy-rank' + rankCls + '">TOP ' + (i + 1) + '</span>' + cover +
        '</div>' +
        '<div class="dy-info">' +
          '<div class="dy-title">' + dyEsc(v.title) + '</div>' +
          '<div class="dy-meta"><span class="dy-author">' + meta + '</span></div>' +
          '<div class="dy-stats">' + stats + '</div>' +
          '<div class="dy-heat"><i style="width:' + ratio + '%"></i></div>' +
        '</div>' +
        '<a class="dy-link" href="' + dyEsc(v.url) + '" target="_blank" rel="noopener">去抖音看 ›</a>' +
      '</article>';"""

new_card = """      const vurl = dyVideoUrl(v.url);
      return '<a class="dy-card" href="' + dyEsc(vurl) + '" target="_blank" rel="noopener" style="text-decoration:none;color:inherit;">' +
        '<div class="dy-cover">' +
          '<span class="dy-rank' + rankCls + '">TOP ' + (i + 1) + '</span>' + cover +
        '</div>' +
        '<div class="dy-info">' +
          '<div class="dy-title">' + dyEsc(v.title) + '</div>' +
          '<div class="dy-meta"><span class="dy-author">' + meta + '</span></div>' +
          '<div class="dy-stats">' + stats + '</div>' +
          '<div class="dy-heat"><i style="width:' + ratio + '%"></i></div>' +
        '</div>' +
        '<span class="dy-link">去抖音看 ›</span>' +
      '</a>';"""

content = content.replace(old_card, new_card)

# 3. 更新空状态提示
old_empty = "list.innerHTML = '<div class=\"dy-empty-card\">尚未获取数据。<br/>在上方输入关键词并选择筛选条件，然后把关键词和条件发给 AI（例如「帮我搜 <b>帆布鞋</b> 本周点赞最多的抖音视频」），AI 会自动把真实热门视频更新到本页。</div>';"
new_empty = "list.innerHTML = '<div class=\"dy-empty-card\">尚未获取数据。<br/>在上方输入关键词，点击「搜索」按钮，系统会自动搜索真实抖音热门视频并更新到本页（约30-60秒后自动刷新）。</div>';"
content = content.replace(old_empty, new_empty)

with io.open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Patched successfully')
