#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,shutil,subprocess,tempfile,time
from pathlib import Path
from bench.agent_ab.adapter import JsonBrokerAdapter
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[2]; M=json.loads((HERE/'manifest.json').read_text()); TASKS={x['id']:x for x in M['tasks']}
def tok(s):return (len(s)+3)//4
def testcmd(t):return ['python3','test_task.py'] if t['language']=='python' else ['sh','-c','javac *.java && java TaskTest']
def mutate(t,w):
 p=w/t['entry'];s=p.read_text();s=s.replace('100','120').replace('return Codec.encode(s)','return Codec.encode(s.trim())').replace('n % 2 != 0','n % 3 != 0');p.write_text(s)
def safe(w,x):
 p=(w/x).resolve();return p if (p==w or w in p.parents) and p.is_file() else None
def loop(broker,t,w,prompt,phase,env,claim=None,stale=False,covered=None):
 sys=f'''You are a coding agent in phase {phase} of a continuous logical workflow. Work only via one strict JSON action per response. Task: {prompt}\nContinuity envelope: {json.dumps(env)}\nActions: {{"action":"list"}}, {{"action":"read","path":"relative"}}, {{"action":"search","query":"text"}}, {{"action":"edit","path":"relative","old":"exact","new":"replacement"}}, {{"action":"test"}}, {{"action":"final","answer":string,"citations":["path:line"]}}. Source is authoritative.'''
 injection=''
 if claim and not stale: injection='\nFRESH source-bound TMF memory (may be used without rereading): '+json.dumps(claim)
 if claim and stale: injection='\nSTALE memory notice: prior source hash changed; old fact is withheld. Read the localized affected source before relying on it or editing.'
 sys+=injection; hist=[];met={'tool_calls':0,'source_reads':0,'source_files':[],'source_lines':0,'source_bytes':0,'repeat_reads':0,'repeat_files':[],'repeat_lines':0,'repeat_bytes':0,'tests':0,'prompt_tokens':0,'completion_tokens':0,'injection_tokens':tok(injection),'wall_seconds':0}; final=None;invalid=0;edited=False;start=time.time()
 for _ in range(M['budgets']['phase_a_max_turns' if phase=='A' else 'phase_b_max_turns']):
  q=sys+'\n'+'\n'.join(hist or ['Begin.']);met['prompt_tokens']+=tok(q);raw=broker.answer(q,budget=1)['answer'];met['completion_tokens']+=tok(raw)
  try:a=json.loads(raw)
  except:invalid+=1;hist+=['SYSTEM: invalid JSON; repair.'];continue
  met['tool_calls']+=1;act=a.get('action');out={}
  if act=='list':out={'files':sorted(x.name for x in w.iterdir() if x.is_file() and x.suffix!='.class')}
  elif act=='search':
   hits=[];needle=str(a.get('query','')).lower()
   for p in w.iterdir():
    if p.suffix in ('.py','.java'):
     for i,l in enumerate(p.read_text().splitlines(),1):
      if needle in l.lower():hits.append(f'{p.name}:{i}:{l}')
   out={'hits':hits[:30]}
  elif act=='read':
   p=safe(w,str(a.get('path','')))
   if not p:out={'error':'invalid path'}
   else:
    data=p.read_bytes();ls=p.read_text(errors='replace').splitlines();met['source_reads']+=1;met['source_files'].append(p.name);met['source_lines']+=len(ls);met['source_bytes']+=len(data)
    if covered and p.name in covered:met['repeat_reads']+=1;met['repeat_files'].append(p.name);met['repeat_lines']+=len(ls);met['repeat_bytes']+=len(data)
    out={'path':p.name,'content':'\n'.join(f'{i}: {l}' for i,l in enumerate(ls,1))}
  elif act=='edit':
   p=safe(w,str(a.get('path','')));old=str(a.get('old',''));new=str(a.get('new',''))
   if stale and t['entry'] not in met['source_files']:out={'error':'blocked: localized stale source read required'}
   elif not p or p.read_text().count(old)!=1:out={'error':'edit requires one exact match'}
   else:p.write_text(p.read_text().replace(old,new));edited=True;out={'edited':p.name}
  elif act=='test':
   met['tests']+=1;c=subprocess.run(testcmd(t),cwd=w,text=True,capture_output=True,timeout=20);out={'exit':c.returncode,'stdout':c.stdout[-800:],'stderr':c.stderr[-800:]}
  elif act=='final':
   if stale and t['entry'] not in met['source_files']:out={'error':'blocked: localized stale source read required'}
   else:final=a;break
  else:out={'error':'unknown action'}
  hist += ['AGENT:'+raw,'TOOL:'+json.dumps(out)]
 met['wall_seconds']=time.time()-start; met['source_files']=sorted(set(met['source_files']));met['repeat_files']=sorted(set(met['repeat_files']))
 return final,met,edited

def score(t,w,final):
 if t['kind'] in ('local_edit','test_fix'):
  c=subprocess.run(testcmd(t),cwd=w,text=True,capture_output=True,timeout=20);return c.returncode==0,False
 text=((final or {}).get('answer') or '').lower();keys={'A01':['120'],'A02':['25'],'A05':['discount'],'A06':['codec','encode'],'A09':['no','moon_phase'],'A10':['multipl']};cite=bool((final or {}).get('citations'));return all(k in text for k in keys[t['id']]) and cite,cite
def execute(tid,arm,broker):
 t=TASKS[tid];td=Path(tempfile.mkdtemp(prefix='cc-'));w=td/'repo';shutil.copytree(HERE/'fixtures'/tid/'base',w);aid='agent-'+tid;wid='workflow-'+tid+'-'+arm.lower();env={'logical_agent_id':aid,'workflow_id':wid,'prior_task_complete':False,'memory_ids':[],'provenance':[]}
 fa,ma,_=loop(broker,t,w,t['phase_a_prompt'],'A',env);covered={p:(w/p).read_bytes() for p in ma['source_files'] if (w/p).exists()};memid='mem-'+tid;claim={'memory_id':memid,'provenance':{'paths':sorted(covered),'sha256':{p:hashlib.sha256(x).hexdigest() for p,x in covered.items()}},'claim':(fa or {}).get('answer',''),'citations':(fa or {}).get('citations',[])};env={'logical_agent_id':aid,'workflow_id':wid,'prior_task_complete':fa is not None,'memory_ids':[memid],'provenance':[claim['provenance']]}
 if t['scenario']=='semantic':mutate(t,w)
 stale=any(hashlib.sha256((w/p).read_bytes()).hexdigest()!=claim['provenance']['sha256'][p] for p in covered)
 fb,mb,_=loop(broker,t,w,t['phase_b_prompt'],'B',env,claim if arm=='TMF_CONTINUITY' else None,stale if arm=='TMF_CONTINUITY' else False,covered);success,cite=score(t,w,fb);adopt=arm=='TMF_CONTINUITY' and t['scenario']=='fresh' and success and bool(covered) and mb['repeat_reads']==0;stale_err=arm=='TMF_CONTINUITY' and stale and t['entry'] not in mb['source_files']
 return {'task_id':tid,'arm':arm,'valid':fa is not None and fb is not None,'phase_a_complete':fa is not None,'success':success,'citation_success':cite,'adoption':adopt,'stale_detected':stale,'stale_error':stale_err,'attribution':None if success else ('baseline' if arm=='SOURCE_CONTINUITY' else 'post-reread' if stale and mb['repeat_reads'] else 'memory-caused'),'continuity_envelope':env,'claim':claim if arm=='TMF_CONTINUITY' else None,'phase_a':{'final':fa,'telemetry':ma},'phase_b':{'final':fb,'telemetry':mb},'total_tokens':ma['prompt_tokens']+ma['completion_tokens']+mb['prompt_tokens']+mb['completion_tokens']+mb['injection_tokens']}
def main():
 a=argparse.ArgumentParser();a.add_argument('--smoke',action='store_true');a.add_argument('--tag',default='run');z=a.parse_args()
 for line in (HERE/'FROZEN.sha256').read_text().splitlines():h,p=line.split('  ');assert hashlib.sha256((HERE/p).read_bytes()).hexdigest()==h
 b=JsonBrokerAdapter(['/opt/tmf-model-broker/client'],expected_model=M['model'],timeout_seconds=M['budgets']['timeout_seconds']);pre=b.preflight();ids=M['smoke'] if z.smoke else M['full_order'];rows=[]
 for tid in ids:
  for arm in M['order'][tid]:rows.append(execute(tid,arm,b));print(tid,arm,rows[-1]['valid'],rows[-1]['success'],rows[-1]['adoption'],flush=True)
 pairs=[{'task_id':i,'valid':all(r['valid'] for r in rows if r['task_id']==i),'rows':[r for r in rows if r['task_id']==i]} for i in ids];out={'schema':'cognitive-continuity-v1-results','tag':z.tag,'preflight':pre.__dict__,'pairs':pairs,'valid_pairs':sum(p['valid'] for p in pairs),'adoption':sum(r['adoption'] for r in rows)};(HERE/'results'/f'{z.tag}.json').write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__':main()
