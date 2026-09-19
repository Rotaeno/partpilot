/* DOM simulation + actual local API. This is NOT a browser or visual test. */
const { JSDOM, VirtualConsole } = require('jsdom');
const fs = require('node:fs');
const path = require('node:path');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const base = process.env.PARTPILOT_TEST_URL || 'http://127.0.0.1:8765';
const results = [], owned = new Set();
let dom, injectFailure = false, exported = false, initialId;
function check(name, condition) { assert.ok(condition, name); results.push({name,passed:true}); }
async function waitUntil(fn, label) {
  const deadline = Date.now()+6000;
  while (Date.now()<deadline) { if(fn()) return; await new Promise(r=>setTimeout(r,20)); }
  throw new Error('Timed out: '+label);
}
async function main() {
  const pre = await fetch(base+'/api/sessions').then(r=>r.json());
  const fresh = await fetch(base+'/api/sessions',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'}).then(r=>r.json());
  initialId=fresh.id; owned.add(fresh.id);
  const vc = new VirtualConsole();
  const errors=[];
  vc.on('jsdomError',e=>{if(!e.message.includes('navigation'))errors.push(e.message);});
  dom = new JSDOM(fs.readFileSync(path.join(root,'static/index.html'),'utf8'),{url:base,runScripts:'outside-only',pretendToBeVisual:true,virtualConsole:vc});
  const w=dom.window,d=w.document;
  // Real HTTP fetch requires Node's signal brand, unlike JSDOM's DOM-only signal.
  w.AbortController=global.AbortController;
  w.AbortSignal=global.AbortSignal;
  w.localStorage.setItem('partpilot.session',initialId);
  w.HTMLDialogElement.prototype.showModal=function(){this.open=true;};
  w.HTMLDialogElement.prototype.close=function(){this.open=false;};
  w.URL.createObjectURL=()=>{exported=true;return 'blob:partpilot-test';};
  w.URL.revokeObjectURL=()=>{};
  w.fetch=async (url,opts={})=>{
    if(injectFailure&&String(url).endsWith('/turn')){injectFailure=false;return new Response(JSON.stringify({detail:'注入的服务异常'}),{status:503,headers:{'Content-Type':'application/json'}});}
    const r=await fetch(new URL(url,base),opts);
    if(url==='/api/sessions'&&opts.method==='POST'&&r.ok)owned.add((await r.clone().json()).id);
    return r;
  };
  w.eval(fs.readFileSync(path.join(root,'static/app.js'),'utf8'));
  const $=id=>d.getElementById(id);
  const idle=()=>d.querySelector('main').getAttribute('aria-busy')==='false';
  await waitUntil(()=>idle()&&$('catalog-count').textContent==='72','init');
  check('initial offline and synthetic labels',$('mode-badge').textContent.includes('离线规则演示')&&$('mode-badge').textContent.includes('合成数据'));
  check('welcome and actionable input',!!$('message-input')&&$('message-list').textContent.includes('配件'));
  async function submit(text){$('message-input').value=text;$('message-input').dispatchEvent(new w.Event('input',{bubbles:true}));$('message-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));await waitUntil(idle,'send '+text);}
  async function click(el,label){assert.ok(el,label);el.click();await waitUntil(idle,label);}
  await submit('找液压回油滤芯');
  check('missing information asks for equipment',$('session-status').textContent==='补充信息'&&$('message-list').textContent.includes('先补充设备编码'));
  await click($('edit-equipment'),'equipment dialog');
  $('equipment-select').value='DEMO-EX-001';
  $('equipment-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
  await waitUntil(idle,'set equipment');
  check('conditions render without automatic search',$('conditions-list').textContent.includes('DEMO-EX-001')&&$('session-status').textContent==='待启动检索');
  await click($('start-search'),'search');
  check('database candidates rendered',!!d.querySelector('[data-detail="PP-1001"]')&&!!d.querySelector('[data-detail="PP-1002"]'));
  await submit('重量不超过2公斤');
  check('old results removed after change',!d.querySelector('[data-detail="PP-1002"]')&&$('session-status').textContent==='待启动检索');
  await click($('start-search'),'refined search');
  check('refinement matches actual catalog',!!d.querySelector('[data-detail="PP-1001"]')&&!d.querySelector('[data-detail="PP-1002"]'));
  await click(d.querySelector('[data-detail="PP-1001"]'),'details');
  check('detail includes hierarchy and provenance',$('detail-dialog').open&&$('detail-content').textContent.includes('装配层级路径')&&$('detail-content').textContent.includes('合成演示数据'));
  await click($('detail-content').querySelector('[data-select="PP-1001"]'),'ask confirmation');
  const before=await fetch(base+`/api/sessions/${initialId}`).then(r=>r.json());
  check('confirmation dialog does not write',$('confirm-dialog').open&&before.selection===null);
  await click($('confirm-action'),'commit confirmation');
  const after=await fetch(base+`/api/sessions/${initialId}`).then(r=>r.json());
  check('confirmed selection persisted',after.selection?.part_id==='PP-1001'&&$('session-status').textContent==='已确认保存');
  check('confirmed candidate disabled',d.querySelector('[data-select="PP-1001"]').disabled);
  await click($('export-session'),'export');
  check('export action produces download',exported);
  await click($('new-session'),'new session');
  check('new session is isolated',!$('conditions-list').textContent.includes('DEMO-EX-001'));
  await click(d.querySelector(`[data-history="${initialId}"]`),'restore history');
  check('history restored confirmed record',$('session-status').textContent==='已确认保存');
  await click(d.querySelector(`[data-rename="${initialId}"]`),'rename');
  $('rename-input').value='UI验收记录';
  $('rename-form').dispatchEvent(new w.Event('submit',{bubbles:true,cancelable:true}));
  await waitUntil(idle,'rename commit');
  check('history rename persisted',(await fetch(base+`/api/sessions/${initialId}`).then(r=>r.json())).title==='UI验收记录');
  await submit('重量至少100公斤');
  check('conflict displayed',$('session-status').textContent==='条件待澄清');
  await submit('重量不限');
  await submit('重量至少100公斤');
  await click($('start-search'),'empty search');
  check('empty state has measured diagnosis',$('result-content').textContent.includes('没有找到')&&$('result-content').textContent.includes('移除'));
  await click(d.querySelector('[data-action="fallback"]'),'fallback');
  check('fallback leaves device only',!$('conditions-list').textContent.includes('重量下限')&&$('session-status').textContent==='候选已就绪');
  injectFailure=true;
  await click($('start-search'),'injected HTTP failure');
  check('HTTP failure visible to user',$('toast').textContent.includes('注入的服务异常'));
  await submit('<img src=x onerror="alert(1)">找滤芯');
  check('user input is escaped',!d.querySelector('img[src="x"]')&&$('message-list').textContent.includes('<img'));
  check('trace is visible',$('trace-list').textContent.includes('search_parts'));
  check('mobile history includes renamed session',$('mobile-history-list').textContent.includes('UI验收记录'));
  const disposable=[...owned].find(id=>id!==initialId);
  await click(d.querySelector(`[data-delete="${disposable}"]`),'ask delete');
  check('delete requires explicit confirmation',$('confirm-dialog').open&&(await fetch(base+`/api/sessions/${disposable}`)).status===200);
  await click($('confirm-action'),'delete history');
  check('history delete removes only selected test session',(await fetch(base+`/api/sessions/${disposable}`)).status===404&&(await fetch(base+`/api/sessions/${initialId}`)).status===200);
  check('no unexpected script errors',errors.length===0);
  fs.writeFileSync(path.join(root,'artifacts/ui-dom-snapshot.html'),dom.serialize());
  const kept=await fetch(base+'/api/sessions').then(r=>r.json());
  check('preexisting histories untouched',pre.items.every(x=>kept.items.some(y=>y.id===x.id)));
}
(async()=>{
  let error;
  try{await main();}catch(e){error=e;console.error(e.stack);if(dom){console.error(dom.window.document.getElementById('toast').textContent);fs.writeFileSync(path.join(root,'artifacts/ui-dom-failure.html'),dom.serialize());}process.exitCode=1;}
  finally{
    if(dom)dom.window.close();
    for(const id of owned){await fetch(base+`/api/sessions/${id}`,{method:'DELETE'});}
    const report={kind:'JSDOM script + actual local HTTP API; NOT browser/visual verification',passed:!error,assertions:results,error:error?.message||null,external_model_calls:0};
    fs.mkdirSync(path.join(root,'artifacts'),{recursive:true});
    fs.writeFileSync(path.join(root,'artifacts/ui-dom-report.json'),JSON.stringify(report,null,2));
    console.log(JSON.stringify({passed:!error,checks:results.length,error:error?.message||null}));
  }
})();
