'use strict';
const fs=require('node:fs'),path=require('node:path'),cp=require('node:child_process'),assert=require('node:assert/strict'),os=require('node:os');
const test=require('node:test');
const W=path.resolve(__dirname,'../../../..');
const owner=fs.mkdtempSync(path.join(os.tmpdir(),'tmf-lineage-engine-')),B=path.join(owner,'evidence'),repo=path.join(owner,'repo'),state=path.join(owner,'external/.tmf'),cognition=path.join(owner,'cognition'),observations=path.join(B,'observations');
const env={PATH:process.env.PATH,LANG:'C.UTF-8',PYTHONDONTWRITEBYTECODE:'1',TMF_WORKTREE:W};
const evidence=[];const save=()=>fs.writeFileSync(path.join(B,'evidence.json'),JSON.stringify(evidence,null,2));
function run(args){const p=cp.spawnSync(args[0],args.slice(1),{env,cwd:repo,encoding:'utf8',timeout:30000});evidence.push({kind:'process',args,exit:p.status,stdout:p.stdout,stderr:p.stderr});save();assert.equal(p.status,0,p.stderr+p.stdout);return p.stdout;}
function warm(file){const x=JSON.parse(run(['python3','-B',path.join(W,'integrations/reflex/scripts/local_warm.py'),repo,file,'--state-root',state]));assert.equal(x.all_fresh_now,true);assert.ok(x.function_claims>0);return x;}
const old='def quote(item, qty):\n    return f"{item}:{qty}"\n';const fresh='def quote(item, qty, currency):\n    return f"{item}:{qty}:{currency}"\n';const app='from dep import quote\n\ndef main():\n    return "pending"\n';
test('real C1 engine and local_warm: two explicit cognition recovery generations', async()=>{try{
fs.mkdirSync(repo);fs.mkdirSync(observations,{recursive:true});run(['git','init','-q',repo]);fs.writeFileSync(path.join(repo,'dep.py'),old);fs.writeFileSync(path.join(repo,'app.py'),app);warm('dep.py');warm('app.py');
const {createJiti}=require('jiti');const m=createJiti(__filename,{fsCache:false})(path.resolve(__dirname,'../index.ts'));
const handlers={};m.default.register({pluginConfig:{python:'python3',tmfRoot:W,repos:[{repoRoot:repo,stateRoot:state}],recoveryObservationRoot:observations},config:{},runtime:{agent:{resolveAgentWorkspaceDir:()=>repo}},on:(n,h)=>handlers[n]=h,session:{workflow:{enqueueNextTurnInjection:async()=>{}}}});
// Synthetic built-in-shaped executors; actual temp-file I/O, NOT installed SDK/host.
const tools={read:{execute:async(id,p)=>({content:[{type:'text',text:fs.readFileSync(p.path,'utf8')}]})},edit:{execute:async(id,p)=>{
 let text=fs.readFileSync(p.path,'utf8');for(const e of p.edits){assert.ok(text.includes(e.oldText));text=text.replace(e.oldText,e.newText)}fs.writeFileSync(p.path,text);
 return {content:[{type:'text',text:`Successfully replaced ${p.edits.length} block(s) in ${p.path}.`}]};}}};
async function call(tool,params,id){const ev={toolName:tool,params,toolCallId:id},ctx={sessionKey:'fixture-session',sessionId:'fixture-session-id',runId:'fixture-run',toolCallId:id,toolName:tool};const gate=await handlers.before_tool_call(ev,ctx);if(gate?.block){evidence.push({kind:'real-hook-block',id,gate});save();return gate;}const result=await tools[tool].execute(id,params);evidence.push({kind:'synthetic-executor-real-file-result',id,tool,params,result,hookScheduling:'manual fixture adapter; not host runtime E2E'});save();assert.notEqual(result.isError,true);await handlers.after_tool_call({...ev,result},ctx);return result;}
const editParams=(oldText,newText)=>({path:path.join(repo,'app.py'),edits:[{oldText,newText}]});
for(const phase of ['1','2']){
 const from=phase==='1'?'return "pending"':"return quote('pen', 2, 'USD')";const target=phase==='1'?"return quote('pen', 2, 'USD')":"return quote('pen', 2, 'EUR')";
 fs.writeFileSync(path.join(repo,'dep.py'),phase==='2'?fresh.replace('{currency}', '{currency.upper()}'):fresh);
 const blocked=await call('edit',editParams(from,"return quote('pen', 2)"),'block-'+phase);assert.match(blocked.blockReason,/\[need_warm\]/);assert.ok(fs.readFileSync(path.join(repo,'app.py'),'utf8').includes(from));
 warm('dep.py');const waitRead=await call('edit',editParams(from,target),'warm-only-'+phase);assert.match(waitRead.blockReason,/\[need_read\]/);
 const readResult=await call('read',{path:path.join(repo,'dep.py')},'read-'+phase);assert.ok(readResult.content[0].text.includes('currency'));
 await call('edit',editParams(from,target),'fix-'+phase);assert.equal(m.debugState().pending,0);
 const tickets=fs.readdirSync(observations).map(n=>path.join(observations,n));const ticket=tickets.find(t=>{const o=JSON.parse(fs.readFileSync(t));return o.canonical_repo_root===repo&&o.identity.toolCallId==='fix-'+phase});assert.ok(ticket);
 const o=JSON.parse(fs.readFileSync(ticket));assert.equal(o.status,'recovery_released_without_consolidation');assert.equal(o.observed_dependencies[0].read_observed,true);
 run(['python3','-B',path.join(__dirname,'helpers/check_lineage.py'),repo,state,cognition,ticket,phase,B]);
 run(['python3','-B','-c',`import sys;sys.path.insert(0,${JSON.stringify(repo)});import app;assert app.main()==${JSON.stringify(phase==='1'?'pen:2:USD':'pen:2:EUR')};print('independent runtime fixture oracle PASS')`]);
 if(phase==='1')warm('app.py');
}
}finally{fs.rmSync(owner,{recursive:true,force:true});}});
