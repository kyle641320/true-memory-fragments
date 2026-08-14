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
function fixture(){
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'tmf-oc-')),repo=path.join(root,'repo'),state=path.join(root,'state');
  fs.mkdirSync(repo);fs.mkdirSync(state);fs.writeFileSync(path.join(repo,'dep.py'),'def quote(item, qty, currency):\n    return item\n');fs.writeFileSync(path.join(repo,'app.py'),'from dep import quote\n');fs.writeFileSync(path.join(repo,'other.py'),'x=1\n');
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
 out={'schema_version':'tmf.reflex.collision.v1','decision':'block','collision_id':'c1','canonical_repo_root':repo,'canonical_state_root':state,'blocked_action_fingerprint':fingerprint(tool,params,rel),'blocked_tool':tool,'blocked_target_path':rel,'stale_paths':[{'path':'dep.py','qualname':'quote','current_source_blob':blob('dep.py'),'anchor':{'line_start':1,'line_end':2,'reliable':True}}]}
 print(json.dumps(out),file=sys.stderr);sys.exit(2)
print(json.dumps({'schema_version':'tmf.reflex.decision.v1','decision':'allow'}))
`);fs.chmodSync(py,0o755);
  return{root,repo,state,py,cleanup(){fs.rmSync(root,{recursive:true,force:true})}};
}
function registered(f,extra={}){
  const handlers={};const api={pluginConfig:{repos:[{repoRoot:f.repo,stateRoot:f.state}],python:f.py,pendingTtlMs:extra.ttl||1800000},config:{},runtime:{agent:{resolveAgentWorkspaceDir:()=>f.repo}},on:(name,fn)=>handlers[name]=fn,session:{workflow:{enqueueNextTurnInjection:async()=>{}}}};
  m.resetState();m.default.register(api);return handlers;
}
const ctx=(session='s',id='c1',runId='r')=>({sessionKey:session,toolCallId:id,runId,toolName:'edit'});
const stale=f=>({toolName:'edit',toolCallId:'block',params:{path:path.join(f.repo,'app.py'),edits:[{oldText:'x',newText:"quote('pen', 2)"}]}});
const corrected=f=>({toolName:'edit',toolCallId:'fix',params:{path:path.join(f.repo,'app.py'),edits:[{oldText:'x',newText:"quote('pen', 2, 'USD')"}]}});
const readEvent=(f,id='read',params={})=>({toolName:'read',toolCallId:id,params:{path:path.join(f.repo,'dep.py'),...params}});
const reason=(x,code)=>assert.match(x.blockReason,new RegExp(`\\[${code}\\]`));
async function establish(f,h,session='s'){const out=await h.before_tool_call(stale(f),ctx(session,'block'));reason(out,'need_warm');return out}
async function warm(f){const b=fs.readFileSync(path.join(f.repo,'dep.py'));const blob=crypto.createHash('sha1').update(`blob ${b.length}\0`).update(b).digest('hex');fs.writeFileSync(path.join(f.state,'warm'),blob)}
async function successfulRead(f,h,session='s',id='read',params={}){const ev=readEvent(f,id,params);const c=ctx(session,id);assert.equal(await h.before_tool_call(ev,c),undefined);await h.after_tool_call({...ev,result:{content:'ok'}},c)}

test('routes only explicit files into exactly one managed repo',()=>{const f=fixture();try{assert.equal(m.resolveFile({path:'a.py'},f.repo),path.join(f.repo,'a.py'));assert.equal(m.route(path.join(f.repo,'a.py'),[{repoRoot:f.repo}]).repoRoot,f.repo);assert.equal(m.route(path.join(f.repo,'a.py'),[{repoRoot:f.repo},{repoRoot:f.repo}]),undefined)}finally{f.cleanup()}});
test('register captures production lifecycle handlers',()=>{const f=fixture();try{const h=registered(f);for(const name of ['before_tool_call','after_tool_call','session_end'])assert.equal(typeof h[name],'function')}finally{f.cleanup()}});
test('block creates pending; warm fresh without Read remains need_read',async()=>{const f=fixture();try{const h=registered(f);await establish(f,h);assert.equal(m.debugState().pending,1);await warm(f);reason(await h.before_tool_call(stale(f),ctx('s','retry')),'need_read')}finally{f.cleanup()}});
test('successful exact Read unlocks corrected retry and pending is consumed only after success',async()=>{const f=fixture();try{const h=registered(f);await establish(f,h);await warm(f);await successfulRead(f,h);const ev=corrected(f),c=ctx('s','fix');assert.equal(await h.before_tool_call(ev,c),undefined);assert.equal(m.debugState().pending,1);await h.after_tool_call({...ev,result:{ok:true}},c);assert.equal(m.debugState().pending,0)}finally{f.cleanup()}});
test('read error, wrong path, and partial anchor do not unlock',async()=>{for(const kind of ['error','wrong','partial']){const f=fixture();try{const h=registered(f);await establish(f,h);await warm(f);let ev=kind==='wrong'?{toolName:'read',toolCallId:'rd',params:{path:path.join(f.repo,'other.py')}}:readEvent(f,'rd',kind==='partial'?{offset:2,limit:1}:{});let c=ctx('s','rd');const before=await h.before_tool_call(ev,c);if(kind==='partial')reason(before,'need_read');else assert.equal(before,undefined);await h.after_tool_call({...ev,...(kind==='error'?{error:'boom'}:{result:{ok:true}})},c);reason(await h.before_tool_call(corrected(f),ctx('s','fix')),'need_read')}finally{f.cleanup()}}});
test('same stale fingerprint remains stale_retry; corrected retry allows',async()=>{const f=fixture();try{const h=registered(f);await establish(f,h);await warm(f);await successfulRead(f,h);reason(await h.before_tool_call(stale(f),ctx('s','again')),'stale_retry');assert.equal(await h.before_tool_call(corrected(f),ctx('s','fix')),undefined)}finally{f.cleanup()}});
test('source changing after observation rearms and reblocks',async()=>{const f=fixture();try{const h=registered(f);await establish(f,h);await warm(f);await successfulRead(f,h);fs.appendFileSync(path.join(f.repo,'dep.py'),'# external\n');reason(await h.before_tool_call(corrected(f),ctx('s','fix')),'source_changed');assert.equal(m.debugState().pending,1);reason(await h.before_tool_call(corrected(f),ctx('s','fix2')),'need_warm')}finally{f.cleanup()}});
test('missing source blocks conservatively',async()=>{const f=fixture();try{const h=registered(f);await establish(f,h);await warm(f);fs.unlinkSync(path.join(f.repo,'dep.py'));reason(await h.before_tool_call(corrected(f),ctx('s','fix')),'missing')}finally{f.cleanup()}});
test('benign operation remains allowed while collision pending',async()=>{const f=fixture();try{const h=registered(f);await establish(f,h);assert.equal(await h.before_tool_call({toolName:'edit',toolCallId:'b',params:{path:path.join(f.repo,'other.py'),edits:[{oldText:'1',newText:'2'}]}},ctx('s','b')),undefined)}finally{f.cleanup()}});
test('session and repo isolation',async()=>{const f=fixture();try{const h=registered(f);await establish(f,h,'A');await warm(f);await successfulRead(f,h,'B','rb');reason(await h.before_tool_call(corrected(f),ctx('A','fix')),'need_read');assert.equal(await h.before_tool_call(corrected(f),ctx('B','free')),undefined);const f2=fixture();try{const h2=registered(f2);assert.equal(await h2.before_tool_call(corrected(f2),ctx('A','otherrepo')),undefined)}finally{f2.cleanup()}}finally{f.cleanup()}});
test('OpenClaw batch edit payload is fingerprinted and blocked',async()=>{const f=fixture();try{const h=registered(f);const ev=stale(f);reason(await h.before_tool_call(ev,ctx('s','block')),'need_warm');const expected=fp('edit',ev.params,'app.py');assert.equal(expected.length,64)}finally{f.cleanup()}});
test('session cleanup and TTL remove pending/read candidates',async()=>{const f=fixture();try{let h=registered(f);await establish(f,h);await h.session_end({sessionKey:'s'},{});assert.deepEqual(m.debugState(),{pending:0,reads:0,mutations:0});h=registered(f,{ttl:1});await establish(f,h);await new Promise(r=>setTimeout(r,5));assert.equal(m.debugState().pending,0)}finally{f.cleanup()}});
test('shell and pathless actions fail open and cannot unlock',async()=>{const f=fixture();try{const h=registered(f);await establish(f,h);await warm(f);assert.equal(await h.before_tool_call({toolName:'exec',toolCallId:'sh',params:{command:`cat ${path.join(f.repo,'dep.py')}`}},ctx('s','sh')),undefined);assert.equal(await h.before_tool_call({toolName:'apply_patch',toolCallId:'p',params:{input:'*** patch'}},ctx('s','p')),undefined);reason(await h.before_tool_call(corrected(f),ctx('s','fix')),'need_read')}finally{f.cleanup()}});
test('runId is the conservative session identity fallback',async()=>{const f=fixture();try{const h=registered(f);const ev=stale(f);reason(await h.before_tool_call({...ev,runId:'run-only'},{runId:'run-only',toolCallId:'block'}),'need_warm');assert.equal(m.debugState().pending,1)}finally{f.cleanup()}});
