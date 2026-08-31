# -*- coding: utf-8 -*-
"""修改前端 dySearch：搜索时调用后端 API 提交队列"""
import io

p = r'C:/Users/Administrator/Doubao/chats/2026-08-31/new-chat-1/fengye-image-site/index.html'
data = io.open(p, encoding='utf-8').read()

# 替换 dySearch 函数
old = '''  function dySearch(){
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

new = '''  async function dySearch(){
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

assert data.count(old) == 1, 'dySearch not found'
data = data.replace(old, new, 1)

# 修改 dy-request 标题提示
old_title = '把下面的搜索条件发给 AI，AI 会自动把真实抖音热门视频更新到本页'
new_title = '搜索条件已生成。跟 AI 说一声"处理搜索"，AI 会自动读取请求并把真实抖音热门视频更新到本页'
assert data.count(old_title) == 1, 'request title not found'
data = data.replace(old_title, new_title, 1)

io.open(p, 'w', encoding='utf-8', newline='\r\n').write(data)
print('FRONTEND UPDATED. size:', len(data))
