(() => {
window.fengyeFlowGenerate = async (cfg,prompt,images,count,ratio,say=()=>{}) => {
 const u=new URL(cfg.base);if(!['https:','http:'].includes(u.protocol))throw Error('请填写 Flow 后台地址');
 if(!cfg.key)throw Error('请填写 Flow API Key');
 const base=u.href.replace(/\/+$/,'').replace(/\/v1$/,'');
 const model=({'nano-banana-2':'nano_banana','nano-banana-pro':'banana_pro','nano_banana':'nano_banana','banana_pro':'banana_pro'})[cfg.model];
 if(!model)throw Error('请选择 Flow Nano Banana 或 Banana Pro');
 if(images.length>8)throw Error('Flow 最多支持 8 张参考图');
 async function request(path,body){
 let r;try{r=await fetch(base+path,{method:body?'POST':'GET',headers:{Authorization:'Bearer '+cfg.key,...(body?{'Content-Type':'application/json'}:{})},body:body?JSON.stringify(body):undefined,signal:AbortSignal.timeout(30000)});}catch{throw Error('Flow 后台无法连接；已提交任务请到后台查看，避免重复生成');}
 const d=await r.json();if(!r.ok)throw Error(typeof d.detail==='string'?d.detail:'Flow HTTP '+r.status);return d;
 }
 const task=await request('/v1/images/generations',{prompt,model,n:count||1,size:ratio||'1:1',extra:{images}});
 if(!task.id)throw Error('Flow 未返回任务编号');say('Flow 任务：'+task.id);
 for(let i=0;i<200;i++){
 await new Promise(r=>setTimeout(r,3000));const state=await request('/v1/tasks/'+encodeURIComponent(task.id));
 if(['failed','cancelled'].includes(state.status))throw Error(state.error||'Flow 生图失败');
 if(state.status!=='succeeded')continue;
 const urls=(state.outputs||[]).filter(o=>o.type==='image'&&o.url).map(o=>new URL(o.url,base+'/').href);
 if(!urls.length)throw Error('Flow 未返回图片');return urls;
 }
 throw Error('等待超时，请查看 Flow 任务 '+task.id+'，避免重复提交');
};
})();
