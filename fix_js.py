# -*- coding: utf-8 -*-
import io

path = r'C:/Users/Administrator/Doubao/chats/2026-08-31/new-chat-1/fengye-image-site/index.html'
with io.open(path, encoding='utf-8') as f:
    content = f.read()

# 1. 修复视频卡片渲染：用 data 属性代替内联 onclick
old_card = """      const vurl = dyVideoUrl(v.url);
      return '<div class="dy-card" style="cursor:pointer" onclick='openDyVideo(' + JSON.stringify(vurl) + ',' + JSON.stringify(v.title || '') + ')'>' +
        '<div class="dy-cover">' +
          '<span class="dy-rank' + rankCls + '">TOP ' + (i + 1) + '</span>' + cover +
        '</div>' +
        '<div class="dy-info">' +
          '<div class="dy-title">' + dyEsc(v.title) + '</div>' +
          '<div class="dy-meta"><span class="dy-author">' + meta + '</span></div>' +
          '<div class="dy-stats">' + stats + '</div>' +
          '<div class="dy-heat"><i style="width:' + ratio + '%"></i></div>' +
        '</div>' +
        '<span class="dy-link">▶ 站内播放</span>' +
      '</div>';"""

new_card = """      const vurl = dyVideoUrl(v.url);
      return '<div class="dy-card" style="cursor:pointer" data-url="' + dyEsc(vurl) + '" data-title="' + dyEsc(v.title || '') + '">' +
        '<div class="dy-cover">' +
          '<span class="dy-rank' + rankCls + '">TOP ' + (i + 1) + '</span>' + cover +
        '</div>' +
        '<div class="dy-info">' +
          '<div class="dy-title">' + dyEsc(v.title) + '</div>' +
          '<div class="dy-meta"><span class="dy-author">' + meta + '</span></div>' +
          '<div class="dy-stats">' + stats + '</div>' +
          '<div class="dy-heat"><i style="width:' + ratio + '%"></i></div>' +
        '</div>' +
        '<span class="dy-link">▶ 站内播放</span>' +
      '</div>';"""

content = content.replace(old_card, new_card)

# 2. 在 document click 事件中添加 .dy-card 的点击处理
old_click = """  document.addEventListener('click', function(e){
    const p = e.target.closest ? e.target.closest('#dy-sort .pill') : null;
    if (p) { dyData.sort = p.dataset.sort; dyUpdateHash(); renderDy(); dyShowRequest(); return; }
    const t = e.target.closest ? e.target.closest('#dy-time .pill') : null;
    if (t) { dyData.timeRange = t.dataset.time; dyUpdateHash(); renderDy(); dyShowRequest(); return; }
    const d = e.target.closest ? e.target.closest('#dy-duration .pill') : null;
    if (d) { dyData.duration = d.dataset.duration; dyUpdateHash(); renderDy(); dyShowRequest(); return; }
  });"""

new_click = """  document.addEventListener('click', function(e){
    const p = e.target.closest ? e.target.closest('#dy-sort .pill') : null;
    if (p) { dyData.sort = p.dataset.sort; dyUpdateHash(); renderDy(); dyShowRequest(); return; }
    const t = e.target.closest ? e.target.closest('#dy-time .pill') : null;
    if (t) { dyData.timeRange = t.dataset.time; dyUpdateHash(); renderDy(); dyShowRequest(); return; }
    const d = e.target.closest ? e.target.closest('#dy-duration .pill') : null;
    if (d) { dyData.duration = d.dataset.duration; dyUpdateHash(); renderDy(); dyShowRequest(); return; }
    const card = e.target.closest ? e.target.closest('.dy-card') : null;
    if (card && card.dataset.url) { openDyVideo(card.dataset.url, card.dataset.title); return; }
  });"""

content = content.replace(old_click, new_click)

with io.open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Fixed successfully')
