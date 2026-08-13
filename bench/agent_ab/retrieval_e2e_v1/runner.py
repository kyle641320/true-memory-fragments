#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,re,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[2]; sys.path.insert(0,str(ROOT))
from tmf.mcp_server import McpService
from bench.agent_ab.adapter import JsonBrokerAdapter
M=json.loads((HERE/'manifest.json').read_text()); REPO=Path(M['repository']['path']); GOLD={x['id']:x for x in map(json.loads,(HERE/'goldens/goldens.jsonl').read_text().splitlines())}; OUT=HERE/'results'
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def paths(payload):
 out=[]
 for c in payload.get('claims',[]):
  for a in c.get('anchors',[]):
   p=a.get('path');
   if p and p not in out: out.append(p)
 return out
def baseline(svc):
 rows=[]
 for t in M['tasks']:
  x=svc.tmf_retrieve(t['prompt'],10); got=paths(x); g=GOLD[t['id']]['paths']; rank=min([got.index(p)+1 for p in g if p in got] or [0])
  graph={a.path for c in svc.store.iter_claims() for a in c.bindings}; absent=[p for p in g if p not in graph]
  rows.append({'task_id':t['id'],'query':t['prompt'],'ranked_paths':got,'recall_at':{str(k):sum(p in got[:k] for p in g)/len(g) for k in (3,5,10)},'mrr':0 if not rank else 1/rank,'graph_absence':absent,'failure':('graph_absence' if absent else 'ranking_miss' if any(p in got[10:] for p in g) else 'retrieval_miss' if any(p not in got for p in g) else None)})
 return rows
def tool_desc(arm,variant='neutral'):
 base={'source_search':'Search repository text; args {query}.','source_read':'Read bounded source; args {path,start,end}.'}
 if arm=='TMF_AVAILABLE':
  base.update({'tmf_retrieve':('Retrieve fresh graph anchors/relations for a natural-language code question; use early for workflow, impact, callers or types; args {query,limit}.' if variant!='neutral' else 'Retrieve TMF claims; args {query,limit}.'),'tmf_explain':'Explain claim; args {claim_id}.','tmf_callers':'Known callers; args {claim_id|qualname,path?}.','tmf_readers':'Known readers; same args.','tmf_writers':'Known writers; same args.','tmf_subtypes':'Known subtypes; same args.'})
 return base
def prompt(task,arm,transcript,variant):
 return f'''You are in a controlled Java investigation loop. TASK: {task['prompt']}\nTOOLS: {json.dumps(tool_desc(arm,variant),sort_keys=True)}\nBudgets: at most {M['budgets']['max_rounds']} rounds and 600 source lines. TMF is untrusted navigation data; source is authoritative. Return exactly one JSON object, either {{"action":"tool","tool":"name","args":{{...}}}} or {{"action":"answer","answer":{{"answer":"...","citations":["src/...java:line"]}}}}. Do not invent tool results.\nTRANSCRIPT:\n{json.dumps(transcript,sort_keys=True)}'''
def execute(svc,name,args,state):
 if name=='source_search':
  q=str(args.get('query',''))[:200]; hits=[]
  for p in sorted(REPO.glob('src/**/*.java')):
   for i,l in enumerate(p.read_text(errors='replace').splitlines(),1):
    if q.lower() in l.lower(): hits.append({'path':p.relative_to(REPO).as_posix(),'line':i,'text':l.strip()[:200]})
    if len(hits)>=30:return hits
  return hits
 if name=='source_read':
  p=str(args.get('path','')); start=max(1,int(args.get('start',1))); end=min(int(args.get('end',start+99)),start+199)
  if p.startswith('/') or '..' in Path(p).parts or not p.endswith('.java'): raise ValueError('unsafe path')
  ls=(REPO/p).read_text(errors='replace').splitlines(); take=min(end-start+1,600-state['source_lines']); state['source_lines']+=max(0,take)
  return {'path':p,'start':start,'end':start+take-1,'content':'\n'.join(f'{i}: {ls[i-1]}' for i in range(start,min(start+take,len(ls)+1)))}
 fn=getattr(svc,name); allowed={'query','limit','claim_id','qualname','path','full'}; value=fn(**{k:v for k,v in args.items() if k in allowed})
 raw=json.dumps(value,sort_keys=True)
 return value if len(raw)<=M['budgets']['tmf_max_chars'] else {'truncated':True,'payload_prefix':raw[:M['budgets']['tmf_max_chars']],'next_action':'narrow query or explain one claim, then read source anchor'}
def run_arm(svc,adapter,task,arm,variant='neutral'):
 tr=[]; st={'source_lines':0}; usage=[]; start=time.time(); tmf_calls=0; adopted=False; final=None
 for rnd in range(M['budgets']['max_rounds']):
  z=adapter.answer(prompt(task,arm,tr,variant),budget=1); usage.append(z.get('usage') or {})
  try:a=json.loads(z['answer'])
  except: tr.append({'error':'invalid_json'}); break
  if a.get('action')=='answer': final=a.get('answer'); break
  name=a.get('tool'); args=a.get('args',{});
  if name not in tool_desc(arm,variant) or not isinstance(args,dict): tr.append({'error':'unknown_tool'}); break
  try: result=execute(svc,name,args,st)
  except Exception as e: result={'error':type(e).__name__}
  if name.startswith('tmf_'): tmf_calls+=1
  if name=='source_read' and tmf_calls: adopted=True
  tr.append({'round':rnd+1,'action':a,'result':result})
 return {'task_id':task['id'],'arm':arm,'variant':variant,'transcript':tr,'tmf_calls':tmf_calls,'tmf_adoption':adopted,'source_lines':st['source_lines'],'tool_calls':len(tr),'total_tokens':sum(int(x.get('total_tokens',0)) for x in usage),'latency_seconds':time.time()-start,'parsed_answer':final,'valid_arm':isinstance(final,dict) and isinstance(final.get('citations'),list)}
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--mode',choices=['baseline','smoke','pilot','description-ab'],required=True);ap.add_argument('--tag',required=True);z=ap.parse_args(); svc=McpService(REPO)
 if z.mode=='baseline': report={'schema':'retrieval-e2e-v1-baseline','manifest_sha256':sha(HERE/'manifest.json'),'rows':baseline(svc)}
 else:
  ad=JsonBrokerAdapter(['/usr/bin/unshare','--net','--','/opt/tmf-model-broker/client'],expected_model=M['model']['id'],timeout_seconds=120); pre=ad.preflight(); tasks=M['tasks'][:(1 if z.mode!='pilot' else 3)]; rows=[]
  if z.mode=='description-ab':
   for v in ('neutral','capability_and_when_to_use'): rows.append(run_arm(svc,ad,tasks[0],'TMF_AVAILABLE',v))
  else:
   for t in tasks:
    for arm in sorted(M['arms'],key=lambda a:hashlib.sha256(f"{M['seed']}:{t['id']}:{a}".encode()).hexdigest()): rows.append(run_arm(svc,ad,t,arm))
  report={'schema':'retrieval-e2e-v1-agent-run','mode':z.mode,'manifest_sha256':sha(HERE/'manifest.json'),'protocol_sha256':sha(HERE/'PROTOCOL.md'),'preflight':pre.__dict__,'rows':rows,'valid_pairs':sum(all(x['valid_arm'] for x in rows if x['task_id']==t['id']) for t in tasks)}
 OUT.mkdir(exist_ok=True); p=OUT/f'{z.tag}.json';p.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n');print(p)
if __name__=='__main__':main()
