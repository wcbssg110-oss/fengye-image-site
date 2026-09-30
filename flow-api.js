(() => {
  'use strict';
  const el = id => document.getElementById('flow-' + id);
  const say = message => { el('status').textContent = message; };
  el('base').value = localStorage.getItem('fengye_flow_base') || '';
  el('key').value = sessionStorage.getItem('fengye_flow_key') || '';
  function config() {
    const url = new URL(el('base').value.trim());
    if (url.protocol !== 'https:' && !(url.protocol === 'http:' && ['localhost','127.0.0.1'].includes(url.hostname))) throw new Error('请填写 HTTPS 后台地址；仅本机测试可使用 HTTP');
    if (url.username || url.password || url.search || url.hash) throw new Error('后台地址不能包含密码或查询参数');
    const key = el('key').value.trim();
    if (!key) throw new Error('请填写 Flow2API API Key');
    return {base: url.href.replace(/\/+$/, '').replace(/\/v1$/, ''), key};
  }
  async function request(cfg, path, body) {
    let response;
    try {
      response = await fetch(cfg.base + path, {method: body ? 'POST' : 'GET', headers: {'Authorization': 'Bearer ' + cfg.key, ...(body ? {'Content-Type':'application/json'} : {})}, body: body ? JSON.stringify(body) : undefined, signal: AbortSignal.timeout(30000)});
    } catch { throw new Error('后台无法连接，请检查地址、服务和跨域配置。若刚提交任务，请先查看后台历史，避免重复生成。'); }
    const data = await response.json();
    if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '后台请求失败（HTTP ' + response.status + '）');
    return data;
  }
  el('save').onclick = () => {try {const cfg = config(); localStorage.setItem('fengye_flow_base', cfg.base); sessionStorage.setItem('fengye_flow_key', cfg.key); say('配置已保存');} catch(e) {say(e.message);} };
  el('test').onclick = async () => {try {say('正在检查连接…'); await request(config(), '/v1/models'); say('API 地址和 Key 验证成功；生成能力仍需实际任务验证');} catch(e) {say(e.message);} };
  el('generate').onclick = async () => {
    const button = el('generate'); button.disabled = true;
    try {
      const cfg = config(), prompt = el('prompt').value.trim(), n = Number(el('count').value);
      if (!prompt) throw new Error('请填写提示词');
      if (!Number.isInteger(n) || n < 1 || n > 4) throw new Error('图片数量须为 1 到 4');
      el('results').replaceChildren(); say('正在提交…');
      const submitted = await request(cfg, '/v1/images/generations', {prompt, model: el('model').value, n, size: el('ratio').value});
      if (!submitted.id) throw new Error('后台未返回任务编号');
      const path = '/v1/tasks/' + encodeURIComponent(submitted.id);
      for (let i = 0; i < 200; i++) {
        await new Promise(resolve => setTimeout(resolve, 3000));
        const task = await request(cfg, path);
        say('任务 ' + submitted.id + '：' + task.status + ' · ' + (task.progress || 0) + '%');
        if (task.status === 'failed' || task.status === 'cancelled') throw new Error(task.error || '生成失败');
        if (task.status !== 'succeeded') continue;
        const outputs = (task.outputs || []).filter(out => out.type === 'image' && out.url);
        if (!outputs.length) throw new Error('任务结束，但没有返回图片');
        for (const out of outputs) {
          const url = new URL(out.url, cfg.base + '/');
          if (!['https:','http:'].includes(url.protocol)) throw new Error('后台返回了不支持的图片地址');
          const link = document.createElement('a'); link.href = url.href; link.target = '_blank'; link.rel = 'noopener noreferrer';
          const img = document.createElement('img'); img.src = url.href; img.alt = 'Flow 生成图片'; img.style.maxWidth = '320px'; img.style.margin = '8px';
          img.onerror = () => say('生成已完成，但图片未加载，请检查后台文件地址');
          link.append(img); el('results').append(link);
        }
        say('生成完成，共 ' + outputs.length + ' 张'); return;
      }
      throw new Error('等待超过 10 分钟；任务可能仍在执行，请到后台查看，避免重复提交');
    } catch(e) {say(e.message);} finally {button.disabled = false;}
  };
})();
