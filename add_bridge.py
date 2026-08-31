# -*- coding: utf-8 -*-
"""给抖音热榜加搜索条件桥接：一键复制 + URL hash 同步"""
import io

p = r'C:/Users/Administrator/Doubao/chats/2026-08-31/new-chat-1/fengye-image-site/index.html'
data = io.open(p, encoding='utf-8').read()

# ========== 1) CSS：加 dy-request 样式 ==========
css_anchor = '  .dy-stats{font-size:12px;color:var(--text-3);line-height:1.6}'
css_add = css_anchor + '''
  .dy-request{background:rgba(64,158,255,.06);border:1px solid rgba(64,158,255,.25);border-radius:8px;padding:10px 12px;margin-bottom:10px}
  .dy-request-title{font-size:12px;color:var(--text-2);margin-bottom:6px}
  .dy-request-text{font-size:13px;color:var(--text);background:#fff;border:1px solid var(--border);border-radius:6px;padding:8px 10px;line-height:1.7;white-space:pre-wrap;margin-bottom:8px}
  .dy-request-actions{display:flex;gap:8px;flex-wrap:wrap}
'''
assert data.count(css_anchor) == 1, 'css anchor not unique'
data = data.replace(css_anchor, css_add, 1)

# ========== 2) HTML：searchbar 后加 dy-request ==========
html_old = '''        <div class="dy-searchbar">
          <input type="text" id="dy-input" class="dy-input" placeholder="输入关键词，如：帆布鞋、老爹鞋、鞋店运营" />
          <button class="btn btn-primary" onclick="dySearch()">搜索</button>
        </div>'''
html_new = html_old + '''
        <div class="dy-request" id="dy-request" hidden>
          <div class="dy-request-title">把下面的搜索条件发给 AI，AI 会自动把真实抖音热门视频更新到本页</div>
          <div class="dy-request-text" id="dy-request-text"></div>
          <div class="dy-request-actions">
            <button class="btn btn-sm btn-primary" onclick="dyCopyRequest()">一键复制搜索条件</button>
            <button class="btn btn-sm" onclick="dyCopyLink()">复制页面链接</button>
          </div>
        </div>'''
assert data.count(html_old) == 1, 'html anchor not found'
data = data.replace(html_old, html_new, 1)

# ========== 3) JS：替换 dySearch 函数 ==========
js_old_search = '''  function dySearch(){
    const el = $('dy-input');
    dyData.keyword = el ? el.value.trim() : '';
    renderDy();
    if (dyData.videos.length) {
      toast('已按当前条件筛选');
    } else {
      toast('已记录关键词，请把关键词和筛选条件发给 AI 更新真实数据');
    }
  }'''
js_new_search = '''  function dyBuildRequestText(){
    const sortName = { default:'综合', likes:'点赞最多', favorites:'收藏最多', plays:'播放最多', comments:'评论最多' }[dyData.sort] || '综合';
    const timeName = { all:'不限', today:'今天', week:'本周', month:'本月' }[dyData.timeRange] || '不限';
    const durName = { all:'不限', short:'0-1分钟', medium:'1-5分钟', long:'5分钟以上' }[dyData.duration] || '不限';
    return '帮我搜抖音热门视频：\\n关键词：' + (dyData.keyword || '（未填）') + '\\n排序：' + sortName + '\\n时间：' + timeName + '\\n时长：' + durName;
  }
  function dyUpdateHash(){
    const params = new URLSearchParams();
    if (dyData.keyword) params.set('keyword', dyData.keyword);
    if (dyData.sort !== 'default') params.set('sort', dyData.sort);
    if (dyData.timeRange !== 'all') params.set('time', dyData.timeRange);
    if (dyData.duration !== 'all') params.set('duration', dyData.duration);
    const qs = params.toString();
    location.hash = qs ? '#douyin?' + qs : '#douyin';
  }
  function dyFromHash(){
    const h = location.hash;
    if (!h || h.indexOf('#douyin?') !== 0) return;
    const qs = h.slice('#douyin?'.length);
    try {
      const p = new URLSearchParams(qs);
      if (p.get('keyword')) { dyData.keyword = p.get('keyword'); const el = $('dy-input'); if (el) el.value = dyData.keyword; }
      if (p.get('sort')) dyData.sort = p.get('sort');
      if (p.get('time')) dyData.timeRange = p.get('time');
      if (p.get('duration')) dyData.duration = p.get('duration');
    } catch(e) {}
  }
  function dyShowRequest(){
    const box = $('dy-request');
    const txt = $('dy-request-text');
    if (!box || !txt) return;
    if (!dyData.keyword) { box.hidden = true; return; }
    txt.textContent = dyBuildRequestText();
    box.hidden = false;
  }
  function dyCopyRequest(){
    const txt = dyBuildRequestText();
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(txt).then(function(){ toast('已复制，粘贴发给 AI 即可'); }, function(){ toast('复制失败，请手动复制'); });
    } else {
      const ta = document.createElement('textarea'); ta.value = txt; document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); toast('已复制，粘贴发给 AI 即可'); } catch(e){ toast('复制失败，请手动复制'); }
      document.body.removeChild(ta);
    }
  }
  function dyCopyLink(){
    const url = location.href;
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(url).then(function(){ toast('链接已复制，发给 AI 即可'); }, function(){ toast('复制失败，请手动复制地址栏'); });
    } else {
      const ta = document.createElement('textarea'); ta.value = url; document.body.appendChild(ta); ta.select();
      try { document.execCommand('copy'); toast('链接已复制'); } catch(e){ toast('复制失败，请手动复制地址栏'); }
      document.body.removeChild(ta);
    }
  }
  function dySearch(){
    const el = $('dy-input');
    dyData.keyword = el ? el.value.trim() : '';
    dyUpdateHash();
    renderDy();
    dyShowRequest();
    if (dyData.videos.length) {
      toast('已按当前条件筛选');
    } else {
      toast('已生成搜索条件，点击「一键复制」发给 AI');
    }
  }'''
assert data.count(js_old_search) == 1, 'dySearch not found'
data = data.replace(js_old_search, js_new_search, 1)

# ========== 4) JS：筛选点击时同步 hash + 显示请求 ==========
js_old_filter = '''  document.addEventListener('click', function(e){
    const p = e.target.closest ? e.target.closest('#dy-sort .pill') : null;
    if (p) { dyData.sort = p.dataset.sort; renderDy(); return; }
    const t = e.target.closest ? e.target.closest('#dy-time .pill') : null;
    if (t) { dyData.timeRange = t.dataset.time; renderDy(); return; }
    const d = e.target.closest ? e.target.closest('#dy-duration .pill') : null;
    if (d) { dyData.duration = d.dataset.duration; renderDy(); return; }
  });'''
js_new_filter = '''  document.addEventListener('click', function(e){
    const p = e.target.closest ? e.target.closest('#dy-sort .pill') : null;
    if (p) { dyData.sort = p.dataset.sort; dyUpdateHash(); renderDy(); dyShowRequest(); return; }
    const t = e.target.closest ? e.target.closest('#dy-time .pill') : null;
    if (t) { dyData.timeRange = t.dataset.time; dyUpdateHash(); renderDy(); dyShowRequest(); return; }
    const d = e.target.closest ? e.target.closest('#dy-duration .pill') : null;
    if (d) { dyData.duration = d.dataset.duration; dyUpdateHash(); renderDy(); dyShowRequest(); return; }
  });'''
assert data.count(js_old_filter) == 1, 'filter handler not found'
data = data.replace(js_old_filter, js_new_filter, 1)

# ========== 5) JS：init 里从 hash 恢复 + 显示请求 ==========
init_old = '    renderSidebar();\n    renderDy();\n    renderChat();'
init_new = '    renderSidebar();\n    dyFromHash();\n    renderDy();\n    dyShowRequest();\n    renderChat();'
assert data.count(init_old) == 1, 'init block not unique'
data = data.replace(init_old, init_new, 1)

io.open(p, 'w', encoding='utf-8', newline='\r\n').write(data)
print('BRIDGE DONE. size:', len(data))
