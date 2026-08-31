# -*- coding: utf-8 -*-
"""升级抖音热榜：加入完整筛选栏（排序/时间/时长）+ 扩展数据结构"""
import io

p = r'C:/Users/Administrator/Doubao/chats/2026-08-31/new-chat-1/fengye-image-site/index.html'
data = io.open(p, encoding='utf-8').read()

# ========== 1) 追加筛选栏 CSS（在 .dy-empty-card 后） ==========
css_anchor = '  .dy-empty-card b{color:var(--primary)}'
css_add = css_anchor + '''
  .dy-searchbar{display:flex;gap:8px;margin:10px 0 12px}
  .dy-input{flex:1;padding:8px 12px;border:1px solid var(--border);border-radius:6px;font-size:13px;font-family:inherit;background:#fff;color:var(--text)}
  .dy-input:focus{outline:none;border-color:var(--primary)}
  .dy-filters{display:flex;flex-direction:column;gap:8px;margin-bottom:8px}
  .dy-filter-row{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
  .dy-filter-label{font-size:12px;color:var(--text-3);min-width:36px;flex-shrink:0}
  .dy-stats{font-size:12px;color:var(--text-3);line-height:1.6}
'''
assert data.count(css_anchor) == 1, 'css anchor not unique'
data = data.replace(css_anchor, css_add, 1)

# ========== 2) 替换 douyin-panel HTML ==========
old_panel = '''    <!-- ======== 抖音热榜 ======== -->
    <section class="panel" id="douyin-panel">
      <div class="dy-head">
        <h2>抖音热门视频 <span class="dy-tag">真实数据 · 按热度排序</span></h2>
        <p class="hint">当前关键词：<b id="dy-keyword">—</b>　·　更新于：<span id="dy-updated">—</span></p>
      </div>
      <div id="dy-list"></div>
    </section>'''

new_panel = '''    <!-- ======== 抖音热榜 ======== -->
    <section class="panel" id="douyin-panel">
      <div class="dy-head">
        <h2>抖音热门视频 <span class="dy-tag">真实数据 · 多维度筛选</span></h2>
        <div class="dy-searchbar">
          <input type="text" id="dy-input" class="dy-input" placeholder="输入关键词，如：帆布鞋、老爹鞋、鞋店运营" />
          <button class="btn btn-primary" onclick="dySearch()">搜索</button>
        </div>
        <div class="dy-filters">
          <div class="dy-filter-row">
            <span class="dy-filter-label">排序</span>
            <div class="pills" id="dy-sort">
              <span class="pill selected" data-sort="default">综合</span>
              <span class="pill" data-sort="likes">点赞最多</span>
              <span class="pill" data-sort="favorites">收藏最多</span>
              <span class="pill" data-sort="plays">播放最多</span>
              <span class="pill" data-sort="comments">评论最多</span>
            </div>
          </div>
          <div class="dy-filter-row">
            <span class="dy-filter-label">时间</span>
            <div class="pills" id="dy-time">
              <span class="pill selected" data-time="all">不限</span>
              <span class="pill" data-time="today">今天</span>
              <span class="pill" data-time="week">本周</span>
              <span class="pill" data-time="month">本月</span>
            </div>
          </div>
          <div class="dy-filter-row">
            <span class="dy-filter-label">时长</span>
            <div class="pills" id="dy-duration">
              <span class="pill selected" data-duration="all">不限</span>
              <span class="pill" data-duration="short">0-1分钟</span>
              <span class="pill" data-duration="medium">1-5分钟</span>
              <span class="pill" data-duration="long">5分钟以上</span>
            </div>
          </div>
        </div>
        <p class="hint">当前：关键词 <b id="dy-keyword">—</b> · <span id="dy-condition">综合 · 不限时间</span> · 更新于 <span id="dy-updated">—</span></p>
      </div>
      <div id="dy-list"></div>
    </section>'''
assert data.count(old_panel) == 1, 'old panel not found'
data = data.replace(old_panel, new_panel, 1)

# ========== 3) 替换 JS 数据+渲染逻辑 ==========
js_start = '  /* ===== 抖音热榜（真实数据，由 AI 搜索后更新） ===== */'
js_end = '  /* ===== 标签页 / 主题 / toast ===== */'
assert data.count(js_start) == 1 and data.count(js_end) == 1, 'js anchors not found'

new_js = '''  /* ===== 抖音热榜（真实数据，由 AI 按关键词+筛选条件搜索后更新） ===== */
  let dyData = {
    keyword: '',
    sort: 'default',        // default / likes / favorites / plays / comments
    timeRange: 'all',       // all / today / week / month
    duration: 'all',        // all / short / medium / long
    updatedAt: '',
    videos: []
    /* 单条视频字段：title, author, url, cover,
       playText, playNum, likeText, likeNum,
       favText, favNum, commentText, commentNum,
       publishTime(YYYY-MM-DD), durationSec */
  };
  function dyEsc(s){ return String(s == null ? '' : s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;'); }
  function dyNum(v){ return Number(v) || 0; }
  function dyInTimeRange(publishTime, range){
    if (!publishTime || range === 'all') return true;
    const d = new Date(publishTime);
    if (isNaN(d.getTime())) return true;
    const diff = (new Date() - d) / 86400000;
    if (range === 'today') return diff < 1;
    if (range === 'week') return diff <= 7;
    if (range === 'month') return diff <= 30;
    return true;
  }
  function dyInDuration(sec, range){
    if (!sec || range === 'all') return true;
    const s = Number(sec) || 0;
    if (range === 'short') return s < 60;
    if (range === 'medium') return s >= 60 && s <= 300;
    if (range === 'long') return s > 300;
    return true;
  }
  function dySortVideos(list, sort){
    if (sort === 'default' || !sort) return list;
    const key = { likes:'likeNum', favorites:'favNum', plays:'playNum', comments:'commentNum' }[sort];
    if (!key) return list;
    return list.slice().sort(function(a,b){ return dyNum(b[key]) - dyNum(a[key]); });
  }
  function dySearch(){
    const el = $('dy-input');
    dyData.keyword = el ? el.value.trim() : '';
    renderDy();
    if (dyData.videos.length) {
      toast('已按当前条件筛选');
    } else {
      toast('已记录关键词，请把关键词和筛选条件发给 AI 更新真实数据');
    }
  }
  function renderDy() {
    const list = $('dy-list');
    if (!list) return;
    document.querySelectorAll('#dy-sort .pill').forEach(function(p){ p.classList.toggle('selected', p.dataset.sort === dyData.sort); });
    document.querySelectorAll('#dy-time .pill').forEach(function(p){ p.classList.toggle('selected', p.dataset.time === dyData.timeRange); });
    document.querySelectorAll('#dy-duration .pill').forEach(function(p){ p.classList.toggle('selected', p.dataset.duration === dyData.duration); });
    const kw = $('dy-keyword'), up = $('dy-updated'), cond = $('dy-condition');
    if (kw) kw.textContent = dyData.keyword || '—';
    if (up) up.textContent = dyData.updatedAt || '—';
    if (cond) {
      const sortName = { default:'综合', likes:'点赞最多', favorites:'收藏最多', plays:'播放最多', comments:'评论最多' }[dyData.sort] || '综合';
      const timeName = { all:'不限时间', today:'今天', week:'本周', month:'本月' }[dyData.timeRange] || '不限时间';
      cond.textContent = sortName + ' · ' + timeName;
    }
    if (!dyData.videos || !dyData.videos.length) {
      list.innerHTML = '<div class="dy-empty-card">尚未获取数据。<br/>在上方输入关键词并选择筛选条件，然后把关键词和条件发给 AI（例如「帮我搜 <b>帆布鞋</b> 本周点赞最多的抖音视频」），AI 会自动把真实热门视频更新到本页。</div>';
      return;
    }
    let filtered = dyData.videos.filter(function(v){
      return dyInTimeRange(v.publishTime, dyData.timeRange) && dyInDuration(v.durationSec, dyData.duration);
    });
    filtered = dySortVideos(filtered, dyData.sort);
    if (!filtered.length) {
      list.innerHTML = '<div class="dy-empty-card">当前筛选条件下没有匹配的视频。<br/>试试放宽时间或时长条件，或让 AI 更新更多数据。</div>';
      return;
    }
    const max = Math.max(1, Math.max.apply(null, filtered.map(function(v){ return dyNum(v.playNum); })));
    list.innerHTML = filtered.map(function(v, i){
      const ratio = Math.max(6, Math.round((dyNum(v.playNum) / max) * 100));
      const rankCls = i < 3 ? ' dy-rank hot' : '';
      const cover = v.cover
        ? '<img src="' + dyEsc(v.cover) + '" alt="' + dyEsc(v.title) + '" loading="lazy" />'
        : '<span class="dy-play"><svg viewBox="0 0 24 24"><path d="M8 5v14l11-7z"/></svg></span>';
      const stats = [
        v.playText ? '▶ ' + dyEsc(v.playText) : '',
        v.likeText ? '♥ ' + dyEsc(v.likeText) : '',
        v.favText ? '★ ' + dyEsc(v.favText) : '',
        v.commentText ? '✎ ' + dyEsc(v.commentText) : ''
      ].filter(Boolean).join('　');
      const meta = ['@' + dyEsc(v.author), v.publishTime ? dyEsc(v.publishTime) : ''].filter(Boolean).join(' · ');
      return '<article class="dy-card">' +
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
      '</article>';
    }).join('');
  }
  document.addEventListener('click', function(e){
    const p = e.target.closest ? e.target.closest('#dy-sort .pill') : null;
    if (p) { dyData.sort = p.dataset.sort; renderDy(); return; }
    const t = e.target.closest ? e.target.closest('#dy-time .pill') : null;
    if (t) { dyData.timeRange = t.dataset.time; renderDy(); return; }
    const d = e.target.closest ? e.target.closest('#dy-duration .pill') : null;
    if (d) { dyData.duration = d.dataset.duration; renderDy(); return; }
  });

  /* ===== 标签页 / 主题 / toast ===== */'''

# 替换从 js_start 到 js_end（含 js_end）之间的内容
si = data.index(js_start)
ei = data.index(js_end)
data = data[:si] + new_js + data[ei + len(js_end):]

io.open(p, 'w', encoding='utf-8', newline='\r\n').write(data)
print('UPGRADE DONE. size:', len(data))
