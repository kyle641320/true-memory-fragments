const assert=require('node:assert/strict');
const crypto=require('node:crypto');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const test=require('node:test');
const {createJiti}=require('jiti');
const jiti=createJiti(__filename,{interopDefault:true});
const source=path.resolve(__dirname,'../index.ts');
const m=process.env.TMF_R1_R2_BASELINE ? jiti.evalModule(fs.readFileSync(process.env.TMF_R1_R2_BASELINE,'utf8'),{filename:source}) : jiti(source);

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
  m.resetState();m.default.register(api);return handlers;
}
const ctx=(session='s',id='c1',runId='r')=>({sessionKey:session,toolCallId:id,runId,toolName:'edit'});
const stale=f=>({toolName:'edit',toolCallId:'block',params:{path:path.join(f.repo,'app.py'),edits:[{oldText:'x',newText:"quote('pen', 2)"}]}});
const corrected=f=>({toolName:'edit',toolCallId:'fix',params:{path:path.join(f.repo,'app.py'),edits:[{oldText:'x',newText:"quote('pen', 2, 'USD')"}]}});
const readEvent=(f,id='read',params={})=>({toolName:'read',toolCallId:id,params:{path:path.join(f.repo,'dep.py'),...params}});
const reason=(x,code)=>assert.match(x.blockReason,new RegExp(`\\[${code}\\]`));
async function establish(f,h,session='s'){const out=await h.before_tool_call(stale(f),ctx(session,'block'));reason(out,'need_warm');return out}
async function warm(f){const b=fs.readFileSync(path.join(f.repo,'dep.py'));const blob=crypto.createHash('sha1').update(`blob ${b.length}\0`).update(b).digest('hex');fs.writeFileSync(path.join(f.state,'warm'),blob)}
async function successfulRead(f,h,session='s',id='read',params={}){const ev=readEvent(f,id,params);const c=ctx(session,id);assert.equal(await h.before_tool_call(ev,c),undefined);await h.after_tool_call({...ev,result:{content:[{type:'text',text:fs.readFileSync(ev.params.path,'utf8')}]}},c)}


// Raw identities: no label/ID rewriting. Synthetic freshness oracle only.
async function setup(run) {
 const f=fixture(); try { const h=registered(f), session=f.root;
 await establish(f,h,session); await warm(f);
 await run(f,h,session);
 } finally {f.cleanup()}
}
const success=ev=>({content:[{type:'text',text:`Successfully replaced ${ev.params.edits.length} block(s) in ${ev.params.path}.`}]});
const negatives=[['missing',undefined],['null',null],['empty',{}],['blocked',{status:'blocked'}],['ok-only',{ok:true}],['string','success'],['false',false],['empty-error',{error:''}],['wrong-error-type',{error:0}],['wrong-isError',{isError:'false'}]];
for(const [name,result] of negatives)test(`R1 ${name} receipt retains pending`,()=>setup(async(f,h,s)=>{
 await successfulRead(f,h,s);const ev=corrected(f),c=ctx(s,'fix');assert.equal(await h.before_tool_call(ev,c),undefined);
 await h.after_tool_call({...ev,...(result===undefined?{}:{result})},c);
 assert.equal(m.debugState().pending,1);assert.equal(m.debugState().mutations,0);
 const fresh={...ev,toolCallId:'fresh'};assert.equal(await h.before_tool_call(fresh,ctx(s,'fresh')),undefined);
 await h.after_tool_call({...fresh,result:success(fresh)},ctx(s,'fresh'));assert.equal(m.debugState().pending,0);
}));
for(const field of ['status','error','isError'])test(`R1 success text with contradictory ${field} fails closed`,()=>setup(async(f,h,s)=>{
 await successfulRead(f,h,s);const ev=corrected(f),c=ctx(s,'fix');await h.before_tool_call(ev,c);
 await h.after_tool_call({...ev,result:{...success(ev),[field]:field==='status'?'blocked':field==='error'?'':0}},c);assert.equal(m.debugState().pending,1);
}));
for(const kind of ['run-alias','id-alias','id-only','run-only','key-conflict','id-conflict','invalid-key'])test(`R2 ${kind} cannot clear another session or its Read candidate`,()=>setup(async(f,h,s)=>{
 const ev=readEvent(f);await h.before_tool_call(ev,ctx(s,'read'));
 const b=s+'-B';let event={sessionKey:b},context={sessionKey:b};
 if(kind==='run-alias')event.runId=s;
 if(kind==='id-alias')event.sessionId=s;
 if(kind==='id-only'){event={sessionId:s};context={};}
 if(kind==='run-only'){event={runId:s};context={};}
 if(kind==='key-conflict'){event={sessionKey:s};context={sessionKey:b};}
 if(kind==='id-conflict'){event={sessionKey:s,sessionId:'id-A'};context={sessionKey:s,sessionId:'id-B'};}
 if(kind==='invalid-key'){event={sessionKey:s};context={sessionKey:7};}
 await h.session_end(event,context);assert.deepEqual(m.debugState(),{pending:1,reads:1,mutations:0});
 reason(await h.before_tool_call({...corrected(f),toolCallId:'still-gated'},ctx(s,'still-gated')),'need_read');
 await h.after_tool_call({...ev,result:{content:[{type:'text',text:fs.readFileSync(ev.params.path,'utf8')}]}},ctx(s,'read'));
 assert.equal(await h.before_tool_call(corrected(f),ctx(s,'fix')),undefined);
}));
test('R2 valid own end clears mutation but retains identity tombstones',()=>setup(async(f,h,s)=>{
 await successfulRead(f,h,s);const ev=corrected(f);await h.before_tool_call(ev,ctx(s,'fix'));
 const count=m.debugReceiptIdentityState().size;await h.session_end({sessionKey:s,sessionId:'uuid'},{sessionKey:s,sessionId:'uuid'});
 assert.deepEqual(m.debugState(),{pending:0,reads:0,mutations:0});assert.equal(m.debugReceiptIdentityState().size,count);
 reason(await h.before_tool_call(ev,ctx(s,'fix')),'identity_reused');
}));

for(const kind of ['wrong-path','wrong-count','extra-block','event-empty-error'])test(`R1 ${kind} positive-looking receipt rejected`,()=>setup(async(f,h,s)=>{
 await successfulRead(f,h,s);const ev=corrected(f),c=ctx(s,'fix');await h.before_tool_call(ev,c);let result=success(ev),after={...ev,result};
 if(kind==='wrong-path')result.content[0].text+='other';
 if(kind==='wrong-count')result.content[0].text=result.content[0].text.replace('1 block','2 block');
 if(kind==='extra-block')result.content.push({type:'text',text:'failed'});
 if(kind==='event-empty-error')after.error='';
 await h.after_tool_call(after,c);assert.equal(m.debugState().pending,1);
}));
test('R2 collision cannot delete another session mutation candidate',()=>setup(async(f,h,s)=>{
 await successfulRead(f,h,s);const ev=corrected(f),c=ctx(s,'fix');await h.before_tool_call(ev,c);
 await h.session_end({sessionKey:s+'B',sessionId:s,runId:s},{sessionKey:s+'B'});
 assert.deepEqual(m.debugState(),{pending:1,reads:0,mutations:1});await h.after_tool_call({...ev,result:success(ev)},c);assert.equal(m.debugState().pending,0);
}));
test('R2 valid own end clears Read candidate; sessionId-only cleanup is deliberately unsupported',()=>setup(async(f,h,s)=>{
 await h.before_tool_call(readEvent(f),ctx(s,'read'));await h.session_end({}, {sessionKey:s});assert.deepEqual(m.debugState(),{pending:0,reads:0,mutations:0});
}));
// Optional installed SDK control: opt-in local module path, never discover config/auth.
if(process.env.TMF_R1_R2_SDK)for(const tool of ['edit','write'])test(`installed ${tool} actual failure and success receipts`,()=>setup(async(f,h,s)=>{
 const sdk=await import(require('node:url').pathToFileURL(process.env.TMF_R1_R2_SDK).href);
 const execute=(tool==='edit'?sdk.X(f.repo):sdk.B(f.repo)).execute;
 if(tool==='write'){
  // Replace pending with same collision's write variant before warming again.
  fs.unlinkSync(path.join(f.state,'warm'));
  const blocked={toolName:'write',toolCallId:'write-block',params:{path:path.join(f.repo,'app.py'),content:"quote('pen', 2)"}};
  reason(await h.before_tool_call(blocked,ctx(s,'write-block')),'need_warm');await warm(f);
 }
 await successfulRead(f,h,s);
 const ev=tool==='edit'?{...corrected(f),params:{path:path.join(f.repo,'app.py'),edits:[{oldText:'from dep import quote',newText:'from dep import quote # USD'}]}}:{toolName:'write',toolCallId:'fix',params:{path:path.join(f.repo,'app.py'),content:'# USD 中文😀\n'}};
 const c=ctx(s,'fix');assert.equal(await h.before_tool_call(ev,c),undefined);
 let failure;try{await execute('failure',ev.params,AbortSignal.abort());assert.fail('must abort')}catch(e){failure=String(e)}
 await h.after_tool_call({...ev,error:failure},c);assert.equal(m.debugState().pending,1);
 const good={...ev,toolCallId:'good'};const gc=ctx(s,'good');assert.equal(await h.before_tool_call(good,gc),undefined);
 const result=await execute('good',good.params);assert.match(fs.readFileSync(ev.params.path,'utf8'),/USD/);
 await h.after_tool_call({...good,result},gc);assert.equal(m.debugState().pending,0);
}));

test('R2 explicit key cannot clean pending created in sessionId fallback domain',async()=>{
 const f=fixture();try{const h=registered(f),s=f.root,c={sessionId:s,runId:'r',toolCallId:'block'};
 reason(await h.before_tool_call(stale(f),c),'need_warm');await warm(f);
 const ev=readEvent(f);await h.before_tool_call(ev,{...c,toolCallId:'read'});
 await h.session_end({sessionKey:s},{});assert.deepEqual(m.debugState(),{pending:1,reads:1,mutations:0});
 }finally{f.cleanup()}
});
