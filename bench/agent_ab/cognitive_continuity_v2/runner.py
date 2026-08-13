#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,shutil,subprocess,tempfile,time,sys
from dataclasses import asdict
from pathlib import Path
HERE=Path(__file__).resolve().parent; sys.path.insert(0,str(HERE.parents[2]))
from bench.agent_ab.adapter import JsonBrokerAdapter
from tmf.git import GitRepo
from tmf.derive import derive_claims_for_path
from tmf.store import Store
ROOT=HERE.parents[2]; TASK_LIST=json.loads((HERE/'tasks.json').read_text()); TASKS={x['id']:x for x in TASK_LIST}; M={'model':'gpt-5.6-sol','budgets':{'phase_a_max_turns':12,'phase_b_max_turns':12,'timeout_seconds':120},'smoke':['B01','B03'],'full_order':[x['id'] for x in TASK_LIST],'order':{x['id']:['SOURCE_CONTINUITY','TMF_CONTINUITY'] if int(x['id'][1:])%2 else ['TMF_CONTINUITY','SOURCE_CONTINUITY'] for x in TASK_LIST}}
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
 if 'test' in t:
  c=subprocess.run(t['test'],cwd=w,text=True,capture_output=True,timeout=20);return c.returncode==0,False
 c=subprocess.run(t['oracle'],cwd=w,text=True,capture_output=True,timeout=20); expected=c.stdout.strip().lower();text=((final or {}).get('answer') or '').lower();cite=bool((final or {}).get('citations'));return expected in text and cite,cite
def execute(tid,arm,broker):
 t=TASKS[tid];td=Path(tempfile.mkdtemp(prefix='cc-'));w=td/'repo';shutil.copytree(HERE/'fixtures'/tid/'base',w);aid='agent-'+tid;wid='workflow-'+tid+'-'+arm.lower();env={'logical_agent_id':aid,'workflow_id':wid,'prior_task_complete':False,'memory_ids':[],'provenance':[]}
 fa,ma,_=loop(broker,t,w,t['phase_a'],'A',env);covered={p:(w/p).read_bytes() for p in ma['source_files'] if (w/p).exists()};memid='mem-'+tid;store=Store(w); derived=[]
 for path in sorted(covered):
  for c in derive_claims_for_path(GitRepo(w),path): store.put_claim(c);derived.append(c)
 claim={'memory_id':memid,'provenance':{'paths':sorted(covered),'sha256':{p:hashlib.sha256(x).hexdigest() for p,x in covered.items()}},'claims':[{'id':c.id,'type':c.scope,'body':c.body,'bindings':[asdict(b) for b in c.bindings]} for c in derived]};env={'logical_agent_id':aid,'workflow_id':wid,'prior_task_complete':fa is not None,'memory_ids':[memid],'provenance':[claim['provenance']]}
 if t['scenario']=='semantic' and t.get('mutation'):
  m=t['mutation'];p=w/m.get('path',t['entry']);p.write_text(p.read_text().replace(m['old'],m['new']))
 stale=any(hashlib.sha256((w/p).read_bytes()).hexdigest()!=claim['provenance']['sha256'][p] for p in covered)
 fb,mb,_=loop(broker,t,w,t['phase_b'],'B',env,claim if arm=='TMF_CONTINUITY' else None,stale if arm=='TMF_CONTINUITY' else False,covered);success,cite=score(t,w,fb);coverage=[c['id'] for c in claim['claims'] if t.get('coverage') and all(c['body'].get(k)==v or c['body'].get('graph',{}).get(k)==v or any(isinstance(x,dict) and x.get(k)==v for x in c['body'].get('graph',{}).get('callees',[])) for k,v in t['coverage'].items())];adopt=arm=='TMF_CONTINUITY' and t['scenario']=='fresh' and success and bool(coverage) and mb['repeat_reads']==0;stale_err=arm=='TMF_CONTINUITY' and stale and t['entry'] not in mb['source_files']
 return {'task_id':tid,'arm':arm,'valid':fa is not None and fb is not None,'phase_a_complete':fa is not None,'success':success,'citation_success':cite,'adoption':adopt,'stale_detected':stale,'stale_error':stale_err,'attribution':None if success else ('baseline' if arm=='SOURCE_CONTINUITY' else 'post-reread' if stale and mb['repeat_reads'] else 'memory-caused'),'continuity_envelope':env,'claim':claim if arm=='TMF_CONTINUITY' else None,'claim_coverage_ids':coverage if arm=='TMF_CONTINUITY' else [],'phase_a':{'final':fa,'telemetry':ma},'phase_b':{'final':fb,'telemetry':mb},'total_tokens':ma['prompt_tokens']+ma['completion_tokens']+mb['prompt_tokens']+mb['completion_tokens']+mb['injection_tokens']}
def main():
 a=argparse.ArgumentParser();a.add_argument('--smoke',action='store_true');a.add_argument('--tag',default='run');z=a.parse_args()
 subprocess.run([sys.executable,str(HERE/'validate.py'),'--verify-freeze'],check=True,stdout=subprocess.DEVNULL)
 b=JsonBrokerAdapter(['/opt/tmf-model-broker/client'],expected_model=M['model'],timeout_seconds=M['budgets']['timeout_seconds']);pre=b.preflight();ids=M['smoke'] if z.smoke else M['full_order'];rows=[]
 for tid in ids:
  for arm in M['order'][tid]:rows.append(execute(tid,arm,b));print(tid,arm,rows[-1]['valid'],rows[-1]['success'],rows[-1]['adoption'],flush=True)
 pairs=[{'task_id':i,'valid':all(r['valid'] for r in rows if r['task_id']==i),'rows':[r for r in rows if r['task_id']==i]} for i in ids];out={'schema':'cognitive-continuity-v2-results','tag':z.tag,'preflight':pre.__dict__,'pairs':pairs,'valid_pairs':sum(p['valid'] for p in pairs),'adoption':sum(r['adoption'] for r in rows)};(HERE/'results').mkdir(exist_ok=True);(HERE/'results'/f'{z.tag}.json').write_text(json.dumps(out,indent=2)+'\n')
if __name__=='__main__':main()
