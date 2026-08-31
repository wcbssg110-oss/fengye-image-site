# -*- coding: utf-8 -*-
"""在枫叶批量生图网站中加入抖音热榜功能"""
import io, sys, os

p = r'C:/Users/Administrator/Doubao/chats/2026-08-31/new-chat-1/fengye-image-site/index.html'
data = io.open(p, encoding='utf-8').read()

# 锚点确认
anchors = [
    '.empty-tip{color:var(--text-3);font-size:13px;padding:20px;text-align:center}',
    'data-panel="chat">GPT 聊天</button>',
    '<!-- ======== 设置 ======== -->',
    '</section>\n\n    <!-- ======== 设置 ======== -->',
    '  function switchTab(tab)',
    '    renderSidebar();',
]
for a in anchors:
    print(repr(a), '->', data.count(a))

# 1) CSS 插入
css_old = '.empty-tip{color:var(--text-3);font-size:13px;padding:20px;text-align:center}'
css_new = css_old + '''
  /* 抖音热榜 */
  .dy-head{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);padding:14px 16px;margin-bottom:14px}
  .dy-head h2{margin:0 0 6px;font-size:16px;display:flex;align-items:center;gap:8px}
  .dy-head .dy-tag{font-size:12px;font-weight:400;color:var(--text-3)}
  .dy-head .hint{margin:0;line-height:1.7}
  .dy-head b{color:var(--primary)}
  .dy-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}
  .dy-card{background:var(--card);border:1px solid var(--border);border-radius:var(--radius);overflow:hidden;display:flex;flex-direction:column;transition:box-shadow .18s,border-color .18s}
  .dy-card:hover{box-shadow:0 6px 18px rgba(0,0,0,.08);border-color:#c6d6ea}
  .dy-cover{position:relative;aspect-ratio:16/10;background:#0f1419;display:grid;place-items:center;overflow:hidden}
  .dy-cover img{width:100%;height:100%;object-fit:cover;display:block}
  .dy-rank{position:absolute;top:8px;left:8px;background:rgba(0,0,0,.62);color:#fff;font-weight:700;font-size:13px;padding:2px 9px;border-radius:6px;letter-spacing:.5px}
  .dy-rank.hot{background:#f04e3c}
  .dy-play{width:46px;height:46px;border-radius:50%;background:rgba(255,255,255,.92);display:grid;place-items:center;box-shadow:0 2px 10px rgba(0,0,0,.3)}
  .dy-play svg{width:20px;height:20px;fill:#0f1419;margin-left:2px}
  .dy-info{padding:11px 12px 10px;display:flex;flex-direction:column;gap:7px;flex:1}
  .dy-title{font-size:14px;font-weight:600;line-height:1.45;color:var(--text);display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}
  .dy-meta{display:flex;align-items:center;justify-content:space-between;font-size:12px;color:var(--text-3);gap:8px}
  .dy-meta .dy-author{display:flex;align-items:center;gap:6px;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
  .dy-heat{height:5px;background:#eef1f5;border-radius:3px;overflow:hidden}
  .dy-heat i{display:block;height:100%;background:var(--primary);border-radius:3px}
  .dy-link{display:block;text-align:center;padding:9px;background:var(--primary-light);color:var(--primary);font-size:13px;text-decoration:none;border-top:1px solid var(--border);transition:background .15s,color .15s}
  .dy-link:hover{background:var(--primary);color:#fff}
  .dy-empty-card{background:var(--card);border:1px dashed var(--border);border-radius:var(--radius);padding:30px 20px;text-align:center;color:var(--text-3);font-size:13px;line-height:2}
  .dy-empty-card b{color:var(--primary)}
'''
assert data.count(css_old) == 1, 'CSS anchor not unique/found'
data = data.replace(css_old, css_new, 1)

# 2) tab 按钮
tab_old = 'data-panel="chat">GPT 聊天</button>'
tab_new = 'data-panel="chat">GPT 聊天</button>\n      <button class="tab" data-panel="douyin">抖音热榜</button>'
assert data.count(tab_old) == 1, 'tab anchor not found'
data = data.replace(tab_old, tab_new, 1)

# 3) panel：插在 设置 注释之前
panel_anchor = '<!-- ======== 设置 ======== -->'
panel_html = '''<!-- ======== 抖音热榜 ======== -->
    <section class="panel" id="douyin-panel">
      <div class="dy-head">
        <h2>抖音热门视频 <span class="dy-tag">真实数据 · 按热度排序</span></h2>
        <p class="hint">当前关键词：<b id="dy-keyword">—</b>　·　更新于：<span id="dy-updated">—</span></p>
      </div>
      <div id="dy-list"></div>
    </section>

'''
assert data.count(panel_anchor) == 1, 'panel anchor not found'
data = data.replace(panel_anchor, panel_html + panel_anchor, 1)

# 4) JS：在 switchTab 函数前插入数据 + 渲染逻辑
js_anchor = '  /* ===== 标签页 / 主题 / toast ===== */'
js_code = '''  /* ===== 抖音热榜（真实数据，由 AI 搜索后更新） ===== */
  let dyData = { keyword: '', updatedAt: '', videos: [] };
  function dyEsc(s){ return String(s == null ? '' : s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
  function renderDy() {
    const list = $('dy-list');
    if (!list) return;
    const kw = $('dy-keyword'), up = $('dy-updated');
    if (kw) kw.textContent = dyData.keyword || '—';
    if (up) up.textContent = dyData.updatedAt || '—';
    if (!dyData.videos || !dyData.videos.length) {
      list.innerHTML = '<div class="dy-empty-card">尚未获取数据。<br/>把关键词发给 AI（例如「帮我搜 <b>帆布鞋</b> 的抖音热门视频」），AI 会自动把真实热门视频更新到本页。</div>';
      return;
    }
    const max = Math.max(1, ...dyData.videos.map(v => Number(v.playNum) || 0));
    list.innerHTML = dyData.videos.map((v, i) => {
      const ratio = Math.max(6, Math.round(((Number(v.playNum) || 0) / max) * 100));
      const rankCls = i < 3 ? ' dy-rank hot' : '';
      const cover = v.cover
        ? '<img src="' + dyEsc(v.cover) + '" alt="' + dyEsc(v.title) + '" loading="lazy" />'
        : '<span class="dy-play"><svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg></span>';
      return '<article class="dy-card">' +
        '<div class="dy-cover">' +
          '<span class="dy-rank' + rankCls + '">TOP ' + (i + 1) + '</span>' + cover +
        '</div>' +
        '<div class="dy-info">' +
          '<div class="dy-title">' + dyEsc(v.title) + '</div>' +
          '<div class="dy-meta"><span class="dy-author">@' + dyEsc(v.author) + '</span><span>' + dyEsc(v.playText) + ' 播放</span></div>' +
          '<div class="dy-heat"><i style="width:' + ratio + '%"></i></div>' +
        '</div>' +
        '<a class="dy-link" href="' + dyEsc(v.url) + '" target="_blank" rel="noopener">去抖音看 ›</a>' +
      '</article>';
    }).join('');
  }

  /* ===== 标签页 / 主题 / toast ===== */'''
assert data.count(js_anchor) == 1, 'js anchor not found'
data = data.replace(js_anchor, js_code, 1)

# 5) init 中调用 renderDy()
init_anchor = '    renderSidebar();'
init_new = '    renderSidebar();\n    renderDy();'
assert data.count(init_anchor) == 1, 'init anchor not found'
data = data.replace(init_anchor, init_new, 1)

io.open(p, 'w', encoding='utf-8', newline='\r\n').write(data)
print('DONE. new size:', len(data))
