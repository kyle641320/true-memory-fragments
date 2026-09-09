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
function registered(f,extra={}){
  const handlers={};const api={pluginConfig:{repos:[{repoRoot:f.repo,stateRoot:f.state}],python:f.py,pendingTtlMs:extra.ttl||1800000},config:{},runtime:{agent:{resolveAgentWorkspaceDir:()=>f.repo}},on:(name,fn)=>handlers[name]=fn,session:{workflow:{enqueueNextTurnInjection:async()=>{}}}};
  m.resetState();m.default.register(api);for(const [name,fn] of Object.entries(handlers))handlers[name]=(ev,c={})=>fn(ev,{...c,sessionKey:f.root+':'+(c.sessionKey||'s')});return handlers;
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

for(const tool of ['read','edit','write','apply_patch'])test(`duplicate ${tool} without candidate blocked across tools`,async()=>{const f=fixture();try{const h=registered(f),ev={toolName:tool,toolCallId:'x',params:{path:path.join(f.repo,'other.py')}};assert.equal(await h.before_tool_call(ev,ctx('s','x')),undefined);reason(await h.before_tool_call(ev,ctx('s','x')),'identity_reused');reason(await h.before_tool_call({...ev,toolName:'read'},ctx('s','x')),'identity_reused')}finally{f.cleanup()}});
for(const kind of ['read-success','read-failure','success','failure'])test(`tainted ${kind} cannot acquire authority; unique recovery works`,async()=>{const f=fixture();try{const h=registered(f);await establish(f,h);await warm(f);const rd=kind.startsWith('read'),ev=rd?readEvent(f,'identity'):{...corrected(f),toolCallId:'identity'},c=ctx('s','identity');if(!rd)await successfulRead(f,h);assert.equal(await h.before_tool_call(ev,c),undefined);reason(await h.before_tool_call(ev,c),'identity_reused');for(const error of ['blocked duplicate',undefined])await h.after_tool_call({...ev,error:kind.endsWith('failure')?'failed':error,result:rd?{content:[{type:'text',text:fs.readFileSync(ev.params.path,'utf8')}]}:mutationSuccess(f)},c);assert.equal(m.debugState().pending,1);assert.equal(m.debugState()[rd?'reads':'mutations'],0);if(rd){reason(await h.before_tool_call(corrected(f),ctx('s','fix')),'need_read');await successfulRead(f,h,'s','fresh-read')}const good={...corrected(f),toolCallId:'fresh-fix'};assert.equal(await h.before_tool_call(good,ctx('s','fresh-fix')),undefined);await h.after_tool_call({...good,result:mutationSuccess(f)},ctx('s','fresh-fix'));assert.equal(m.debugState().pending,0)}finally{f.cleanup()}});
test('same ID distinct runs isolates receipts',async()=>{const f=fixture();try{const h=registered(f);await establish(f,h);await warm(f);const ev=readEvent(f,'x');assert.equal(await h.before_tool_call(ev,ctx('s','x','r1')),undefined);assert.equal(await h.before_tool_call(ev,ctx('s','x','r2')),undefined);await h.after_tool_call({...ev,error:'old failed'},ctx('s','x','r1'));assert.equal(m.debugState().reads,1);await h.after_tool_call({...ev,result:{content:[{type:'text',text:fs.readFileSync(ev.params.path,'utf8')}]}},ctx('s','x','r2'));assert.equal(await h.before_tool_call(corrected(f),ctx('s','fix')),undefined)}finally{f.cleanup()}});
test('TTL cleanup reset retain tombstones; sessions isolated',async()=>{const f=fixture();try{const h=registered(f,{ttl:1}),ev=readEvent(f,'x');assert.equal(await h.before_tool_call(ev,ctx('s','x')),undefined);await new Promise(r=>setTimeout(r,5));await h.session_end({},ctx('s','end'));m.resetState();reason(await h.before_tool_call(ev,ctx('s','x')),'identity_reused');assert.equal(await h.before_tool_call(ev,ctx('new','x')),undefined)}finally{f.cleanup()}});
test('missing oversized inconsistent fields blocked in approval mode; invalid receipts preserve candidate',async()=>{const f=fixture();try{const config={repos:[{repoRoot:f.repo,stateRoot:f.state}],python:f.py,mode:'approval'},ev=readEvent(f,'valid'),valid={sessionKey:f.root,runId:'r',toolCallId:'valid'};for(const c of [{...valid,runId:undefined},{...valid,sessionKey:undefined},{...valid,toolCallId:'different'},{...valid,runId:'x'.repeat(257)},{...valid,runId:''}])assert.equal(m.runPreToolUse(ev,f.repo,config,c).block,true);assert.equal(m.runPreToolUse({...ev,toolCallId:undefined},f.repo,config,{...valid,toolCallId:undefined}).block,true);const h=registered(f);await establish(f,h);await warm(f);await h.before_tool_call(ev,ctx('s','valid'));await h.after_tool_call({...ev,runId:'wrong',result:{ok:true}},ctx('s','valid'));assert.equal(m.debugState().reads,1)}finally{f.cleanup()}});
test('wrong tool receipt is ignored; JSON tuple separators cannot alias',async()=>{const f=fixture();try{const h=registered(f);await establish(f,h);await warm(f);const ev=readEvent(f,'x');await h.before_tool_call(ev,ctx('s','x'));await h.after_tool_call({...ev,toolName:'edit',error:'wrong'},ctx('s','x'));assert.equal(m.debugState().reads,1);const config={repos:[{repoRoot:f.repo,stateRoot:f.state}],python:f.py},call={toolName:'read',params:{path:path.join(f.repo,'other.py')}};assert.equal(m.runPreToolUse({...call,toolCallId:'c'},f.repo,config,{sessionKey:f.root,runId:'a\0b'}),undefined);assert.equal(m.runPreToolUse({...call,toolCallId:'b\0c'},f.repo,config,{sessionKey:f.root,runId:'a'}),undefined)}finally{f.cleanup()}});
test('bounded global saturation rejects new identities without eviction or reset escape',()=>{const f=fixture();try{const config={repos:[{repoRoot:f.repo,stateRoot:f.state}],python:'/nonexistent'},ev={toolName:'read',params:{path:path.join(f.repo,'other.py')}},start=m.debugReceiptIdentityState().size,cap=m.RECEIPT_IDENTITY_CAPACITY;for(let i=start;i<cap;i++)assert.equal(m.runPreToolUse({...ev,toolCallId:'cap-'+i},f.repo,config,{sessionKey:f.root,runId:'cap'}),undefined);assert.deepEqual(m.debugReceiptIdentityState(),{size:cap,capacity:cap});for(let i=0;i<20;i++)reason(m.runPreToolUse({...ev,toolCallId:'overflow-'+i},f.repo,config,{sessionKey:'other',runId:'r'}),'identity_capacity');m.resetState();reason(m.runPreToolUse({...ev,toolCallId:'cap-'+start},f.repo,config,{sessionKey:f.root,runId:'cap'}),'identity_reused');assert.equal(m.debugReceiptIdentityState().size,cap)}finally{f.cleanup()}});
