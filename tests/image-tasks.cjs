const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const html = fs.readFileSync('index.html', 'utf8');
function section(start, end) { return html.slice(html.indexOf(start), html.indexOf(end, html.indexOf(start))); }
const el = () => ({style:{}, append(){}, remove(){}, replaceChildren(){}});
const task = () => ({state:'queued', meta:{}, status:el(), card:el(), media:el()});
const tasks = new Map();
let response, calls = [], timers = [], rejected, retries=0;
const context = vm.createContext({
  imageTasks:tasks, document:{createElement:el}, Headers, AbortSignal, Promise, Error, Set,
  localStorage:{getItem:k => k==='fengye_pool_enabled'?'1':null},
  sessionStorage:{getItem:()=>''}, window:{},
  gmiImagePoolConfig:()=>({base:'http://127.0.0.1:8791',token:'local-test'}),
  poolConnectionConfig:()=>({base:'https://configured.example',token:'test'}),
  fetch:async (url,options)=>{calls.push({url,options});return response;},
  updateImageTaskBadge(){}, collectImageUrls(v,out){for(const i of Array.isArray(v)?v:[])if(i.url)out.push(i.url);},
  extractPlainText:()=>'', setTimeout:fn=>{timers.push(fn);},
});
vm.runInContext(section('  function gmiServiceFetch(', '  async function savePoolConnection('),context);
vm.runInContext(section('  function addImageTaskResume(', '  /* gpt-image-2：'),context);
(async()=>{
  response={ok:true,json:async()=>({status:'running'})};
  await context.gmiServiceFetch('/api/gmi-image?pool=gmi8791','');
  assert.match(calls.pop().url,/127\.0\.0\.1:8791/);
  await context.gmiServiceFetch('/api/gmi-image?task_id=gmi8791_test','');
  assert.match(calls.pop().url,/127\.0\.0\.1:8791/);
  await context.gmiServiceFetch('/api/gmi-image?task_id=old','');
  assert.match(calls.pop().url,/configured\.example/);
  let t=task();tasks.set('test',t);t.reject=e=>{rejected=e;};
  response={ok:false,status:503};
  for(let i=0;i<5;i++)await context.pollImageGeneration('test',i);
  assert.equal(t.state,'reconnecting');assert.equal(rejected,undefined);
  assert.equal(timers.length,5);assert.equal(t.queryFailures,5);
  t=task();tasks.set('empty',t);response={ok:true,json:async()=>({status:'completed',data:[]})};
  await context.pollImageGeneration('empty',0);assert.equal(t.state,'failed');
  t=task();tasks.set('error',t);response={ok:true,json:async()=>({status:'error',error:'quota'})};
  await context.pollImageGeneration('error',0);assert.equal(t.state,'failed');assert.equal(t.error,'quota');
  t=task();tasks.set('ok',t);response={ok:true,json:async()=>({status:'completed',data:[{url:'https://example.com/image.png'}]})};
  await context.pollImageGeneration('ok',0);assert.equal(t.state,'completed');assert.equal(t.urls.length,1);
  context.localStorage.getItem=()=>JSON.stringify([{id:'saved-failed',state:'failed',error:'saved quota error',meta:{}}]);
  context.migratePoolMedia=(_k,v)=>v;context.isLocalMediaUrl=()=>true;
  context.createImageTaskCard=id=>tasks.set(id,task());
  const realPoll=context.pollImageGeneration;let restoredPolls=0;
  context.pollImageGeneration=async()=>{restoredPolls++;};
  vm.runInContext(section('  function restoreImageTasks()', '  function addImageTaskResume('),context);
  context.restoreImageTasks();assert.equal(restoredPolls,0);
  assert.equal(tasks.get('saved-failed').error,'saved quota error');
  context.pollImageGeneration=realPoll;
  context.getConfig=()=>({provider:'gmi'});context.isGmiImageModel=()=>true;
  context.gmiImageGenerate=async()=>{throw new Error('uncertain submission');};
  vm.runInContext(section('  function geminiGenerate(', '  async function grsaiDrawGenerate('),context);
  await assert.rejects(context.geminiGenerate({},'',[],1),e=>e.noRetry===true);
  console.log('PASS: pool routing, transient timeout recovery, empty completion, error status, image success, no duplicate submission');
})().catch(e=>{console.error(e);process.exitCode=1;});

