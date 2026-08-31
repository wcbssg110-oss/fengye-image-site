# -*- coding: utf-8 -*-
"""修改前端 dySearch：搜索成功后显示进度并自动刷新"""
import io

p = r'C:/Users/Administrator/Doubao/chats/2026-08-31/new-chat-1/fengye-image-site/index.html'
data = io.open(p, encoding='utf-8').read()

old = '''  async function dySearch(){
    const el = $('dy-input');
    dyData.keyword = el ? el.value.trim() : '';
    dyUpdateHash();
    renderDy();
    dyShowRequest();
    if (!dyData.keyword) { toast('请输入关键词'); return; }
    try {
      const res = await fetch('/.netlify/functions/submit-search', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ keyword: dyData.keyword, sort: dyData.sort, timeRange: dyData.timeRange, duration: dyData.duration })
      });
      const d = await res.json();
      if (d.ok) { toast('搜索请求已提交，跟 AI 说"处理搜索"即可'); }
      else { toast(d.error || '提交失败，可用一键复制'); }
    } catch(e) { toast('提交失败，可用一键复制发给 AI'); }
  }'''

new = '''  async function dySearch(){
    const el = $('dy-input');
    dyData.keyword = el ? el.value.trim() : '';
    dyUpdateHash();
    renderDy();
    dyShowRequest();
    if (!dyData.keyword) { toast('请输入关键词'); return; }
    const btn = document.getElementById('dy-search-btn');
    if (btn) { btn.disabled = true; btn.textContent = '搜索中...'; }
    toast('正在搜索抖音视频并更新网站，请稍候...');
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
  }'''

assert data.count(old) == 1, 'dySearch not found'
data = data.replace(old, new, 1)

# 修改 dy-request 区域提示
old_title = '搜索条件已生成。跟 AI 说一声"处理搜索"，AI 会自动读取请求并把真实抖音热门视频更新到本页'
new_title = '输入关键词点搜索，后端会自动搜索抖音热门视频并更新到本页，约30秒后自动刷新显示结果'
assert data.count(old_title) == 1, 'request title not found'
data = data.replace(old_title, new_title, 1)

io.open(p, 'w', encoding='utf-8', newline='\r\n').write(data)
print('FRONTEND UPDATED. size:', len(data))
