#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,time,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[2];sys.path.insert(0,str(ROOT))
from bench.agent_ab.adapter import JsonBrokerAdapter
M=json.loads((HERE/'manifest.json').read_text()); GOLD={x['phase']:x for x in map(json.loads,(HERE/'goldens/goldens.jsonl').read_text().splitlines())}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def tree(ver):
 d=HERE/'fixture'/ver
 return {p.relative_to(d).as_posix():sha(p) for p in sorted(d.rglob('*.java'))}
def read(ver,path):
 p=HERE/'fixture'/ver/path;s=p.read_text();return {'path':path,'lines':len(s.splitlines()),'bytes':len(s.encode()),'content':s}
def claim():
 x=read('base',M['region']['path'])
 return {'identity':M['region']['identity'],'claim':'VIP subtotal >= 100 receives discount 20. OrderService subtracts discount from subtotal.','anchors':[{'path':x['path'],'lines':[3,4,5]}],'provenance':{'file_sha256':tree('base')[x['path']],'tree_fingerprint':fingerprint('base')},'freshness':'fresh'}
def fingerprint(ver):return hashlib.sha256(json.dumps(tree(ver),sort_keys=True).encode()).hexdigest()
def evidence(arm,phase,store):
 ver='mutated' if phase=='mutation_revisit' else 'base'; events=[]; hit=False;adopt=False;blocked=False;lookup_ms=0
 identity=M['unknown']['identity'] if phase=='unknown' else M['region']['identity']
 if arm=='TMF_MEMORY' and phase!='first_visit':
  t=time.perf_counter();hit=identity in store;lookup_ms=(time.perf_counter()-t)*1000
  if hit:
   c=store[identity];fresh=c['provenance']['file_sha256']==tree(ver)[M['region']['path']]
   if fresh: events=[{'kind':'memory','claim':c}];adopt=True
   else: events=[{'kind':'stale_block','identity':identity}, {'kind':'source','data':read(ver,M['region']['path'])}];blocked=True
  else: events=[{'kind':'source','data':read(ver,M['unknown']['path'])}]
 else:
  paths=[M['unknown']['path']] if phase=='unknown' else [M['region']['path'],'com/acme/OrderService.java']
  events=[{'kind':'source','data':read(ver,p)} for p in paths]
 return events,hit,adopt,blocked,lookup_ms
def task_prompt(phase,events):
 # Memory contains no previous answer/transcript; this prompt is reconstructed for a stateless call.
 return 'Controlled code task: '+M['tasks'][phase]+'\nEvidence (source authoritative; stale claims are never included):\n'+json.dumps(events,sort_keys=True)+'\nReturn only JSON {"answer":"concise factual answer","citations":["path:line"]}.'
def run(mode,tag):
 ad=JsonBrokerAdapter(['/usr/bin/unshare','--net','--','/opt/tmf-model-broker/client'],expected_model=M['model']['id'],timeout_seconds=120);pre=ad.preflight(); seqs=M['sequences'][:1 if mode=='smoke' else 3];rows=[]
 for si,sid in enumerate(seqs):
  for arm in ((['CONTROL','TMF_MEMORY'] if si%2==0 else ['TMF_MEMORY','CONTROL'])):
   store={}; sessions=[]
   for phase in ['first_visit','fresh_revisit','unknown','mutation_revisit']:
    ev,hit,adopt,blocked,lms=evidence(arm,phase,store);prompt=task_prompt(phase,ev);started=time.perf_counter();z=ad.answer(prompt,budget=1);lat=time.perf_counter()-started
    try: ans=json.loads(z['answer'])
    except: ans={}
    if arm=='TMF_MEMORY' and phase=='first_visit':store[M['region']['identity']]=claim()
    src=[e['data'] for e in ev if e['kind']=='source'];g=GOLD[phase];text=str(ans.get('answer','')).lower();cites=ans.get('citations',[]);correct=all(x.lower() in text for x in g['must_contain']) and any(g['citation'] in x for x in cites)
    sessions.append({'phase':phase,'broker_call_id':hashlib.sha256((sid+arm+phase+str(time.time_ns())).encode()).hexdigest()[:16],'valid':isinstance(ans.get('answer'),str) and isinstance(cites,list),'correct':correct,'answer':ans,'memory_hit':hit,'memory_adoption':adopt,'stale_blocked':blocked,'source_lines':sum(x['lines'] for x in src),'source_files':len(src),'source_bytes':sum(x['bytes'] for x in src),'prompt_tokens':int((z.get('usage')or{}).get('prompt_tokens',0)),'completion_tokens':int((z.get('usage')or{}).get('completion_tokens',0)),'total_tokens':int((z.get('usage')or{}).get('total_tokens',0)),'latency_seconds':lat,'tmf_lookup_ms':lms,'stale_trust_error':phase=='mutation_revisit' and adopt})
   rows.append({'sequence':sid,'arm':arm,'memory_store':store if arm=='TMF_MEMORY' else None,'sessions':sessions})
 rep={'schema':'revisit-memory-v1-run','mode':mode,'frozen_sha256':sha(HERE/'FROZEN.sha256'),'preflight':pre.__dict__,'pre_tree':tree('base'),'post_tree':tree('mutated'),'pre_fingerprint':fingerprint('base'),'post_fingerprint':fingerprint('mutated'),'rows':rows}
 out=HERE/'results'/f'{tag}.json';out.write_text(json.dumps(rep,indent=2,sort_keys=True)+'\n');print(out)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--mode',choices=['smoke','pilot'],required=True);a.add_argument('--tag',required=True);z=a.parse_args();run(z.mode,z.tag)
