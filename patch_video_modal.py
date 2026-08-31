# -*- coding: utf-8 -*-
import io

path = r'C:/Users/Administrator/Doubao/chats/2026-08-31/new-chat-1/fengye-image-site/index.html'
with io.open(path, encoding='utf-8') as f:
    content = f.read()

# 1. 在 statsModal 后添加视频播放模态框
old_modal = """<input type="file" id="batchUploadInput" accept="image/*" multiple style="display:none" />"""

new_modal = """<!-- 抖音视频站内播放 -->
<div class="modal-mask" id="dyVideoModal" hidden onclick="if(event.target===this)closeDyVideo()">
  <div class="modal" style="width:min(420px,92vw);padding:0;overflow:hidden">
    <div class="modal-head" style="padding:10px 14px;border-bottom:1px solid var(--border)">
      <strong id="dyVideoTitle" style="font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">视频播放</strong>
      <button class="btn btn-sm" onclick="closeDyVideo()">关闭</button>
    </div>
    <div style="position:relative;width:100%;padding-top:133%;background:#000">
      <iframe id="dyVideoFrame" style="position:absolute;inset:0;width:100%;height:100%;border:0" allow="autoplay; fullscreen" allowfullscreen></iframe>
    </div>
    <div style="padding:8px 14px;font-size:11px;color:var(--text-3);text-align:center">视频由抖音提供，如无法播放请点击右上角在抖音打开</div>
  </div>
</div>

<input type="file" id="batchUploadInput" accept="image/*" multiple style="display:none" />"""

content = content.replace(old_modal, new_modal)

# 2. 修改视频卡片渲染：从 <a> 改为 <div onclick>
old_card = """      const vurl = dyVideoUrl(v.url);
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

new_card = """      const vurl = dyVideoUrl(v.url);
      return '<div class="dy-card" style="cursor:pointer" onclick=\'openDyVideo(' + JSON.stringify(vurl) + ',' + JSON.stringify(v.title || '') + ')\'>' +
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

# 3. 在 dyVideoUrl 函数后添加打开/关闭模态框函数
old_func = """  function dyVideoUrl(url){
    if(!url) return '#';
    // iesdouyin分享链接转抖音官网视频页
    var m = url.match(/iesdouyin\\.com\\/share\\/video\\/(\\d+)/);
    if(m) return 'https://www.douyin.com/video/' + m[1];
    return url;
  }"""

new_func = old_func + """
  function openDyVideo(url, title){
    var modal = document.getElementById('dyVideoModal');
    var frame = document.getElementById('dyVideoFrame');
    var titleEl = document.getElementById('dyVideoTitle');
    if(frame) frame.src = url;
    if(titleEl) titleEl.textContent = title || '视频播放';
    if(modal) modal.hidden = false;
    document.body.style.overflow = 'hidden';
  }
  function closeDyVideo(){
    var modal = document.getElementById('dyVideoModal');
    var frame = document.getElementById('dyVideoFrame');
    if(frame) frame.src = '';
    if(modal) modal.hidden = true;
    document.body.style.overflow = '';
  }"""

content = content.replace(old_func, new_func)

with io.open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print('Patched successfully')
