#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,importlib.util,json,shutil,subprocess,tempfile,time,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[2]
spec=importlib.util.spec_from_file_location('frozen_mw',ROOT/'bench/agent_ab/middleware_hardening_v1/middleware.py'); mw=importlib.util.module_from_spec(spec);sys.modules['frozen_mw']=mw;spec.loader.exec_module(mw)
from bench.agent_ab.adapter import JsonBrokerAdapter
M=json.loads((HERE/'manifest.json').read_text()); G={x['id']:x['golden'] for x in map(json.loads,(HERE/'goldens/goldens.jsonl').read_text().splitlines())}
TASKS={x['id']:x for x in M['tasks']}
def tokens(s): return (len(s)+3)//4
def valid_path(w,p):
 q=(w/p).resolve(); return q if q==w or w in q.parents else None
def test_cmd(task,w):
 if task['language']=='python': return ['python3','test_task.py']
 return ['sh','-c','javac *.java && java TaskTest']
def execute(tid,arm,broker):
 t=TASKS[tid]; src=HERE/'fixtures'/tid/'base'; td=Path(tempfile.mkdtemp(prefix=f'tmf-{tid}-{arm}-')); w=td/'repo';shutil.copytree(src,w)
 # common real-source familiarization, then transcript discarded
 entry=w/t['entry']; old=entry.read_bytes(); claim=mw.Claim(f'{tid}-entry','fixture-'+tid,'base@45ab3e4',t['entry'],tid,'agent',None,None,mw.digest(old),1)
 if t['scenario']=='semantic':
  s=entry.read_text(); s=s.replace('100','120').replace('return Codec.encode(s)','return Codec.encode(s.trim())').replace('n % 2 != 0','n % 3 != 0'); entry.write_text(s)
 sysmsg=f'''You are a stateless coding agent in a frozen experiment. Work only via JSON actions. Task: {t['prompt']}\nAvailable actions: {{"action":"list"}}, {{"action":"read","path":"relative"}}, {{"action":"search","query":"text"}}, {{"action":"edit","path":"relative","old":"exact","new":"replacement"}}, {{"action":"test"}}, {{"action":"final","answer":string,"citations":["path:line"]}}. One action only per response, strict JSON. Source is authoritative.''' 
 history=[]; telemetry={'tool_calls':0,'source_reads':0,'source_files':set(),'source_lines':0,'source_bytes':0,'tests':0,'prompt_tokens':0,'completion_tokens':0,'injection_tokens':0}; final=None; invalid=False; state=mw.GateState(); injected=[]; start=time.time()
 for turn in range(M['budgets']['max_turns']):
  prompt=sysmsg+'\n'+('\n'.join(history) if history else 'Begin.')
  telemetry['prompt_tokens']+=tokens(prompt); r=broker.answer(prompt,budget=1); raw=r['answer'];telemetry['completion_tokens']+=tokens(raw)
  try:a=json.loads(raw)
  except Exception:
   history.append('SYSTEM: invalid JSON; schema repair allowed once.');
   if invalid: break
   invalid=True;continue
  act=a.get('action'); telemetry['tool_calls']+=1
  if act=='list': out={'files':sorted(p.name for p in w.iterdir() if p.is_file() and p.suffix not in('.class',))}
  elif act=='search':
   q=str(a.get('query','')); hits=[]
   for p in w.iterdir():
    if p.is_file() and p.suffix in ('.py','.java'):
     for i,line in enumerate(p.read_text(errors='replace').splitlines(),1):
      if q.lower() in line.lower():hits.append(f'{p.name}:{i}:{line}')
   out={'hits':hits[:30]}
  elif act=='read':
   p=valid_path(w,str(a.get('path','')))
   if not p or not p.is_file():out={'error':'invalid path'}
   else:
    data=p.read_bytes(); payload={'kind':'MISS','items':[]}
    if arm=='TMF_MIDDLEWARE':
     target=mw.Target('fixture-'+tid,'base@45ab3e4',p.name,tid,'agent',None,None,str(turn)); prior=target
     payload,state=mw.before_read(target,prior,[claim],data); telemetry['injection_tokens']+=tokens(json.dumps(payload));injected.append(payload)
    lines=p.read_text(errors='replace').splitlines(); telemetry['source_reads']+=1;telemetry['source_files'].add(p.name);telemetry['source_lines']+=len(lines);telemetry['source_bytes']+=len(data)
    mw.record_read(state,path=p.name,start=1,end=max(1,len(lines)),success=True,source_hash=mw.digest(data))
    out={'middleware':payload if arm=='TMF_MIDDLEWARE' else None,'path':p.name,'content':'\n'.join(f'{i+1}: {x}' for i,x in enumerate(lines))}
  elif act=='edit':
   if arm=='TMF_MIDDLEWARE' and not mw.allow_final_or_edit(state):out={'error':'blocked: reread stale affected source first'}
   else:
    p=valid_path(w,str(a.get('path',''))); oldx=str(a.get('old',''));new=str(a.get('new',''))
    if not p or not p.is_file() or p.read_text().count(oldx)!=1:out={'error':'edit requires one exact match'}
    else:p.write_text(p.read_text().replace(oldx,new));out={'edited':p.name}
  elif act=='test':
   telemetry['tests']+=1; cp=subprocess.run(test_cmd(t,w),cwd=w,text=True,capture_output=True,timeout=20);out={'exit':cp.returncode,'stdout':cp.stdout[-1000:],'stderr':cp.stderr[-1000:]}
  elif act=='final':
   if arm=='TMF_MIDDLEWARE' and not mw.allow_final_or_edit(state):out={'error':'blocked: reread stale affected source first'}
   else: final=a;break
  else: out={'error':'unknown action'}
  history.extend(['AGENT:'+raw,'TOOL:'+json.dumps(out,ensure_ascii=False)])
 telemetry['wall_seconds']=time.time()-start; telemetry['source_files']=sorted(telemetry['source_files'])
 kind=t['kind']; success=False; cite=False
 if kind in ('understanding','cross_file_trace'):
  text=(final or {}).get('answer','').lower(); keys={'A01':['sum','tax'],'A02':['25','attempt'],'A05':['discount'],'A06':['codec','encode'],'A09':['no','moon_phase'],'A10':['multipl']}; success=all(k in text for k in keys[tid]); cite=bool((final or {}).get('citations'))
  success=success and cite
 else:
  cp=subprocess.run(test_cmd(t,w),cwd=w,text=True,capture_output=True,timeout=20); success=cp.returncode==0
 adoption=arm=='TMF_MIDDLEWARE' and success and any(x.get('kind')=='FRESH' for x in injected) and t['entry'] not in telemetry['source_files']
 stale_error=any(x.get('kind')=='STALE' and any('fact' in json.dumps(i) for i in x.get('items',[])) for x in injected)
 return {'task_id':tid,'arm':arm,'valid':final is not None,'success':success,'citation_success':cite,'adoption':adoption,'stale_error':stale_error,'mechanism_error':stale_error,'attribution':None if success else ('output-contract' if final is None else ('baseline-agent-failure' if arm=='SOURCE_ONLY' else ('post-reread-agent-failure' if t['scenario']=='semantic' else 'memory-caused' if adoption else 'output-contract'))),'final':final,'telemetry':telemetry,'injections':injected}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--smoke',action='store_true');ap.add_argument('--tag',default='run');a=ap.parse_args()
 for line in (HERE/'FROZEN.sha256').read_text().splitlines():h,p=line.split('  ');assert hashlib.sha256((HERE/p).read_bytes()).hexdigest()==h
 assert subprocess.check_output(['git','-C',str(ROOT),'rev-parse','HEAD'],text=True).strip()==M['base_commit']
 b=JsonBrokerAdapter(['/opt/tmf-model-broker/client'],expected_model=M['model'],timeout_seconds=M['budgets']['timeout_seconds']);pre=b.preflight(); ids=M['smoke'] if a.smoke else M['full_order']; rows=[]
 for tid in ids:
  for arm in M['order'][tid]: rows.append(execute(tid,arm,b)); print(tid,arm,rows[-1]['valid'],rows[-1]['success'],flush=True)
 pairs=[]
 for tid in ids:
  rr=[x for x in rows if x['task_id']==tid];pairs.append({'task_id':tid,'valid':all(x['valid'] for x in rr),'rows':rr})
 out={'schema':'agent-middleware-value-v1-results','tag':a.tag,'preflight':pre.__dict__,'manifest_sha256':hashlib.sha256((HERE/'manifest.json').read_bytes()).hexdigest(),'pairs':pairs,'valid_pairs':sum(x['valid'] for x in pairs)}
 p=HERE/'results'/f'{a.tag}.json';p.write_text(json.dumps(out,indent=2)+'\n');print(p)
if __name__=='__main__':main()
