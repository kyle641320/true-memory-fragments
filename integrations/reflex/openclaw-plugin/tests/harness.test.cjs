const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const test=require('node:test');
const {createJiti}=require('jiti');
const m=createJiti(__filename,{interopDefault:true})(path.resolve(__dirname,'../index.ts'));

const stable=v=>Array.isArray(v)?`[${v.map(stable).join(',')}]`:v&&typeof v==='object'?`{${Object.keys(v).sort().map(k=>`${JSON.stringify(k)}:${stable(v[k])}`).join(',')}}`:JSON.stringify(v);
const fp=(tool,params,rel)=>crypto.createHash('sha256').update(stable({tool_name:tool,path:rel,input:params})).digest('hex');
function fixture(options={}){
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'tmf-oc-')),repo=path.join(root,'repo'),state=path.join(root,'external','.tmf');
  fs.mkdirSync(repo);fs.mkdirSync(state,{recursive:true});fs.writeFileSync(path.join(repo,'dep.py'),'def quote(item, qty, currency):\n    return item\n');fs.writeFileSync(path.join(repo,'app.py'),'from dep import quote\n');fs.writeFileSync(path.join(repo,'other.py'),'x=1\n');
  const py=path.join(root,'fake-hook.py');
  fs.writeFileSync(py,`#!/usr/bin/env python3
import hashlib,json,os,sys
p=json.loads(sys.stdin.read()); params=p.get('tool_input') or {}; tool=p.get('tool_name','').lower(); repo=${JSON.stringify(repo)}; state=${JSON.stringify(state)}
def stable(v):
 return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False)
def blob(rel):
 try:
  b=open(os.path.join(repo,rel),'rb').read(); return hashlib.sha1(b'blob '+str(len(b)).encode()+b'\\0'+b).hexdigest()
 except: return None
def fingerprint(t,x,rel): return hashlib.sha256(stable({'tool_name':t,'path':rel,'input':x}).encode()).hexdigest()
warm_path=os.path.join(state,'warm')
warm=os.path.exists(warm_path) and open(warm_path).read().strip()==str(blob('dep.py'))
text=stable(params)
stale=('quote(' in text and 'USD' not in text) or (tool in ('edit','write') and os.path.abspath(str(params.get('path') or params.get('file_path') or ''))==os.path.join(repo,'dep.py'))
if stale and not warm:
 rel='app.py' if os.path.abspath(str(params.get('path') or params.get('file_path') or ''))!=os.path.join(repo,'dep.py') else 'dep.py'
 out={'schema_version':'tmf.reflex.collision.v1','decision':'block','collision_id':'c1','canonical_repo_root':repo,'canonical_state_root':state,'blocked_action_fingerprint':fingerprint(tool,params,rel),'blocked_tool':tool,'blocked_target_path':rel,'stale_paths':[{'path':'dep.py','qualname':'quote','current_source_blob':blob('dep.py'),'anchor':${options.unreliableAnchor?"{'line_start':None,'line_end':None,'reliable':False}":"{'line_start':1,'line_end':2,'reliable':True}"}}]}
 print(json.dumps(out),file=sys.stderr);sys.exit(2)
print(json.dumps({'schema_version':'tmf.reflex.decision.v1','decision':'allow'}))
`);fs.chmodSync(py,0o755);
  return{root,repo,state,py,cleanup(){fs.rmSync(root,{recursive:true,force:true})}};
}
// Invocation sequence survives re-registration/reset, just like production tombstones.
let fixtureInvocationOrdinal=0;
function registered(f,extra={}){
  const handlers={};const api={pluginConfig:{repos:[{repoRoot:f.repo,stateRoot:f.state}],python:f.py,pendingTtlMs:extra.ttl||1800000},config:{},runtime:{agent:{resolveAgentWorkspaceDir:()=>f.repo}},on:(name,fn)=>handlers[name]=fn,session:{workflow:{enqueueNextTurnInjection:async()=>{}}}};
  m.resetState();m.default.register(api);
  // Legacy freshness/generation fixtures need genuine unique invocation IDs.
  // Preserve logical labels for delayed after lookup; identity adversaries live
  // in receipt-identity.test.cjs and the independent real runtime probe.
  const calls=new Map();
  for(const [name,fn] of Object.entries(handlers)) handlers[name]=(ev,c={})=>{
    const session=c.sessionKey?f.root+':'+c.sessionKey:undefined;
    if(name==='session_end')return fn({...ev,sessionKey:ev.sessionKey?f.root+':'+ev.sessionKey:undefined},{...c,sessionKey:session});
    const label=c.toolCallId||ev.toolCallId, key=JSON.stringify([session,c.runId,label]);
    if(name==='before_tool_call')calls.set(key,'fixture-call-'+(++fixtureInvocationOrdinal));
    const id=calls.get(key)||label;
    return fn({...ev,toolCallId:id},{...c,sessionKey:session,toolCallId:id});
  };
  return handlers;
}
const ctx=(session='s',id='c1',runId='r')=>({sessionKey:session,toolCallId:id,runId,toolName:'edit'});
const stale=f=>({toolName:'edit',toolCallId:'block',params:{path:path.join(f.repo,'app.py'),edits:[{oldText:'x',newText:"quote('pen', 2)"}]}});
const corrected=f=>({toolName:'edit',toolCallId:'fix',params:{path:path.join(f.repo,'app.py'),edits:[{oldText:'x',newText:"quote('pen', 2, 'USD')"}]}});
const readEvent=(f,id='read',params={})=>({toolName:'read',toolCallId:id,params:{path:path.join(f.repo,'dep.py'),...params}});
const mutationSuccess=f=>({content:[{type:'text',text:`Successfully replaced 1 block(s) in ${path.join(f.repo,'app.py')}.`}]});
const reason=(x,code)=>assert.match(x.blockReason,new RegExp(`\\[${code}\\]`));
async function establish(f,h,session='s'){const out=await h.before_tool_call(stale(f),ctx(session,'block'));reason(out,'need_warm');return out}
async function warm(f){const b=fs.readFileSync(path.join(f.repo,'dep.py'));const blob=crypto.createHash('sha1').update(`blob ${b.length}\0`).update(b).digest('hex');fs.writeFileSync(path.join(f.state,'warm'),blob)}
async function successfulRead(f,h,session='s',id='read',params={}){const ev=readEvent(f,id,params);const c=ctx(session,id);assert.equal(await h.before_tool_call(ev,c),undefined);await h.after_tool_call({...ev,result:{content:[{type:'text',text:fs.readFileSync(ev.params.path,'utf8')}]}},c)}

test('routes only explicit files into exactly one managed repo',()=>{const f=fixture();try{assert.equal(m.resolveFile({path:'a.py'},f.repo),path.join(f.repo,'a.py'));assert.equal(m.route(path.join(f.repo,'a.py'),[{repoRoot:f.repo}]).repoRoot,f.repo);assert.equal(m.route(path.join(f.repo,'a.py'),[{repoRoot:f.repo},{repoRoot:f.repo}]),undefined)}finally{f.cleanup()}});
test('register captures production lifecycle handlers',()=>{const f=fixture();try{const h=registered(f);for(const name of ['before_tool_call','after_tool_call','session_end'])assert.equal(typeof h[name],'function')}finally{f.cleanup()}});
test('block creates pending; warm fresh without Read remains need_read',async()=>{const f=fixture();try{const h=registered(f);await establish(f,h);assert.equal(m.debugState().pending,1);await warm(f);reason(await h.before_tool_call(stale(f),ctx('s','retry')),'need_read')}finally{f.cleanup()}});
test('successful exact Read unlocks corrected retry and pending is consumed only after success',async()=>{const f=fixture();try{const h=registered(f);await establish(f,h);await warm(f);await successfulRead(f,h);const ev=corrected(f),c=ctx('s','fix');assert.equal(await h.before_tool_call(ev,c),undefined);assert.equal(m.debugState().pending,1);await h.after_tool_call({...ev,result:mutationSuccess(f)},c);assert.equal(m.debugState().pending,0)}finally{f.cleanup()}});
test('production lifecycle accepts OpenClaw string pagination for an exact recovery Read',async()=>{const f=fixture();try{const h=registered(f);await establish(f,h);await warm(f);const ev=readEvent(f,'string-read',{offset:'1',limit:'2000'}),c=ctx('s','string-read');assert.equal(await h.before_tool_call(ev,c),undefined);assert.equal(m.debugState().reads,1);await h.after_tool_call({...ev,result:{content:[{type:'text',text:fs.readFileSync(ev.params.path,'utf8')}]}},c);assert.equal(await h.before_tool_call(corrected(f),ctx('s','fix')),undefined)}finally{f.cleanup()}});
test('production lifecycle permits a demonstrable whole-file Read when parser anchor is unavailable',async()=>{const f=fixture({unreliableAnchor:true});try{const h=registered(f);await establish(f,h);await warm(f);const ev=readEvent(f,'whole-file',{offset:1,limit:2000}),c=ctx('s','whole-file');assert.equal(await h.before_tool_call(ev,c),undefined);await h.after_tool_call({...ev,result:{content:[{type:'text',text:fs.readFileSync(ev.params.path,'utf8')}]}},c);assert.equal(await h.before_tool_call(corrected(f),ctx('s','fix')),undefined)}finally{f.cleanup()}});
test('unreliable anchor still rejects a partial Read',async()=>{const f=fixture({unreliableAnchor:true});try{const h=registered(f);await establish(f,h);await warm(f);reason(await h.before_tool_call(readEvent(f,'partial',{offset:1,limit:1}),ctx('s','partial')),'need_read')}finally{f.cleanup()}});
test('failed string-paginated recovery Read is only a candidate and does not unlock',async()=>{const f=fixture();try{const h=registered(f);await establish(f,h);await warm(f);const ev=readEvent(f,'failed-string-read',{offset:'1',limit:'2000'}),c=ctx('s','failed-string-read');assert.equal(await h.before_tool_call(ev,c),undefined);assert.equal(m.debugState().reads,1);await h.after_tool_call({...ev,error:'read failed'},c);reason(await h.before_tool_call(corrected(f),ctx('s','fix')),'need_read')}finally{f.cleanup()}});
test('read error, wrong path, and partial anchor do not unlock',async()=>{for(const kind of ['error','wrong','partial']){const f=fixture();try{const h=registered(f);await establish(f,h);await warm(f);let ev=kind==='wrong'?{toolName:'read',toolCallId:'rd',params:{path:path.join(f.repo,'other.py')}}:readEvent(f,'rd',kind==='partial'?{offset:2,limit:1}:{});let c=ctx('s','rd');const before=await h.before_tool_call(ev,c);if(kind==='partial')reason(before,'need_read');else assert.equal(before,undefined);await h.after_tool_call({...ev,...(kind==='error'?{error:'boom'}:{result:{ok:true}})},c);reason(await h.before_tool_call(corrected(f),ctx('s','fix')),'need_read')}finally{f.cleanup()}}});
test('same stale fingerprint remains stale_retry; corrected retry allows',async()=>{const f=fixture();try{const h=registered(f);await establish(f,h);await warm(f);await successfulRead(f,h);reason(await h.before_tool_call(stale(f),ctx('s','again')),'stale_retry');assert.equal(await h.before_tool_call(corrected(f),ctx('s','fix')),undefined)}finally{f.cleanup()}});
test('source changing after observation rearms and reblocks',async()=>{const f=fixture();try{const h=registered(f);await establish(f,h);await warm(f);await successfulRead(f,h);fs.appendFileSync(path.join(f.repo,'dep.py'),'# external\n');reason(await h.before_tool_call(corrected(f),ctx('s','fix')),'source_changed');assert.equal(m.debugState().pending,1);reason(await h.before_tool_call(corrected(f),ctx('s','fix2')),'need_warm')}finally{f.cleanup()}});
test('missing source blocks conservatively',async()=>{const f=fixture();try{const h=registered(f);await establish(f,h);await warm(f);fs.unlinkSync(path.join(f.repo,'dep.py'));reason(await h.before_tool_call(corrected(f),ctx('s','fix')),'missing')}finally{f.cleanup()}});
test('benign operation remains allowed while collision pending',async()=>{const f=fixture();try{const h=registered(f);await establish(f,h);assert.equal(await h.before_tool_call({toolName:'edit',toolCallId:'b',params:{path:path.join(f.repo,'other.py'),edits:[{oldText:'1',newText:'2'}]}},ctx('s','b')),undefined)}finally{f.cleanup()}});
test('session and repo isolation',async()=>{const f=fixture();try{const h=registered(f);await establish(f,h,'A');await warm(f);await successfulRead(f,h,'B','rb');reason(await h.before_tool_call(corrected(f),ctx('A','fix')),'need_read');assert.equal(await h.before_tool_call(corrected(f),ctx('B','free')),undefined);const f2=fixture();try{const h2=registered(f2);assert.equal(await h2.before_tool_call(corrected(f2),ctx('A','otherrepo')),undefined)}finally{f2.cleanup()}}finally{f.cleanup()}});
test('OpenClaw batch edit payload is fingerprinted and blocked',async()=>{const f=fixture();try{const h=registered(f);const ev=stale(f);reason(await h.before_tool_call(ev,ctx('s','block')),'need_warm');const expected=fp('edit',ev.params,'app.py');assert.equal(expected.length,64)}finally{f.cleanup()}});
test('session cleanup and TTL remove pending/read candidates',async()=>{const f=fixture();try{let h=registered(f);await establish(f,h);await h.session_end({sessionKey:'s'},{});assert.deepEqual(m.debugState(),{pending:0,reads:0,mutations:0});h=registered(f,{ttl:1});await establish(f,h);await new Promise(r=>setTimeout(r,5));assert.equal(m.debugState().pending,0)}finally{f.cleanup()}});
test('shell and pathless actions fail open and cannot unlock',async()=>{const f=fixture();try{const h=registered(f);await establish(f,h);await warm(f);assert.equal(await h.before_tool_call({toolName:'exec',toolCallId:'sh',params:{command:`cat ${path.join(f.repo,'dep.py')}`}},ctx('s','sh')),undefined);assert.equal(await h.before_tool_call({toolName:'apply_patch',toolCallId:'p',params:{input:'*** patch'}},ctx('s','p')),undefined);reason(await h.before_tool_call(corrected(f),ctx('s','fix')),'need_read')}finally{f.cleanup()}});
test('runId alone no longer substitutes for required session identity',async()=>{const f=fixture();try{const h=registered(f);const ev=stale(f);reason(await h.before_tool_call({...ev,runId:'run-only'},{runId:'run-only',toolCallId:'block'}),'identity_missing_or_mismatched');assert.equal(m.debugState().pending,0)}finally{f.cleanup()}});
test('after verifies exact result, params and source version; failures retain pending',async()=>{for(const kind of ['unknown','metadata','isError','wrong-params','during-read-change']){const f=fixture();try{const h=registered(f);await establish(f,h);await warm(f);const ev=readEvent(f),c=ctx('s','read');assert.equal(await h.before_tool_call(ev,c),undefined);let result={content:[{type:'text',text:fs.readFileSync(ev.params.path,'utf8')}]};if(kind==='unknown')result={content:'ok'};if(kind==='metadata')result.details={returnedLines:2,truncated:false};if(kind==='isError')result.isError=true;const after={...ev,result};if(kind==='wrong-params')after.params={...ev.params,offset:2};if(kind==='during-read-change')fs.appendFileSync(ev.params.path,'# raced\n');await h.after_tool_call(after,c);reason(await h.before_tool_call(corrected(f),ctx('s','fix')),kind==='during-read-change'?'source_changed':'need_read');assert.equal(m.debugState().pending,1)}finally{f.cleanup()}}});

// Generation regressions: Python freshness is an explicit fixture, not real SDK.
// Constant collision_id c1, repeated source bytes/target/fingerprint intentionally
// make target/hash/collision-ID matching insufficient as an ownership check.
for(const transition of ['replacement','rearm-ABA','expiry','cleanup']) for(const receipt of ['success','failure','read']) {
 test(`generation ${transition}: old ${receipt} cannot authorize new pending`,async()=>{
  const f=fixture(),realNow=Date.now;let now=realNow();Date.now=()=>now;
  try{
   const h=registered(f,{ttl:10000});await establish(f,h);await warm(f);
   const oldRead=readEvent(f,'old-read'),oldMutation={...corrected(f),toolCallId:'old-mutation'};
   const text=fs.readFileSync(oldRead.params.path,'utf8');
   if(receipt==='read') assert.equal(await h.before_tool_call(oldRead,ctx('s','old-read')),undefined);
   else {await successfulRead(f,h);assert.equal(await h.before_tool_call(oldMutation,ctx('s','old-mutation')),undefined);}
   if(transition==='rearm-ABA'){
    fs.appendFileSync(oldRead.params.path,'# B\n');reason(await h.before_tool_call(corrected(f),ctx('s','rearm-B')),'source_changed');
    fs.writeFileSync(oldRead.params.path,text);reason(await h.before_tool_call(corrected(f),ctx('s','rearm-A')),'source_changed');
   }else{
    if(transition==='expiry')now+=10001;
    if(transition==='cleanup')await h.session_end({sessionKey:'s'},{});
    fs.unlinkSync(path.join(f.state,'warm'));
    // Different mutation tool replaces the same-target slot, then replaces it
    // back; same source, target, collision_id and blocked fingerprint recur.
    if(transition==='replacement')reason(await h.before_tool_call({...stale(f),toolName:'write',toolCallId:'replace'},ctx('s','replace')),'need_warm');
    await establish(f,h);
   }
   assert.deepEqual(m.debugState(),{pending:1,reads:0,mutations:0});await warm(f);
   if(receipt==='read'){
    // Validate current warmth with a NEW before, but withhold its receipt.
    assert.equal(await h.before_tool_call(readEvent(f,'new-held-read'),ctx('s','new-held-read')),undefined);
    await h.after_tool_call({...oldRead,result:{content:[{type:'text',text}]}},ctx('s','old-read'));
    reason(await h.before_tool_call(corrected(f),ctx('s','unread')),'need_read');
   }else{
    // A fresh Read candidate must survive delivery of the old mutation error/success.
    const fresh=readEvent(f,'fresh-read');assert.equal(await h.before_tool_call(fresh,ctx('s','fresh-read')),undefined);
    await h.after_tool_call({...oldMutation,...(receipt==='failure'?{error:'realistic failure'}:{result:mutationSuccess(f)})},ctx('s','old-mutation'));
    assert.deepEqual(m.debugState(),{pending:1,reads:1,mutations:0});
    reason(await h.before_tool_call(corrected(f),ctx('s','unread')),'need_read');
    await h.after_tool_call({...fresh,result:{content:[{type:'text',text}]}},ctx('s','fresh-read'));
   }
   if(receipt==='read')await successfulRead(f,h,'s','new-read');
   const current={...corrected(f),toolCallId:'new-mutation'};
   assert.equal(await h.before_tool_call(current,ctx('s','new-mutation')),undefined);
   await h.after_tool_call({...current,result:mutationSuccess(f)},ctx('s','new-mutation'));assert.equal(m.debugState().pending,0);
  }finally{Date.now=realNow;f.cleanup()}
 });
}
test('rearm preserves configured TTL rather than extending it to the default',async()=>{
 const f=fixture(),realNow=Date.now;let now=realNow();Date.now=()=>now;
 try{const h=registered(f,{ttl:10000});await establish(f,h);now+=9000;fs.appendFileSync(path.join(f.repo,'dep.py'),'# B\n');reason(await h.before_tool_call(corrected(f),ctx('s','rearm')),'source_changed');now+=9999;assert.equal(m.debugState().pending,1);now+=1;assert.equal(m.debugState().pending,0)}finally{Date.now=realNow;f.cleanup()}
});
for(const result of [{isError:true},{error:'executor failed'}])test(`result-level mutation error retains own generation ${JSON.stringify(result)}`,async()=>{
 const f=fixture();try{const h=registered(f);await establish(f,h);await warm(f);await successfulRead(f,h);const ev=corrected(f);assert.equal(await h.before_tool_call(ev,ctx('s','fix')),undefined);await h.after_tool_call({...ev,result},ctx('s','fix'));assert.equal(m.debugState().pending,1);assert.equal(m.debugState().mutations,0)}finally{f.cleanup()}
});
for(const failure of [false,true])test(`old receipt leaves new admitted mutation candidate intact (failure=${failure})`,async()=>{
 const f=fixture();try{
  const h=registered(f);await establish(f,h);await warm(f);await successfulRead(f,h);
  const old={...corrected(f),toolCallId:'old'};assert.equal(await h.before_tool_call(old,ctx('s','old')),undefined);
  fs.unlinkSync(path.join(f.state,'warm'));
  reason(await h.before_tool_call({...stale(f),toolName:'write',toolCallId:'replace'},ctx('s','replace')),'need_warm');await establish(f,h);await warm(f);await successfulRead(f,h,'s','fresh');
  const current={...corrected(f),toolCallId:'current'};assert.equal(await h.before_tool_call(current,ctx('s','current')),undefined);
  await h.after_tool_call({...old,...(failure?{error:'old failure'}:{result:mutationSuccess(f)})},ctx('s','old'));
  assert.deepEqual(m.debugState(),{pending:1,reads:0,mutations:1});
  await h.after_tool_call({...current,result:mutationSuccess(f)},ctx('s','current'));assert.equal(m.debugState().pending,0);
 }finally{f.cleanup()}
});
