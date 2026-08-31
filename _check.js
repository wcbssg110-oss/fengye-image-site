
  /* ===== 状态 ===== */
  const DEFAULT_PROMPT = '生成九宫格图片，白色背景，各个角度的鞋子';   // 内置九宫格提示词，无需输入
  let rows = [];
  let rowSeq = 1;
  function freshRow() { return { id: rowSeq++, prompt: '', title: '', images: [], generated: [], status: '' }; }
  let batchRound = 0;   // 批量上传轮次：第 1 批放每行第 1 格，第 2 批放每行第 2 格…
  function seedRows() { rows = []; rowSeq = 1; batchRound = 0; for (let i = 0; i < 5; i++) { const r = freshRow(); if (i === 0) r.prompt = DEFAULT_PROMPT; rows.push(r); } }
  seedRows();
  let batchRefs = [];   // 批量参考图（最多6张）
  let toastTimer = null;

  /* ===== 提示词编辑参数 ===== */
  function $(id) { return document.getElementById(id); }
  function getVal(id) { const el = $(id); return el ? el.value.trim() : ''; }
  function activePill(group) {
    const el = document.querySelector('.pills[data-group="' + group + '"] .pill.selected');
    return el ? el.textContent.trim() : '';
  }

  /* ===== 九宫格生图（内置提示词，无需输入） ===== */
  const NINE_PROMPT = DEFAULT_PROMPT;
  let nineRefs = [];        // 上传的鞋子参考图
  let nineResults = [];     // 生成的九宫格图片地址
  function renderNineList() {
    const box = $('nine-image-list');
    if (!box) return;
    box.innerHTML = nineRefs.map((u, i) =>
      '<span style="position:relative;display:inline-block"><img src="' + u + '" onclick="viewImage(this.src)" alt="参考图"><button class="del-up" onclick="nineRemove(' + i + ')">✕</button></span>').join('');
    try { localStorage.setItem('llt_nine_refs', JSON.stringify(nineRefs)); } catch (e) {}
  }
  function renderNineResult() {
    const box = $('nine-result');
    if (!box) return;
    box.innerHTML = nineResults.length
      ? nineResults.map(u => '<a href="javascript:void(0)" onclick="viewImage(\'' + u + '\')"><img src="' + u + '"></a>').join('')
      : '<div class="image-placeholder" style="width:100%;height:360px">生成的九宫格将显示在这里</div>';
    try { localStorage.setItem('llt_nine_results', JSON.stringify(nineResults)); } catch (e) {}
  }
  function nineUpload() {
    const fi = $('nine-files');
    fi.value = '';
    const handler = (e) => {
      const files = Array.from(e.target.files || []);
      fi.removeEventListener('change', handler);
      if (!files.length) return;
      files.forEach(f => {
        const reader = new FileReader();
        reader.onload = () => { nineRefs.push(reader.result); renderNineList(); };
        reader.readAsDataURL(f);
      });
      toast('已添加 ' + files.length + ' 张鞋子参考图');
    };
    fi.addEventListener('change', handler);
    fi.click();
  }
  function nineRemove(i) { nineRefs.splice(i, 1); renderNineList(); }
  function nineClear() {
    nineRefs = []; nineResults = [];
    renderNineList(); renderNineResult();
    toast('已清空参考图与结果');
  }
  /* 九宫格生图：复用 gemini 生图管线（grsaiDrawGenerate /v1/api/generate） */
  async function nineGenerate() {
    const cfg = getConfig();
    if (!cfg.key) { toast('请先在「设置」页填写并保存 API Key'); switchTab('settings'); return; }
    if (!nineRefs.length) { toast('请先添加参考图'); return; }
    openLog();
    logProgress('正在生成九宫格…（参考图 ' + nineRefs.length + ' 张，一次提交）');
    addLog('info', '▶ 九宫格开始生成（一次提交 ' + nineRefs.length + ' 张参考图）');
    try {
      const urls = await geminiGenerate(cfg, NINE_PROMPT, nineRefs.slice(), 1);
      nineResults = urls;
      renderNineResult();
      addLog('ok', '✔ 九宫格生成完成：' + urls.join(', '));
      logProgress('完成：成功 ' + urls.length + ' 张');
      toast('九宫格生成完成');
    } catch (e) {
      addLog('error', '✘ 九宫格生成失败：' + e.message);
      logProgress('生成失败');
      toast('生成失败：' + e.message);
    }
  }
  function nineDownload() {
    if (!nineResults.length) { toast('还没有生成的九宫格'); return; }
    nineResults.forEach((u, i) => downloadImage(u, 'jiugongge-' + (i + 1) + '.png'));
    toast('开始下载 ' + nineResults.length + ' 张九宫格');
  }

  /* ===== GPT 聊天（Grsai /v1/chat/completions，流式，支持上传图片/文本） ===== */
  /* ===== GPT 聊天（ChatGPT 风格：多会话 + 流式 + 上传图片/文本 + Markdown） ===== */
  let chatMsgs = [];
  let chatBusy = false;
  let chatFiles = [];   // 待发送附件：{name, kind:'image'|'text', data}
  let convs = [];       // 会话列表：{id, title, msgs}
  let curConvId = null;
  function curConv() { return convs.find(c => c.id === curConvId) || null; }

  function escHtml(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function userContentHtml(m) {
    let html = '';
    if (Array.isArray(m.content)) {
      const imgs = m.content.filter(p => p.type === 'image_url' && p.image_url && p.image_url.url);
      const texts = m.content.filter(p => p.type === 'text').map(p => p.text);
      if (imgs.length) {
        html += '<div class="msg-imgs">' + imgs.map(p => '<img src="' + esc(p.image_url.url) + '" onclick="viewImage(this.src)" title="点击预览">').join('') + '</div>';
      }
      if (texts.length) html += '<span class="msg-text">' + escHtml(texts.join('\n')) + '</span>';
    } else {
      html = '<span class="msg-text">' + escHtml(msgText(m)) + '</span>';
    }
    return html;
  }
  function msgText(m) {
    if (typeof m.content === 'string') return m.content;
    if (Array.isArray(m.content)) {
      return m.content.map(c => {
        if (c.type === 'text') return c.text;
        if (c.image_url) return '[图片]';
        return '[附件]';
      }).filter(Boolean).join('\n');
    }
    return String(m.content || '');
  }
  /* 轻量 Markdown 渲染（已转义，安全） */
  function mdToHtml(src) {
    src = escHtml(src);
    const blocks = [];
    src = src.replace(/```([\s\S]*?)```/g, function (m, code) {
      const lines = code.split('\n');
      const first = lines[0].trim();
      const lang = /^[a-zA-Z0-9+#.-]+$/.test(first) ? first : '';
      const body = (lang ? lines.slice(1) : lines).join('\n').replace(/^\n+|\n+$/g, '');
      blocks.push('<div class="md-codecard"><div class="md-codehead"><span>' + (lang || '代码') + '</span><button onclick="copyCode(this)">复制</button></div><pre><code>' + body + '</code></pre></div>');
      return '\u0000' + (blocks.length - 1) + '\u0000';
    });
    src = src.replace(/^### (.*)$/gm, '<h4>$1</h4>');
    src = src.replace(/^## (.*)$/gm, '<h3>$1</h3>');
    src = src.replace(/^# (.*)$/gm, '<h2>$1</h2>');
    src = src.replace(/`([^`]+)`/g, '<code>$1</code>');
    src = src.replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>');
    src = src.replace(/(^|[^*])\*([^*\n]+)\*/g, '$1<i>$2</i>');
    src = src.replace(/\[([^\]]+)\]\((https?:[^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');
    const lines = src.split('\n');
    const html = []; let inUl = false, inOl = false;
    const closeAll = () => { if (inUl) { html.push('</ul>'); inUl = false; } if (inOl) { html.push('</ol>'); inOl = false; } };
    for (const line of lines) {
      const t = line.trim();
      if (!t) { closeAll(); html.push(''); continue; }
      if (/^[-*] /.test(t)) { if (!inUl) { closeAll(); html.push('<ul>'); inUl = true; } html.push('<li>' + t.replace(/^[-*] /, '') + '</li>'); continue; }
      if (/^\d+\. /.test(t)) { if (!inOl) { closeAll(); html.push('<ol>'); inOl = true; } html.push('<li>' + t.replace(/^\d+\. /, '') + '</li>'); continue; }
      closeAll();
      if (/^<h[234]>/.test(t) || /^<pre>/.test(t)) html.push(t);
      else html.push('<p>' + t + '</p>');
    }
    closeAll();
    let out = html.join('\n');
    out = out.replace(/\u0000(\d+)\u0000/g, function (m, i) { return blocks[+i] || ''; });
    return out;
  }

  function saveChat() {
    const c = curConv();
    if (c) {
      if (!c.title) {
        const first = c.msgs.find(m => m.role === 'user');
        if (first) {
          const t = msgText(first).replace(/\s+/g, ' ').trim();
          c.title = t ? t.slice(0, 20) : '新对话';
        }
      }
      c.msgs = chatMsgs.slice(-60);
    }
    try {
      const slim = convs.map(x => ({
        id: x.id, title: x.title || '',
        msgs: (x.msgs || []).map(m => {
          if (typeof m.content === 'string') return { role: m.role, content: m.content };
          const parts = (m.content || []).map(p => {
            if (p.type === 'image_url') return { type: 'image_url', image_url: { url: p.image_url && p.image_url.url } };
            if (p.type === 'text') return { type: 'text', text: p.text };
            return null;
          }).filter(Boolean);
          return { role: m.role, content: parts };
        })
      }));
      localStorage.setItem('llt_convs', JSON.stringify(slim));
      localStorage.setItem('llt_cur_conv', String(curConvId || ''));
    } catch (e) {}
  }
  function renderSidebar() {
    const box = $('chat-history');
    if (!box) return;
    box.innerHTML = convs.map(c => {
      const active = c.id === curConvId;
      return '<div class="cgpt-hist-item' + (active ? ' active' : '') + '" onclick="openConv(' + c.id + ')">' +
        '<span class="cgpt-hist-title">' + esc(c.title || '新对话') + '</span>' +
        '<button class="cgpt-hist-del" onclick="delConv(' + c.id + ', event)" title="删除">🗑</button></div>';
    }).join('');
  }
  function newChat() {
    const c = { id: Date.now(), title: '', msgs: [] };
    convs.unshift(c); curConvId = c.id; chatMsgs = c.msgs;
    chatFiles = []; renderChatFiles();
    saveChat(); renderSidebar(); renderChat();
    const inp = $('chat-input'); if (inp) inp.focus();
  }
  function openConv(id) {
    const c = convs.find(x => x.id === id); if (!c) return;
    curConvId = id; chatMsgs = c.msgs;
    saveChat(); renderSidebar(); renderChat();
  }
  function delConv(id, ev) {
    if (ev) ev.stopPropagation();
    convs = convs.filter(x => x.id !== id);
    if (curConvId === id) { const c = { id: Date.now(), title: '', msgs: [] }; convs.unshift(c); curConvId = c.id; chatMsgs = c.msgs; }
    saveChat(); renderSidebar(); renderChat();
  }
  function emptyStateHtml() {
    return '<div class="chat-empty">' +
      '<div class="ce-title">我们先从哪里开始呢？</div>' +
      '<div class="ce-chips">' +
      '<button class="ce-chip" onclick="suggest(\'帮我写一段商品详情介绍\')">🛍️ 帮我写一段商品详情介绍</button>' +
      '<button class="ce-chip" onclick="suggest(\'总结一下这份文档的重点\')">📄 总结一下这份文档的重点</button>' +
      '<button class="ce-chip" onclick="suggest(\'给我一些店铺运营的创意灵感\')">💡 给我一些店铺运营的创意灵感</button>' +
      '<button class="ce-chip" onclick="suggest(\'帮我优化这段代码\')">🛠 帮我优化这段代码</button>' +
      '</div></div>';
  }
  function suggest(text) {
    const inp = $('chat-input'); if (inp) { inp.value = text; inp.focus(); if (window.syncSend) syncSend(); }
  }
  function renderChat() {
    const list = $('chat-list');
    if (!list) return;
    if (!chatMsgs.length) { list.innerHTML = emptyStateHtml(); return; }
    list.innerHTML = chatMsgs.map((m, i) => {
      if (m.role === 'user') return '<div class="chat-msg user" data-idx="' + i + '">' + userContentHtml(m) +
        '<div class="chat-actions"><button onclick="editMsg(this)">编辑</button><button onclick="copyMsg(this)">复制</button></div></div>';
      const raw = msgText(m);
      return '<div class="chat-msg assistant" data-idx="' + i + '">' +
        '<div class="md">' + mdToHtml(raw) + '</div>' +
        '<div class="chat-actions"><button onclick="editMsg(this)">编辑</button><button onclick="copyMsg(this)">复制</button><button onclick="regenerate(this)">重新生成</button></div></div>';
    }).join('');
    scrollChat();
  }
  function scrollChat() { const c = document.querySelector('.cgpt-scroll'); if (c) c.scrollTop = c.scrollHeight; }
  function copyMsg(btn) {
    const bubble = btn.closest('.chat-msg');
    const idx = parseInt(bubble && bubble.dataset.idx, 10);
    const raw = msgText(chatMsgs[idx] || {});
    const done = () => toast('已复制');
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(raw).then(done, () => fallbackCopy(raw, done));
    else fallbackCopy(raw, done);
  }
  function fallbackCopy(text, done) {
    const ta = document.createElement('textarea');
    ta.value = text; ta.style.position = 'fixed'; ta.style.opacity = '0';
    document.body.appendChild(ta); ta.select();
    try { document.execCommand('copy'); done(); } catch (e) {}
    ta.remove();
  }
  function copyCode(btn) {
    const card = btn.closest('.md-codecard');
    const text = card ? card.querySelector('pre code').textContent : '';
    const done = () => toast('已复制');
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(text).then(done, () => fallbackCopy(text, done));
    else fallbackCopy(text, done);
  }
  function regenerate(btn) {
    const bubble = btn.closest('.chat-msg');
    const idx = parseInt(bubble && bubble.dataset.idx, 10);
    if (isNaN(idx) || idx < 1) return;
    const userMsg = chatMsgs[idx - 1];
    if (!userMsg || userMsg.role !== 'user') return;
    chatMsgs = chatMsgs.slice(0, idx);
    const c = curConv(); if (c) c.msgs = chatMsgs;
    renderChat();
    generateReply(makeAssistantBubble());
  }
  function makeAssistantBubble() {
    const list = $('chat-list');
    if (!list) return null;
    if (list.querySelector('.chat-empty')) list.innerHTML = '';
    const div = document.createElement('div');
    div.className = 'chat-msg assistant';
    div.innerHTML = '<span class="typing"><span class="tdot"></span><span class="tdot"></span><span class="tdot"></span></span>';
    list.appendChild(div);
    scrollChat();
    return div;
  }
  function renderAssistantBubble(bubble, raw) {
    if (!bubble) return;
    bubble.innerHTML = '<div class="md">' + mdToHtml(raw) + '</div>' +
      '<div class="chat-actions"><button onclick="editMsg(this)">编辑</button><button onclick="copyMsg(this)">复制</button><button onclick="regenerate(this)">重新生成</button></div>';
    bubble.dataset.idx = String(chatMsgs.length);
    scrollChat();
  }
  function editMsg(btn) {
    const bubble = btn.closest('.chat-msg');
    const idx = parseInt(bubble && bubble.dataset.idx, 10);
    if (isNaN(idx)) return;
    const msg = chatMsgs[idx];
    if (!msg) return;
    const wrap = document.createElement('div');
    wrap.style.cssText = 'display:flex;flex-direction:column;gap:8px;min-width:260px;';
    const ta = document.createElement('textarea');
    ta.value = msgText(msg);
    ta.style.cssText = 'width:100%;box-sizing:border-box;border:1px solid #d9d9d9;border-radius:10px;padding:10px;font-size:15px;line-height:1.6;font-family:inherit;color:#0d0d0d;background:#fff;resize:vertical;min-height:72px;outline:none;';
    const btns = document.createElement('div');
    btns.className = 'chat-actions';
    btns.style.cssText = 'opacity:1;';
    const save = document.createElement('button');
    save.textContent = '保存';
    save.onclick = async () => {
      const v = ta.value;
      msg.content = v;
      if (msg.role === 'user') {
        chatMsgs = chatMsgs.slice(0, idx + 1);
        const c = curConv(); if (c) c.msgs = chatMsgs;
        renderChat();
        generateReply(makeAssistantBubble());
      } else {
        renderChat();
      }
      saveChat(); renderSidebar();
    };
    const cancel = document.createElement('button');
    cancel.textContent = '取消';
    cancel.onclick = () => renderChat();
    btns.appendChild(save); btns.appendChild(cancel);
    wrap.appendChild(ta); wrap.appendChild(btns);
    bubble.innerHTML = '';
    bubble.appendChild(wrap);
    ta.focus();
    scrollChat();
  }
  /* 文件上传 */
  function chatAttach() {
    const fi = $('chat-file-input');
    fi.value = '';
    const handler = (e) => {
      const files = Array.from(e.target.files || []);
      fi.removeEventListener('change', handler);
      if (!files.length) return;
      files.forEach(f => {
        const name = f.name || 'file';
        const isImg = /^image\//.test(f.type) || /\.(png|jpe?g|gif|webp|bmp)$/i.test(name);
        const isText = /\.(txt|md|csv|json|log|js|py|html|css|xml|yaml|yml|tsv)$/i.test(name) || /^text\//.test(f.type);
        if (isImg) {
          const reader = new FileReader();
          reader.onload = () => { chatFiles.push({ name, kind: 'image', data: reader.result }); renderChatFiles(); toast('已添加图片：' + name); };
          reader.readAsDataURL(f);
        } else if (isText) {
          const reader = new FileReader();
          reader.onload = () => { chatFiles.push({ name, kind: 'text', data: String(reader.result || '') }); renderChatFiles(); toast('已添加文件：' + name); };
          reader.readAsText(f, 'utf-8');
        } else {
          toast('暂不支持该文件类型：' + name + '（支持图片和文本文件）');
        }
      });
    };
    fi.addEventListener('change', handler);
    fi.click();
  }
  function removeChatFile(i) { chatFiles.splice(i, 1); renderChatFiles(); }
  function renderChatFiles() {
    const box = $('chat-files');
    if (!box) return;
    box.innerHTML = chatFiles.map((f, i) => {
      const thumb = f.kind === 'image' ? '<img src="' + f.data + '">' : '<span class="txt-ico">T</span>';
      return '<span class="chat-file-chip">' + thumb + '<span class="cf-name">' + esc(f.name) + '</span><button title="移除" onclick="removeChatFile(' + i + ')">✕</button></span>';
    }).join('');
    box.style.display = chatFiles.length ? 'flex' : 'none';
    if (window.syncSend) syncSend();
  }
  async function sendChat() {
    if (chatBusy) { toast('上一条还在回复中…'); return; }
    const cfg = getChatConfig();
    if (!cfg.key) { toast('请先在「设置」页填写并保存 API Key'); switchTab('settings'); return; }
    const inp = $('chat-input');
    const text = inp.value.trim();
    if (!text && !chatFiles.length) { toast('请输入内容或添加文件'); return; }
    inp.value = '';
    const model = ($('chat-model') ? $('chat-model').value : 'gpt-5.6-terra') || 'gpt-5.6-terra';
    let userContent;
    if (chatFiles.length) {
      userContent = [];
      if (text) userContent.push({ type: 'text', text: text });
      chatFiles.forEach(f => {
        if (f.kind === 'image') userContent.push({ type: 'image_url', image_url: { url: f.data } });
        else userContent.push({ type: 'text', text: '【附件：' + f.name + '】\n' + (f.data || '').slice(0, 60000) });
      });
    } else {
      userContent = text;
    }
    const userMsg = { role: 'user', content: userContent };
    chatMsgs.push(userMsg);
    const list = $('chat-list');
    if (list) {
      if (list.querySelector('.chat-empty')) list.innerHTML = '';
      const u = document.createElement('div');
      u.className = 'chat-msg user';
      u.dataset.idx = String(chatMsgs.length - 1);
      u.innerHTML = userContentHtml(userMsg) + '<div class="chat-actions"><button onclick="editMsg(this)">编辑</button><button onclick="copyMsg(this)">复制</button></div>';
      list.appendChild(u); scrollChat();
    }
    chatFiles = []; renderChatFiles();
    if (window.syncSend) syncSend();
    saveChat(); renderSidebar();
    const bubble = makeAssistantBubble();
    await generateReply(bubble);
  }
  async function generateReply(bubble) {
    const cfg = getChatConfig();
    const model = ($('chat-model') ? $('chat-model').value : 'gpt-5.6-terra') || 'gpt-5.6-terra';
    const url = apiBase(cfg.base) + '/chat/completions';
    let full = '';
    chatBusy = true;
    const sendBtn = $('chat-send'); if (sendBtn) sendBtn.disabled = true;
    try {
      const resp = await fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + cfg.key },
        body: JSON.stringify({ model: model, stream: true, messages: chatMsgs })
      });
      if (!resp.ok) { const t = await resp.text(); throw new Error('HTTP ' + resp.status + (t ? ' ' + t.slice(0, 160) : '')); }
      if (!resp.body) { throw new Error('该接口不支持流式响应'); }
      const reader = resp.body.getReader();
      const decoder = new TextDecoder('utf-8');
      let buf = '';
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop();
        for (const line of lines) {
          const s = line.trim();
          if (!s.startsWith('data:')) continue;
          const payload = s.slice(5).trim();
          if (!payload || payload === '[DONE]') continue;
          try {
            const j = JSON.parse(payload);
            const delta = j.choices && j.choices[0] && j.choices[0].delta;
            const piece = (delta && (delta.content || delta.reasoning_content)) || '';
            if (piece) {
              full += piece;
              if (bubble) { bubble.innerHTML = '<div class="md">' + mdToHtml(full) + '</div><div class="chat-actions"><button onclick="editMsg(this)">编辑</button><button onclick="copyMsg(this)">复制</button><button onclick="regenerate(this)">重新生成</button></div>'; scrollChat(); }
            }
          } catch (e) {}
        }
      }
      if (!full) full = '（模型未返回内容）';
      if (bubble) renderAssistantBubble(bubble, full);
      chatMsgs.push({ role: 'assistant', content: full });
      saveChat(); renderSidebar();
    } catch (e) {
      if (bubble) {
        bubble.innerHTML = '⚠ ' + escHtml(e.message);
        bubble.classList.add('error');
      }
      addLog('error', 'GPT 聊天失败：' + e.message);
    } finally {
      chatBusy = false;
      if (sendBtn) sendBtn.disabled = false;
      if (window.syncSend) syncSend();
    }
  }

  /* ===== 批量行渲染 ===== */
  function renderRows() {
    const tb = $('task-body');
    $('task-empty').hidden = rows.length > 0;
    if (!rows.length) { tb.innerHTML = ''; return; }
    tb.innerHTML = rows.map((r, idx) => {
      const gen = (r.generated || []).filter(Boolean);
      const genHtml = gen.length
        ? gen.map(u => '<a href="javascript:void(0)" onclick="viewImage(\'' + u.replace(/'/g, "\\'") + '\')"><img class="gen-thumb" src="' + u + '" alt="Grsai 生成结果"></a>').join('')
        : '<div class="image-placeholder">生成预览</div>';
      const ups = (r.images || []).filter(Boolean);
      const upThumbs = ups.map((u, si) => '<span style="position:relative;display:inline-block"><img class="up-thumb" src="' + u + '" onclick="viewImage(this.src)" alt="上传图"><button class="del-up" onclick="removeImage(' + r.id + ',' + si + ')">✕</button></span>').join('');
      const addHtml = ups.length
        ? '<label class="up-add-pill">＋ 添加<input type="file" accept="image/*" onchange="handleSlotFile(this,' + r.id + ')"></label>'
        : '<label class="up-add-cell">＋ 添加图片<input type="file" accept="image/*" onchange="handleSlotFile(this,' + r.id + ')"></label>';
      const upHtml = '<div class="up-imgs">' + upThumbs + addHtml + '</div>';
      const st = r.status || '';
      const stText = st === 'generating' ? '生成中…' : st === 'done' ? '已完成' : st === 'error' ? '失败' : '待生成';
      return '<tr class="task-row" data-id="' + r.id + '">' +
        '<td><span class="task-number">' + (idx + 1) + '</span></td>' +
        '<td><textarea class="task-text" placeholder="输入提示词…" oninput="setPrompt(' + r.id + ',this.value)">' + esc(r.prompt) + '</textarea>' +
          '<div class="title-line">图片标题：<input class="title-input" oninput="setTitle(' + r.id + ',this.value)" value="' + esc(r.title || '') + '"></div>' +
          '<div class="row-status ' + st + '"><span class="dot"></span>' + stText + '</div></td>' +
        '<td class="image-cell">' + genHtml + '</td>' +
        '<td class="upload-cell"><div class="up-imgs">' + upHtml + '</div></td>' +
        '<td><div class="small-actions">' +
          '<button onclick="doAction(' + r.id + ',\'生图片\')">生图片</button>' +
          '<button class="dl" onclick="doAction(' + r.id + ',\'下图片\')">下图片</button>' +
          '<button onclick="doAction(' + r.id + ',\'生视频\')">生视频</button>' +
          '<button class="dl" onclick="doAction(' + r.id + ',\'下视频\')">下视频</button>' +
          '<button class="delete" onclick="deleteRow(' + r.id + ')">删除任务</button>' +
        '</div></td></tr>';
    }).join('');
    saveRows();
  }
  /* ===== 状态持久化：上传图/生成图/提示词保存到本机，刷新不丢失 ===== */
  function saveRows() {
    try {
      const snap = rows.map(r => ({ id: r.id, prompt: r.prompt || '', title: r.title || '', images: (r.images || []).filter(Boolean), generated: (r.generated || []).filter(Boolean) }));
      localStorage.setItem('llt_rows', JSON.stringify(snap));
    } catch (e) {
      try {   // 存储空间不足：退化为仅保留提示词和生成图地址
        const snap = rows.map(r => ({ id: r.id, prompt: r.prompt || '', title: r.title || '', images: [], generated: (r.generated || []).filter(Boolean) }));
        localStorage.setItem('llt_rows', JSON.stringify(snap));
        if (!window.__quotaWarned) { window.__quotaWarned = true; toast('图片数据较大，刷新后上传图可能丢失（仅保留提示词）'); }
      } catch (e2) {}
    }
  }
  function loadRows() {
    try {
      const raw = localStorage.getItem('llt_rows');
      if (raw === null) return false;
      const arr = JSON.parse(raw);
      if (!Array.isArray(arr)) return false;
      rows = arr.map(x => {
        const gen = Array.isArray(x.generated) ? x.generated.filter(Boolean) : [];
        return { id: (typeof x.id === 'number' ? x.id : rowSeq++), prompt: x.prompt || '', title: x.title || '', images: Array.isArray(x.images) ? x.images.filter(Boolean) : [], generated: gen, status: gen.length ? 'done' : '' };
      });
      rowSeq = rows.reduce((m, r) => Math.max(m, r.id || 0), 0) + 1;
      return true;
    } catch (e) { return false; }
  }
  function esc(s) { return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;'); }
  function setPrompt(id, v) { const r = rows.find(x => x.id === id); if (r) r.prompt = v; }
  function setTitle(id, v) { const r = rows.find(x => x.id === id); if (r) r.title = v; }
  function fillFromFirstRow() {
    if (!rows.length) { toast('没有可填入的行'); return; }
    const first = rows[0].prompt || '';
    rows.forEach((r, i) => { if (i > 0) r.prompt = first; });
    renderRows();
    toast('已将第一行提示词填入所有行');
    addLog('ok', '已将第一行提示词填入所有行');
  }
  function deleteRow(id) {
    rows = rows.filter(x => x.id !== id);
    if (!rows.length) { const nr = freshRow(); nr.prompt = DEFAULT_PROMPT; rows.push(nr); }
    renderRows();
    toast('任务已删除');
  }
  function addRow() {
    rows.push(freshRow());
    renderRows();
    toast('已添加任务行');
  }

  /* ===== 图片预览 ===== */
  function viewImage(src) { if (!src) return; $('imgViewerImg').src = src; $('imgViewer').hidden = false; }
  function closeImgViewer() { $('imgViewer').hidden = true; }
  document.addEventListener('keydown', e => { if (e.key === 'Escape') { closeImgViewer(); closeLog(); closeStats(); } });

  /* ===== 上传 ===== */
  function handleSlotFile(input, id) {
    const f = input.files && input.files[0];
    input.value = '';
    if (!f) return;
    const r = rows.find(x => x.id === id);
    if (!r) return;
    const reader = new FileReader();
    reader.onload = () => {
      if (!r.images) r.images = [];
      r.images.push(reader.result);
      if (r.images.length > 4) r.images = r.images.slice(-4);   // 最多4张
      renderRows();
      toast('已上传参考图');
    };
    reader.readAsDataURL(f);
  }
  function removeImage(id, si) {
    const r = rows.find(x => x.id === id);
    if (!r) return;
    const arr = (r.images || []).filter((_, i) => i !== si);
    r.images = arr;
    renderRows();
  }
  function removeGen(id, gi) {
    const r = rows.find(x => x.id === id);
    if (!r) return;
    (r.generated || []).splice(gi, 1);
    renderRows();
  }
  /* 批量上传图片：第 k 批图片依次放到每行的第 k 格（k=1,2,3…），行不够自动新增 */
  function batchUploadImages() {
    const fi = $('batchUploadInput');
    fi.value = '';
    const handler = (e) => {
      const files = Array.from(e.target.files || []);
      fi.removeEventListener('change', handler);
      if (!files.length) return;
      batchRound++;
      if (batchRound > 4) { batchRound = 4; toast('每行最多 4 张图，无法再添加'); return; }
      const slot = batchRound - 1;
      while (rows.length < files.length) rows.push(freshRow());   // 行不够自动补空行
      files.forEach((f, i) => {
        const r = rows[i];
        if (!r.images) r.images = [];
        while (r.images.length < slot) r.images.push(null);
        r.images[slot] = '__pending__';
        const reader = new FileReader();
        reader.onload = () => { r.images[slot] = reader.result; renderRows(); };
        reader.readAsDataURL(f);
      });
      renderRows();
      toast('已批量上传 ' + files.length + ' 张图片（第 ' + batchRound + ' 格）');
    };
    fi.addEventListener('change', handler);
    fi.click();
  }

  /* ===== 配置 ===== */
  function getConfig() {
    // 旧版存储键名迁移（llt_gemini_* → llt_*）
    if (!localStorage.getItem('llt_key') && localStorage.getItem('llt_gemini_key')) {
      localStorage.setItem('llt_key', localStorage.getItem('llt_gemini_key'));
      localStorage.setItem('llt_base', localStorage.getItem('llt_gemini_base') || 'https://grsai.dakka.com.cn');
      localStorage.setItem('llt_model', localStorage.getItem('llt_gemini_model') || 'nano-banana-2');
    }
    return {
      key: (localStorage.getItem('llt_key') || '').trim(),
      base: (localStorage.getItem('llt_base') || 'https://grsai.dakka.com.cn').trim(),
      model: localStorage.getItem('llt_model') || 'nano-banana-2',
      res: (['1K', '2K', '4K'].includes(localStorage.getItem('llt_res')) ? localStorage.getItem('llt_res') : '4K'),
      concurrent: Math.max(1, Math.min(100, parseInt(localStorage.getItem('llt_concurrent')) || 5)),
      interval: Math.max(0, parseInt(localStorage.getItem('llt_interval')) || 0),
      requireBoth: localStorage.getItem('llt_require_both') !== '0'
    };
  }
  function saveSettings() {
    localStorage.setItem('llt_key', $('api-key').value.trim());
    localStorage.setItem('llt_base', $('base-url').value.trim());
    localStorage.setItem('llt_model', $('image-model').value);
    localStorage.setItem('llt_res', $('image-size').value);
    localStorage.setItem('llt_concurrent', String(Math.max(1, Math.min(100, parseInt($('concurrency').value) || 5))));
    localStorage.setItem('llt_interval', String(Math.max(0, parseInt($('interval').value) || 0)));
    localStorage.setItem('llt_require_both', $('require-both').checked ? '1' : '0');
    toast('设置已保存');
  }
  /* ===== GPT 聊天独立接口（与生图接口互不覆盖） ===== */
  function getChatConfig() {
    const k = (localStorage.getItem('llt_chat_key') || '').trim();
    const b = (localStorage.getItem('llt_chat_base') || '').trim();
    const m = localStorage.getItem('llt_chat_model') || 'gpt-5.6-terra';
    return {
      key: k || (localStorage.getItem('llt_key') || '').trim(),
      base: (b || localStorage.getItem('llt_base') || 'https://grsai.dakka.com.cn').trim(),
      model: m
    };
  }
  function saveChatSettings() {
    localStorage.setItem('llt_chat_key', $('chat-api-key').value.trim());
    localStorage.setItem('llt_chat_base', $('chat-base-url').value.trim());
    localStorage.setItem('llt_chat_model', $('chat-model-settings').value.trim() || 'gpt-5.6-terra');
    const cm = $('chat-model');
    if (cm) cm.value = localStorage.getItem('llt_chat_model');
    toast('聊天设置已保存');
  }
  /* 生图校验：一行必须同时具备提示词和上传图 */
  function rowReady(r, requireBoth) {
    if (!String(r.prompt || '').trim()) return '缺少提示词';
    if (requireBoth && !(r.images || []).filter(Boolean).length) return '缺少上传图';
    return null;
  }
  function normBase(b) { return (b || '').replace(/\/+$/, ''); }
  /* 兼容两种 base：https://api.openai.com 或 https://api.openai.com/v1，自动补 /v1 不重复 */
  function apiBase(b) { const s = normBase(b); return /\/v1$/i.test(s) ? s : s + '/v1'; }
  function currentRatio() { return activePill('ratio') || '1:1'; }
  const RATIO_SIZE = { '1:1':'1024x1024','4:3':'2048x1536','3:4':'1536x2048','16:9':'2048x1152','9:16':'1152x2048','3:2':'1536x1024','2:3':'1024x1536','auto':'1024x1024' };
  function maskKey(url, key) { return key ? url.split(key).join('***KEY***') : url; }
  async function readErrBody(resp) {
    try {
      const t = await resp.text();
      try { const j = JSON.parse(t); return (j.error && (j.error.message || j.error.status)) || (j.msg || '') || t.slice(0, 300); }
      catch (e) { return t.slice(0, 300); }
    } catch (e) { return ''; }
  }
  const sleep = ms => new Promise(r => setTimeout(r, ms));

  /* ===== 真实生图 ===== */
  function geminiGenerate(cfg, prompt, images, count) {
    if (/^nano-banana/.test(cfg.model)) return grsaiDrawGenerate(cfg, prompt, images, count);
    return openaiImagesGenerate(cfg, prompt, count);
  }
  /* nano-banana 走 Grsai 官方绘图接口 /v1/api/generate，imageSize 支持 1K/2K/4K */
  async function grsaiDrawGenerate(cfg, prompt, images, count) {
    const base = normBase(cfg.base);
    const url = base + '/v1/api/generate';
    const out = [];
    const refs = [];
    (images || []).filter(Boolean).forEach(u => refs.push(u));
    batchRefs.forEach(u => refs.push(u));
    const aspectRatio = currentRatio();
    const imageSize = (cfg.res && cfg.res !== 'auto' && cfg.res !== '默认') ? cfg.res : '1K';
    addLog('info', '【请求发起】' + cfg.model + ' ｜ POST ' + maskKey(url, cfg.key) + ' ｜ 参考图 ' + refs.length + ' 张 ｜ 比例 ' + aspectRatio + ' ｜ 分辨率 ' + imageSize);
    addLog('info', '提示词：' + (prompt || '').slice(0, 80) + ((prompt || '').length > 80 ? '…' : ''));
    for (let n = 0; n < count; n++) {
      const body = { model: cfg.model, prompt: prompt, images: refs, aspectRatio: aspectRatio, imageSize: imageSize, replyType: 'json' };
      addLog('info', '正在发送请求到接口…（第 ' + (n + 1) + '/' + count + ' 张）');
      const t0 = performance.now();
      let resp;
      try { resp = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + cfg.key }, body: JSON.stringify(body) }); }
      catch (e) { throw new Error('无法连接接口 ' + maskKey(url, cfg.key) + '：' + e.message); }
      let data = {};
      try { data = await resp.json(); } catch (e) { data = {}; }
      const secs = ((performance.now() - t0) / 1000).toFixed(1);
      if (!resp.ok) {
        const detail = data.error || (data.msg || (data.message || ''));
        addLog('error', '【响应】HTTP ' + resp.status + ' ｜ 耗时 ' + secs + 's ｜ ' + (detail || '无错误信息'));
        throw new Error('接口返回 ' + resp.status + '：' + (detail || '无错误信息') + ' ｜ 调用地址：' + maskKey(url, cfg.key) + '（请核对模型「' + cfg.model + '」与 base URL）');
      }
      let status = data.status;
      const taskId = data.id;
      if (status === 'running' || !status) {
        addLog('info', '任务已提交（id=' + (taskId || '-') + '），等待生成完成…');
        let tried = 0;
        while (tried++ < 90) {
          await sleep(3000);
          let qd = {};
          try {
            const q = await fetch(base + '/v1/api/result?id=' + encodeURIComponent(taskId || ''), { headers: { 'Authorization': 'Bearer ' + cfg.key } });
            if (q.ok) qd = await q.json();
          } catch (e) {}
          if (qd.progress !== undefined) addLog('info', '生成进度：' + qd.progress + '%');
          status = qd.status;
          if (status === 'succeeded') { data = qd; break; }
          if (status === 'failed' || status === 'violation') { data = qd; break; }
        }
      }
      addLog('ok', '【响应】HTTP ' + resp.status + ' ｜ 耗时 ' + secs + 's ｜ 任务状态 ' + (status || 'succeeded'));
      if (status === 'failed' || status === 'violation') {
        const err = (data && (data.error || data.message)) || '未知错误';
        addLog('error', '生成失败（' + status + '）：' + err);
        throw new Error('生成失败（' + status + '）：' + err);
      }
      const urls = ((data && data.results) || []).map(r => r && r.url).filter(Boolean);
      if (!urls.length) throw new Error('接口未返回图片（模型「' + cfg.model + '」可能不支持生图）');
      out.push(urls[0]);
      addLog('ok', '✔ 第 ' + (n + 1) + '/' + count + ' 张已返回：' + urls[0]);
    }
    addLog('ok', '本次接口调用完成：成功返回 ' + out.length + ' 张图片（分辨率 ' + imageSize + '）');
    return out;
  }
  /* gpt-image-2 走 OpenAI images/generations */
  async function openaiImagesGenerate(cfg, prompt, count) {
    const size = RATIO_SIZE[currentRatio()] || '1024x1024';
    const url = apiBase(cfg.base) + '/images/generations';
    addLog('info', '【请求发起】' + cfg.model + ' ｜ POST ' + maskKey(url, cfg.key) + ' ｜ ' + count + ' 张，' + size);
    const body = { model: cfg.model, prompt: prompt, n: count, size: size, response_format: 'url' };
    if (cfg.res && cfg.res !== 'auto') { body.resolution = cfg.res.toLowerCase(); addLog('info', '分辨率设置：' + cfg.res); }
    addLog('info', '正在发送请求到接口…');
    const t0 = performance.now();
    let resp;
    try { resp = await fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', 'Authorization': 'Bearer ' + cfg.key }, body: JSON.stringify(body) }); }
    catch (e) { throw new Error('无法连接接口 ' + maskKey(url, cfg.key) + '：' + e.message); }
    const secs = ((performance.now() - t0) / 1000).toFixed(1);
    if (!resp.ok) {
      const detail = await readErrBody(resp);
      addLog('error', '【响应】HTTP ' + resp.status + ' ｜ 耗时 ' + secs + 's ｜ ' + (detail || '无错误信息'));
      throw new Error('接口返回 ' + resp.status + '：' + (detail || '无错误信息') + ' ｜ 调用地址：' + maskKey(url, cfg.key) + '（请核对模型「' + cfg.model + '」与 base URL）');
    }
    addLog('ok', '【响应】HTTP ' + resp.status + ' ｜ 耗时 ' + secs + 's，正在解析返回数据…');
    const data = await resp.json();
    const urls = ((data.data) || []).map(d => d && d.url).filter(Boolean);
    if (!urls.length) throw new Error('接口未返回图片（请确认模型「' + cfg.model + '」支持生图）');
    urls.forEach((u, i) => addLog('ok', '✔ 第 ' + (i + 1) + '/' + urls.length + ' 张已返回：' + u));
    addLog('ok', '本次接口调用完成：成功返回 ' + urls.length + ' 张图片');
    return urls.slice(0, count);
  }

  /* 单行操作 */
  async function doAction(id, action) {
    const r = rows.find(x => x.id === id);
    if (!r) return;
    if (action === '生图片') {
      const cfg = getConfig();
      if (!cfg.key) { toast('请先在「设置」页填写并保存 API Key'); switchTab('settings'); return; }
      const reason = rowReady(r, cfg.requireBoth);
      if (reason) { toast('该行' + reason + '，无法生图'); r.status = 'error'; renderRows(); return; }
      openLog();
      logProgress('正在生成第 ' + (rows.indexOf(r) + 1) + ' 行…');
      r.status = 'generating'; renderRows();
      try {
        const urls = await geminiGenerate(cfg, r.prompt, r.images, 1);
        r.generated = [];          // 重新生成：先清空旧图再添加
        urls.forEach(u => r.generated.push(u));
        r.status = 'done';
        logProgress('完成：成功 1 行，失败 0 行');
        addLog('ok', '✔ 第 ' + (rows.indexOf(r) + 1) + ' 行完成（' + urls.length + ' 张）');
        toast('生图成功 ' + urls.length + ' 张');
      } catch (e) {
        r.status = 'error';
        logProgress('完成：成功 0 行，失败 1 行');
        addLog('error', '✘ 第 ' + (rows.indexOf(r) + 1) + ' 行失败：' + e.message);
        toast('生图失败：' + e.message);
      }
      renderRows();
    } else if (action === '下图片') {
      const urls = (r.generated || []).filter(Boolean);
      if (!urls.length) { toast('该行还没有生成结果'); return; }
      urls.forEach((u, i) => downloadImage(u, 'generated-' + r.id + '-' + (i + 1) + '.png'));
      toast('已下载 ' + urls.length + ' 张图片');
    } else if (action === '生视频') {
      toast('视频生成需要 Veo 视频 API（当前未接入），图片生成已真实可用');
    }
  }

  /* 批量出图（并发 worker 池）；onlyFailed=true 时仅重试失败的行 */
  function batchGenerate(autoDownload, onlyFailed) {
    const cfg = getConfig();
    if (!cfg.key) { toast('请先在「设置」页填写并保存 API Key'); switchTab('settings'); return; }
    openLog();
    const pending = [];
    rows.forEach(r => {
      if (onlyFailed) {                       // 重试模式：只挑失败行
        if (r.status === 'error') {
          const reason = rowReady(r, cfg.requireBoth);
          if (reason) addLog('warn', '⚠ 第 ' + (rows.indexOf(r) + 1) + ' 行' + reason + '，无法重试');
          else pending.push(r);
        }
        return;
      }
      const reason = rowReady(r, cfg.requireBoth);
      if (reason) {
        r.status = 'error';
        addLog('warn', '⚠ 第 ' + (rows.indexOf(r) + 1) + ' 行' + reason + '，已跳过');
      } else pending.push(r);
    });
    if (!pending.length) {
      renderRows();
      if (onlyFailed) { addLog('warn', '没有失败的行可重试'); toast('没有失败的行可重试'); }
      else { addLog('warn', '没有可生图的行（每行需提示词' + (cfg.requireBoth ? '和上传图' : '') + '）'); toast('没有可生图的行（每行需提示词' + (cfg.requireBoth ? '和上传图' : '') + '）'); }
      return;
    }
    const limit = cfg.concurrent;
    const interval = cfg.interval * 1000;
    const head = onlyFailed ? '重试失败出图' : '开始批量出图';
    addLog('info', head + '：' + pending.length + ' 行，并发 ' + limit + '，间隔 ' + cfg.interval + ' 秒');
    toast(head + '：' + pending.length + ' 行，并发 ' + limit);
    (async () => {
      let ok = 0, fail = 0, idx = 0;
      const progress = (extra) => logProgress('进度：' + (ok + fail) + '/' + pending.length + '（完成 ' + ok + ' · 失败 ' + fail + (extra ? ' · ' + extra : '') + '）');
      progress('进行中 0');
      const worker = async () => {
        while (idx < pending.length) {
          const i = idx++;
          const r = pending[i];
          r.status = 'generating'; renderRows();
          progress('进行中 ' + Math.min(limit, pending.length - idx));
          addLog('info', '▶ 第 ' + (rows.indexOf(r) + 1) + ' 行开始生成…');
          try {
            const urls = await geminiGenerate(cfg, r.prompt, r.images, 1);
            r.generated = [];       // 重新生成：先清空旧图再添加
            urls.forEach(u => r.generated.push(u));
            r.status = 'done'; ok++;
            addLog('ok', '✔ 第 ' + (rows.indexOf(r) + 1) + ' 行完成（' + urls.length + ' 张）');
            if (autoDownload) urls.forEach((u, j) => downloadImage(u, 'generated-' + r.id + '-' + (j + 1) + '.png'));
          } catch (e) {
            r.status = 'error'; fail++;
            addLog('error', '✘ 第 ' + (rows.indexOf(r) + 1) + ' 行失败：' + e.message);
            toast('第 ' + (rows.indexOf(r) + 1) + ' 行失败：' + e.message);
          }
          progress('');
          renderRows();
          if (interval > 0) await sleep(interval);
        }
      };
      const workers = [];
      for (let w = 0; w < Math.min(limit, pending.length); w++) workers.push(worker());
      await Promise.all(workers);
      logProgress('完成：成功 ' + ok + ' 行，失败 ' + fail + ' 行');
      addLog('ok', '批量出图结束：成功 ' + ok + ' 行，失败 ' + fail + ' 行');
      toast('批量出图完成：成功 ' + ok + ' 行，失败 ' + fail);
    })();
  }
  function batchDownload() {
    const all = rows.reduce((a, r) => a.concat((r.generated || []).filter(Boolean).map(u => ({ u, id: r.id }))), []);
    if (!all.length) { toast('还没有生成结果'); return; }
    all.forEach((it, i) => downloadImage(it.u, 'generated-' + it.id + '-' + (i + 1) + '.png'));
    toast('已下载 ' + all.length + ' 张图片');
  }
  async function downloadImage(u, filename) {
    if (String(u).indexOf('data:') === 0) { downloadDataUrl(u, filename); return; }
    // 1) 先走 CORS fetch → blob 下载
    try {
      const r = await fetch(u, { mode: 'cors' });
      if (r.ok) { const b = await r.blob(); downloadDataUrl(b, filename); return; }
    } catch (e) {}
    // 2) CORS 不可用时用 no-cors 取不透明 blob，objectURL 仍可触发下载
    try {
      const r = await fetch(u, { mode: 'no-cors' });
      const b = await r.blob();
      downloadDataUrl(b, filename);
      return;
    } catch (e) {}
    // 3) 最后兜底：新窗口打开，供用户手动保存
    addLog('warn', '自动下载失败，已在新窗口打开图片，可右键另存：' + u);
    window.open(u, '_blank');
  }
  function downloadDataUrl(dataUrl, filename) {
    const a = document.createElement('a');
    let href = dataUrl;
    let revoke = null;
    if (dataUrl instanceof Blob) {          // Blob 必须先转成 objectURL，否则 href 会变成 "[object Blob]"
      href = URL.createObjectURL(dataUrl);
      revoke = href;
    }
    a.href = href; a.download = filename;
    a.rel = 'noopener';
    document.body.appendChild(a); a.click(); a.remove();
    if (revoke) setTimeout(() => URL.revokeObjectURL(revoke), 4000);
  }

  /* ===== 导入 / 清空 ===== */
  $('import-file').addEventListener('change', function () {
    const f = this.files && this.files[0];
    if (!f) return;
    const reader = new FileReader();
    reader.onload = () => {
      const text = String(reader.result || '');
      const lines = text.split(/\r?\n/).map(l => l.trim()).filter(l => l && !/^(序号|提示词|标题)/.test(l));
      if (!lines.length) { toast('未解析到提示词'); return; }
      rows = []; rowSeq = 1; batchRound = 0;
      lines.forEach(l => { const r = freshRow(); r.prompt = l; rows.push(r); });
      renderRows();
      toast('已导入 ' + lines.length + ' 条提示词');
    };
    reader.readAsText(f, 'utf-8');
    this.value = '';
  });
  const CLEAR_OPS = ['清空所有', '清空提示词', '清空生成图', '清空上传图', '清空无图行', '导出提示词表格'];
  function toggleDD(id) {
    const el = $(id);
    const will = el.hidden;
    document.querySelectorAll('.dd-menu').forEach(d => d.hidden = true);
    if (will) el.hidden = false;
  }
  document.addEventListener('click', e => {
    if (!e.target.closest('.dd-wrap')) document.querySelectorAll('.dd-menu').forEach(d => d.hidden = true);
  });
  CLEAR_OPS.forEach(op => {
    const d = document.createElement('div');
    d.className = 'dd-item';
    d.textContent = op;
    d.onclick = () => {
      $('clearDD').hidden = true;
      if (op === '清空所有') { rows = []; rowSeq = 1; batchRound = 0; }
      else if (op === '清空提示词') rows.forEach(r => r.prompt = '');
      else if (op === '清空生成图') rows.forEach(r => r.generated = []);
      else if (op === '清空上传图') { rows.forEach(r => r.images = []); batchRound = 0; }
      else if (op === '清空无图行') { rows = rows.filter(r => (r.images || []).filter(Boolean).length); batchRound = 0; }
      else if (op === '导出提示词表格') {
        const lines = rows.map((r, i) => (i + 1) + '\t' + (r.prompt || '')).join('\n');
        const blob = new Blob(['序号\t提示词\n' + lines], { type: 'text/plain;charset=utf-8' });
        const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = '提示词表格.txt';
        document.body.appendChild(a); a.click(); a.remove();
        toast('已导出提示词表格');
      }
      renderRows();
      if (!rows.length) toast('列表已清空');
    };
    $('clearDD').appendChild(d);
  });

  /* ===== 运行日志（实时） ===== */
  function addLog(type, msg) {
    const area = $('logArea');
    if (!area) return;
    const line = document.createElement('div');
    line.className = 'log-line ' + (type || 'info');
    line.textContent = '[' + new Date().toLocaleTimeString() + '] ' + msg;
    area.appendChild(line);
    area.scrollTop = area.scrollHeight;
  }
  /* 顶部实时进度条：随生成动态更新 */
  function logProgress(text) {
    let el = $('logProgress');
    if (!el) {
      el = document.createElement('div');
      el.id = 'logProgress';
      el.className = 'log-line progress';
      const area = $('logArea');
      if (area) area.insertBefore(el, area.firstChild);
    }
    el.textContent = text;
  }
  function openLog() { $('logModal').hidden = false; }
  function closeLog() { $('logModal').hidden = true; }
  function clearLog() { $('logArea').innerHTML = '<div class="log-line time">[系统] 日志已清空</div>'; }

  /* ===== 统计 ===== */
  function openStats() {
    const withImg = rows.filter(r => (r.images || []).filter(Boolean).length).length;
    const withGen = rows.reduce((a, r) => a + (r.generated || []).filter(Boolean).length, 0);
    const ok = rows.filter(r => r.status === 'done').length;
    const err = rows.filter(r => r.status === 'error').length;
    $('statsBody').innerHTML =
      '<div>任务总数：<b>' + rows.length + '</b></div>' +
      '<div>含上传图行数：<b>' + withImg + '</b></div>' +
      '<div>已生成图片总数：<b>' + withGen + '</b></div>' +
      '<div>成功行：<b style="color:var(--success)">' + ok + '</b></div>' +
      '<div>失败行：<b style="color:var(--danger)">' + err + '</b></div>';
    $('statsModal').hidden = false;
  }
  function closeStats() { $('statsModal').hidden = true; }

  /* ===== 抖音热榜（真实数据，由 AI 按关键词+筛选条件搜索后更新） ===== */
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
  function dyBuildRequestText(){
    const sortName = { default:'综合', likes:'点赞最多', favorites:'收藏最多', plays:'播放最多', comments:'评论最多' }[dyData.sort] || '综合';
    const timeName = { all:'不限', today:'今天', week:'本周', month:'本月' }[dyData.timeRange] || '不限';
    const durName = { all:'不限', short:'0-1分钟', medium:'1-5分钟', long:'5分钟以上' }[dyData.duration] || '不限';
    return '帮我搜抖音热门视频：\n关键词：' + (dyData.keyword || '（未填）') + '\n排序：' + sortName + '\n时间：' + timeName + '\n时长：' + durName;
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
  async function dySearch(){
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
    if (p) { dyData.sort = p.dataset.sort; dyUpdateHash(); renderDy(); dyShowRequest(); return; }
    const t = e.target.closest ? e.target.closest('#dy-time .pill') : null;
    if (t) { dyData.timeRange = t.dataset.time; dyUpdateHash(); renderDy(); dyShowRequest(); return; }
    const d = e.target.closest ? e.target.closest('#dy-duration .pill') : null;
    if (d) { dyData.duration = d.dataset.duration; dyUpdateHash(); renderDy(); dyShowRequest(); return; }
  });

  /* ===== 标签页 / 主题 / toast ===== */
  function switchTab(tab) {
    document.querySelectorAll('.tab').forEach(b => b.classList.toggle('active', b.dataset.panel === tab));
    document.querySelectorAll('.panel').forEach(p => p.classList.toggle('active', p.id === tab + '-panel'));
  }
  document.querySelectorAll('.tab').forEach(b => b.addEventListener('click', () => switchTab(b.dataset.panel)));
  function setTheme(btn, theme) {
    document.querySelectorAll('.theme-card').forEach(x => x.classList.remove('selected'));
    btn.classList.add('selected');
    document.body.style.background = theme === 'dim' ? '#eef3fb' : '';
    toast(theme === 'dim' ? '已切换雾蓝主题' : '已切换浅色主题');
  }
  function toast(msg) {
    const t = $('toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => t.classList.remove('show'), 2200);
  }

  /* ===== 初始化 ===== */
  (function init() {
    try {
    const cfg = getConfig();
    $('api-key').value = cfg.key;
    $('base-url').value = cfg.base;
    $('image-model').value = cfg.model;
    $('image-size').value = cfg.res;
    if (!['1K', '2K', '4K'].includes(localStorage.getItem('llt_res'))) localStorage.setItem('llt_res', cfg.res);   // 旧值(auto)迁移为4K
    $('concurrency').value = cfg.concurrent;
    $('interval').value = cfg.interval;
    const rb = $('require-both');
    if (rb) rb.checked = cfg.requireBoth;
    loadRows();                                  // 恢复上次保存的上传图/生成图/提示词
    renderRows();
    /* 九宫格页：恢复参考图与结果、绑定文件上传 */
    try { const r1 = JSON.parse(localStorage.getItem('llt_nine_refs') || '[]'); if (Array.isArray(r1)) nineRefs = r1.filter(Boolean); } catch (e) {}
    try { const r2 = JSON.parse(localStorage.getItem('llt_nine_results') || '[]'); if (Array.isArray(r2)) nineResults = r2.filter(Boolean); } catch (e) {}
    renderNineList(); renderNineResult();
    const nf = $('nine-files');
    if (nf) nf.addEventListener('change', () => {
      const files = Array.from(nf.files || []);
      nf.value = '';
      if (!files.length) return;
      files.forEach(f => {
        const reader = new FileReader();
        reader.onload = () => { nineRefs.push(reader.result); renderNineList(); };
        reader.readAsDataURL(f);
      });
      toast('已添加 ' + files.length + ' 张鞋子参考图');
    });
    /* GPT 聊天：恢复对话记录、模型选择、回车发送、输入框自适应 */
    /* GPT 聊天：恢复会话、模型选择、回车发送、输入框自适应 */
    try {
      const stored = JSON.parse(localStorage.getItem('llt_convs') || '[]');
      if (Array.isArray(stored) && stored.length) {
        convs = stored.filter(x => x && Array.isArray(x.msgs));
        const savedId = parseInt(localStorage.getItem('llt_cur_conv'), 10);
        const cur = convs.find(x => x.id === savedId) || convs[0];
        if (cur) { curConvId = cur.id; chatMsgs = cur.msgs; }
      }
    } catch (e) {}
    if (!convs.length) { const c0 = { id: Date.now(), title: '', msgs: [] }; convs.push(c0); curConvId = c0.id; chatMsgs = c0.msgs; }
    const cm = $('chat-model');
    const cms = $('chat-model-settings');
    const chatCfg = getChatConfig();
    if ($('chat-base-url')) $('chat-base-url').value = (localStorage.getItem('llt_chat_base') || '').trim() || chatCfg.base;
    if ($('chat-api-key')) $('chat-api-key').value = localStorage.getItem('llt_chat_key') || '';
    if (cm) { const saved = localStorage.getItem('llt_chat_model'); if (saved) cm.value = saved; cm.addEventListener('change', () => { localStorage.setItem('llt_chat_model', cm.value); if (cms) cms.value = cm.value; }); }
    if (cms) { cms.value = localStorage.getItem('llt_chat_model') || 'gpt-5.6-terra'; cms.addEventListener('change', () => { localStorage.setItem('llt_chat_model', cms.value); if (cm) cm.value = cms.value; }); }
    renderSidebar();
    dyFromHash();
    renderDy();
    dyShowRequest();
    renderChat();
    const ci = $('chat-input');
    const csBtn = $('chat-send');
    window.syncSend = function () {
      if (ci) {
        ci.style.height = 'auto';
        ci.style.height = Math.min(ci.scrollHeight, 160) + 'px';
      }
      if (csBtn) csBtn.disabled = !((ci && ci.value.trim()) || chatFiles.length);
    };
    if (ci) {
      ci.addEventListener('keydown', e => {
        if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendChat(); }
      });
      ci.addEventListener('input', syncSend);
    }
    syncSend();
    if (rows.length) addLog('time', '[系统] 已恢复上次保存的任务数据（' + rows.length + ' 行）');
    else addLog('time', '[系统] 编辑器已加载，配置好 API Key 即可真实出图');
    } catch (err) { window.__initErr = err && err.message; console.error('[init]', err); }
  })();
