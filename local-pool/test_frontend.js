const fs = require('fs');
const vm = require('vm');
const assert = require('assert');
const path = require('path');
const html = fs.readFileSync(path.join(__dirname, '..', 'index.html'), 'utf8');
for (const match of html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)) new vm.Script(match[1]);
const source = html.slice(html.indexOf('  function gmiImagePoolConfig()'), html.indexOf('  async function savePoolConnection()'));
const calls = [];
const context = {
  localStorage: {getItem: () => null}, Headers,
  fetch: (url, options) => {calls.push({url, options}); return Promise.resolve({ok:true});},
  poolConnectionConfig: () => ({base:'https://original.example', token:'original-token'})
};
vm.createContext(context);
vm.runInContext(source, context);
(async () => {
  await context.gmiServiceFetch('/api/gmi-image?edits=1&pool=gmi8791', '', {method:'POST'});
  assert.equal(calls.at(-1).url, 'http://127.0.0.1:8791/api/gmi-image?edits=1&pool=gmi8791');
  assert.equal(calls.at(-1).options.headers.get('X-Pool-Token'), 'monid-pool');
  await context.gmiServiceFetch('/api/gmi-image?task_id=gmi8791_abc', '', {});
  assert(calls.at(-1).url.startsWith('http://127.0.0.1:8791/'));
  await context.gmiServiceFetch('/api/gmi-image?task_id=old_leap_task', '', {});
  assert(calls.at(-1).url.startsWith('http://127.0.0.1:8796/'));
  console.log('PASS: script syntax, GMI submission/poll routing, original task routing');
})();
