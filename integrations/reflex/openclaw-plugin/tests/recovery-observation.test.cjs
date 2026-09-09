const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const test=require('node:test');
const {createJiti}=require('jiti');
const jiti=createJiti(__filename,{interopDefault:true});
const source=path.resolve(__dirname,'../index.ts');
let m=process.env.TMF_R1_R2_BASELINE ? jiti.evalModule(fs.readFileSync(process.env.TMF_R1_R2_BASELINE,'utf8'),{filename:source}) : jiti(source);

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
  return{root,repo,state,py,observations:path.join(root,'observations'),cleanup(){fs.rmSync(root,{recursive:true,force:true})}};
}
function registered(f,extra={}){
  const handlers={};const api={pluginConfig:{repos:[{repoRoot:f.repo,stateRoot:f.state}],python:f.py,recoveryObservationRoot:f.observations,pendingTtlMs:extra.ttl||1800000},config:{},runtime:{agent:{resolveAgentWorkspaceDir:()=>f.repo}},on:(name,fn)=>handlers[name]=fn,session:{workflow:{enqueueNextTurnInjection:async()=>{}}}};
  m.resetState();m.default.register(api);return handlers;
}
const ctx=(session='s',id='c1',runId='r')=>({sessionKey:session,toolCallId:id,runId,toolName:'edit'});
const stale=f=>({toolName:'edit',toolCallId:'block',params:{path:path.join(f.repo,'app.py'),edits:[{oldText:'from dep import quote',newText:"quote('pen', 2)"}]}});
const corrected=f=>({toolName:'edit',toolCallId:'fix',params:{path:path.join(f.repo,'app.py'),edits:[{oldText:'from dep import quote',newText:"quote('pen', 2, 'USD')"}]}});
const readEvent=(f,id='read',params={})=>({toolName:'read',toolCallId:id,params:{path:path.join(f.repo,'dep.py'),...params}});
const reason=(x,code)=>assert.match(x.blockReason,new RegExp(`\\[${code}\\]`));
async function establish(f,h,session='s'){const out=await h.before_tool_call(stale(f),ctx(session,'block'));reason(out,'need_warm');return out}
async function warm(f){const b=fs.readFileSync(path.join(f.repo,'dep.py'));const blob=crypto.createHash('sha1').update(`blob ${b.length}\0`).update(b).digest('hex');fs.writeFileSync(path.join(f.state,'warm'),blob)}
async function successfulRead(f,h,session='s',id='read',params={}){const ev=readEvent(f,id,params);const c=ctx(session,id);assert.equal(await h.before_tool_call(ev,c),undefined);await h.after_tool_call({...ev,result:{content:[{type:'text',text:fs.readFileSync(ev.params.path,'utf8')}]}},c)}


// Synthetic Python freshness oracle and built-in-shaped host receipts.
// Real registered C1 handlers + real temp-file mutation/read/postimage I/O.
const {spawnSync}=require('node:child_process');
const success=ev=>({content:[{type:'text',text:`Successfully replaced ${ev.params.edits.length} block(s) in ${ev.params.path}.`}]});
async function ready(f,h,s){await establish(f,h,s);await warm(f);await successfulRead(f,h,s);const ev=corrected(f);assert.equal(await h.before_tool_call(ev,ctx(s,'fix')),undefined);return ev;}
function executeMutation(ev){let text=fs.readFileSync(ev.params.path,'utf8');for(const edit of ev.params.edits){assert.ok(text.includes(edit.oldText));text=text.replace(edit.oldText,edit.newText);}fs.writeFileSync(ev.params.path,text);return success(ev)}
const tickets=f=>fs.existsSync(f.observations)?fs.readdirSync(f.observations):[];
for(const mode of ['normal','wrong-predicate','drift-target','drift-dependency','drift-before-validation'])test(`release -> explicit ${mode}`,async()=>{
 const f=fixture();try {const h=registered(f),s=f.root;const ev=await ready(f,h,s);
 assert.equal(tickets(f).length,0);await h.after_tool_call({...ev,result:executeMutation(ev)},ctx(s,'fix'));
 assert.equal(m.debugState().pending,0);assert.equal(tickets(f).length,1);
 const ticket=path.join(f.observations,tickets(f)[0]),o=JSON.parse(fs.readFileSync(ticket));
 assert.equal(o.status,'recovery_released_without_consolidation');assert.equal(o.identity.sessionKey,s);assert.equal(o.identity.runId,'r');assert.equal(o.identity.toolCallId,'fix');assert.equal(o.identity.sessionId,null);assert.deepEqual(o.identity_gaps,['sessionId:not_provided_by_host']);assert.equal(o.postmutation_vector.length,2);
 assert.equal(fs.existsSync(path.join(f.root,'cognition')),false);
 await h.after_tool_call({...ev,result:success(ev)},ctx(s,'fix'));assert.equal(tickets(f).length,1);
 const p=spawnSync('python3',[path.join(__dirname,'helpers/check_candidate.py'),f.repo,ticket,mode],{encoding:'utf8'});assert.equal(p.status,0,p.stdout+p.stderr);
 } finally{f.cleanup()}
});
for(const mode of ['error','unknown','wrong-id','wrong-fingerprint','wrong-run','missing-id'])test(`no observation on ${mode}`,async()=>{
 const f=fixture();try {const h=registered(f),s=f.root;const ev=await ready(f,h,s);let result=success(ev),c=ctx(s,'fix'),after={...ev,result};
 if(mode==='error')after.error='failed';if(mode==='unknown')after.result={ok:true};
 if(mode==='wrong-id'){after.toolCallId='wrong';c.toolCallId='wrong'}
 if(mode==='missing-id'){delete after.toolCallId;delete c.toolCallId}
 if(mode==='wrong-run')c.runId='other';if(mode==='wrong-fingerprint')after.params={...ev.params,edits:[{oldText:'different',newText:'different'}]};
 await h.after_tool_call(after,c);assert.equal(m.debugState().pending,1);assert.equal(tickets(f).length,0);
 }finally{f.cleanup()}
});
test('observation persistence failure never reverses successful mutation/release',async()=>{
 const f=fixture();try{fs.writeFileSync(f.observations,'not a directory');const h=registered(f),s=f.root,ev=await ready(f,h,s);
 const before=m.debugRecoveryGaps().length;await h.after_tool_call({...ev,result:executeMutation(ev)},ctx(s,'fix'));
 assert.equal(m.debugState().pending,0);assert.match(fs.readFileSync(ev.params.path,'utf8'),/USD/);
 assert.equal(m.debugRecoveryGaps().length,before+1);assert.equal(m.debugRecoveryGaps().at(-1).status,'recovery_released_observation_gap');
 }finally{f.cleanup()}
});

test('optional session identity drift with stable primary key cannot create observation',async()=>{
 const f=fixture();try{const h=registered(f),s=f.root;await establish(f,h,s);await warm(f);await successfulRead(f,h,s);const ev=corrected(f);
 assert.equal(await h.before_tool_call(ev,{...ctx(s,'fix'),sessionId:'before-id'}),undefined);
 const n=m.debugRecoveryGaps().length;await h.after_tool_call({...ev,result:executeMutation(ev)},{...ctx(s,'fix'),sessionId:'after-id'});
 assert.equal(m.debugState().pending,0);assert.equal(tickets(f).length,0);assert.equal(m.debugRecoveryGaps().length,n+1);assert.match(m.debugRecoveryGaps().at(-1).reason,/identity_drift/);
 }finally{f.cleanup()}
});

// Fault-inject only the UUID call in an isolated evaluation of the current source.
// Namespace-import snapshots cannot reliably be patched after Jiti compilation.
test('UUID failure must not escape released recovery',async()=>{
 const f=fixture(), originalModule=m;
 try {
  const text=fs.readFileSync(source,'utf8');assert.equal(text.split('id=crypto.randomUUID();').length,2);
  m=jiti.evalModule(text.replace('id=crypto.randomUUID();', "id=(()=>{throw new Error('injected uuid failure')})();"),{filename:source});
  const h=registered(f),s=f.root,ev=await ready(f,h,s),result=executeMutation(ev);
  await assert.doesNotReject(()=>h.after_tool_call({...ev,result},ctx(s,'fix')));
  assert.equal(m.debugState().pending,0);assert.match(fs.readFileSync(ev.params.path,'utf8'),/USD/);
  assert.equal(tickets(f).length,0);assert.equal(m.debugRecoveryGaps().at(-1).id,null);
  assert.match(m.debugRecoveryGaps().at(-1).reason,/injected uuid failure/);
 } finally {m=originalModule;f.cleanup()}
});
