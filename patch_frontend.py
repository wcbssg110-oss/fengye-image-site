# -*- coding: utf-8 -*-
import io

path = r'C:/Users/Administrator/Doubao/chats/2026-08-31/new-chat-1/fengye-image-site/index.html'
with io.open(path, encoding='utf-8') as f:
    content = f.read()

old = """    toast('正在搜索抖音视频并更新网站，请稍候...');
    try {
      const res = await fetch('/.netlify/functions/submit-search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyword: dyData.keyword, sort: dyData.sort, timeRange: dyData.timeRange, duration: dyData.duration })
      });
      const d = await res.json();
      if (d.ok && d.count > 0) {
        toast('搜到 ' + d.count + ' 条视频，网站更新中，30秒后自动刷新');
        setTimeout(function(){ location.reload(); }, 30000);
      } else if (d.ok) {
        toast(d.message || '未搜到相关视频，请换个关键词');
        if (btn) { btn.disabled = false; btn.textContent = '搜索'; }
      } else {
        toast(d.error || '搜索失败，请重试');
        if (btn) { btn.disabled = false; btn.textContent = '搜索'; }
      }
    } catch(e) {
      toast('搜索失败：' + e.message);
      if (btn) { btn.disabled = false; btn.textContent = '搜索'; }
    }
  }"""

new = """    toast('正在提交搜索请求，请稍候...');
    try {
      const res = await fetch('/.netlify/functions/submit-search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyword: dyData.keyword, sort: dyData.sort, timeRange: dyData.timeRange, duration: dyData.duration })
      });
      const d = await res.json();
      if (d.ok) {
        toast(d.message || '搜索请求已提交，正在处理中...');
        let checks = 0;
        const poll = setInterval(async function(){
          checks++;
          try {
            const qres = await fetch('/.netlify/functions/submit-search');
            const qd = await qres.json();
            const stillInQueue = (qd.queue || []).some(function(q){ return q.keyword === dyData.keyword && q.status === 'pending'; });
            if (!stillInQueue || checks >= 30) {
              clearInterval(poll);
              if (!stillInQueue) toast('搜索完成，正在刷新页面...');
              else toast('搜索处理时间较长，请稍后手动刷新');
              setTimeout(function(){ location.reload(); }, 1500);
            }
          } catch(e) {}
        }, 10000);
      } else {
        toast(d.error || '搜索失败，请重试');
        if (btn) { btn.disabled = false; btn.textContent = '搜索'; }
      }
    } catch(e) {
      toast('搜索失败：' + e.message);
      if (btn) { btn.disabled = false; btn.textContent = '搜索'; }
    }
  }"""

if old in content:
    content = content.replace(old, new)
    with io.open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print('Replaced successfully')
else:
    print('Old string not found!')
    # 查找相似内容
    idx = content.find("正在搜索抖音视频")
    if idx >= 0:
        print('Found at index', idx)
        print(repr(content[idx:idx+200]))
