#!/usr/bin/env python3
"""Versioned real-model pilot over the frozen v1 tasks; never writes formal REPORT.*."""
from __future__ import annotations
import argparse, hashlib, json, os, re, socket, subprocess, sys, time
from pathlib import Path
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[2]
sys.path.insert(0,str(ROOT))
from bench.agent_ab.adapter import JsonBrokerAdapter
P=json.loads((HERE/'broker_pilot_manifest.json').read_text()); M=json.loads((HERE/'manifest.json').read_text())
REPO=Path(M['repositories'][0]['path']); OUT=HERE/'broker_pilot_v1'
SECRET_NAMES=('AISZ_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY','OPENCLAW_GATEWAY_TOKEN','AWS_SECRET_ACCESS_KEY')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*a): return subprocess.check_output(['git','-C',str(REPO),*a],text=True).strip()
def source_bundle(task):
 terms=set(re.findall(r'[A-Z][A-Za-z]+|bookVisit|flush|date',task['prompt'])); ranked=[]
 for p in sorted(REPO.glob('src/**/*.java')):
  s=p.read_text(errors='replace'); score=sum(s.count(t) for t in terms)
  if score: ranked.append((score,p))
 ranked.sort(key=lambda x:(-x[0],str(x[1])))
 files=[]; total=0
 for _,p in ranked:
  ls=p.read_text(errors='replace').splitlines()
  if len(files)>=M['budgets']['source_files'] or total+len(ls)>M['budgets']['source_lines']: continue
  files.append({'path':p.relative_to(REPO).as_posix(),'lines':len(ls),'content':'\n'.join(f'{i+1}: {v}' for i,v in enumerate(ls))}); total+=len(ls)
  if len(files)>=4: break
 return files
def tmf_bundle(task):
 cp=subprocess.run([sys.executable,str(HERE/'petclinic_tmf_locator.py'),task['prompt'],'--max-chars',str(M['budgets']['context_tokens'])],text=True,capture_output=True,timeout=120,check=False)
 if cp.returncode: raise RuntimeError('tmf locator failed: '+cp.stderr[-300:])
 obj=json.loads(cp.stdout); return obj['result']
def assignment(tid):
 arms=P['arms'][:]; arms.sort(key=lambda a:hashlib.sha256(f"{P['seed']}:{tid}:{a}".encode()).hexdigest()); return arms
def prompt_for(task,arm,src,tmf):
 evidence='\n\n'.join(f"FILE {f['path']} ({f['lines']} lines)\n{f['content']}" for f in src)
 extra='' if arm=='SOURCE_ONLY' else '\n\nTMF THIN CONTEXT (navigation hints only; source is authoritative):\n'+json.dumps(tmf,ensure_ascii=False,sort_keys=True)
 return f"""You are one isolated arm in a frozen Java A/B pilot. Answer only the unchanged task below. Use only supplied evidence. No tools, network, memory, or hidden state are available. TMF is navigation evidence, never authority. Cite exact file:line. Do not claim tests were run. Return concise JSON with keys answer, citations (array), confidence.\n\nTASK {task['id']}: {task['prompt']}\n\nSOURCE EVIDENCE:\n{evidence}{extra}"""
def probe_isolation():
 code="""import json,os,socket; out={'ambient_secrets':[k for k in %r if k in os.environ],'inet_blocked':False};\ntry: socket.socket().connect(('1.1.1.1',53))\nexcept OSError: out['inet_blocked']=True\nprint(json.dumps(out))"""%(SECRET_NAMES,)
 env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'}
 cp=subprocess.run(['unshare','--net','--',sys.executable,'-c',code],env=env,text=True,capture_output=True,check=True); return json.loads(cp.stdout)
def run_pair(tid,adapter):
 task=next(t for t in M['tasks'] if t['id']==tid); src=source_bundle(task); tmf=tmf_bundle(task); rows=[]
 for arm in assignment(tid):
  before=set(OUT.glob('*')); prompt=prompt_for(task,arm,src,tmf); start=time.time(); result=adapter.answer(prompt,budget=1); wall=time.time()-start
  try: parsed=json.loads(result['answer']); answer_valid=isinstance(parsed,dict) and isinstance(parsed.get('citations'),list)
  except Exception: parsed=None; answer_valid=False
  rows.append({'task_id':tid,'arm':arm,'assignment_order':len(rows),'prompt_sha256':hashlib.sha256(prompt.encode()).hexdigest(),'source_manifest':[{'path':f['path'],'lines':f['lines'],'sha256':hashlib.sha256(f['content'].encode()).hexdigest()} for f in src], 'tmf_included':arm=='TMF_MAP','tmf_sha256':hashlib.sha256(json.dumps(tmf,sort_keys=True).encode()).hexdigest() if arm=='TMF_MAP' else None,'broker':{k:result.get(k) for k in ('protocol','model','calls','request_id','usage')},'raw_answer':result['answer'],'parsed_answer':parsed,'answer_schema_valid':answer_valid,'wall_seconds':wall,'budget_valid':result.get('calls')==1,'valid_arm':answer_valid and result.get('calls')==1})
 return {'pair_id':tid,'order':assignment(tid),'rows':rows,'valid_pair':all(r['valid_arm'] for r in rows),'cross_arm_state_files':sorted(str(x) for x in set(OUT.glob('*'))-before)}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--pairs',type=int,default=P['pairs']); ap.add_argument('--tag',required=True); a=ap.parse_args()
 assert 1<=a.pairs<=len(P['task_order']); assert sha(HERE/'manifest.json')==P['base_manifest_sha256']; assert M['model']['id'].split('/',1)[-1]==P['model']['id']; assert git('rev-parse','HEAD')==M['repositories'][0]['commit']
 OUT.mkdir(exist_ok=True); adapter=JsonBrokerAdapter(['/usr/bin/unshare','--net','--',P['broker']['client']],expected_model=P['model']['id'],timeout_seconds=P['model']['timeout_seconds']); pre=adapter.preflight(); isolation=probe_isolation()
 pairs=[]
 for tid in P['task_order'][:a.pairs]: pairs.append(run_pair(tid,adapter))
 report={'schema':P['schema']+'-report','tag':a.tag,'execution_kind':'real_broker_isolated_evidence_agent','created_at':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime()),'pilot_manifest_sha256':sha(HERE/'broker_pilot_manifest.json'),'base_manifest_sha256':sha(HERE/'manifest.json'),'protocol_sha256':sha(HERE/'PROTOCOL.md'),'repo_commit':git('rev-parse','HEAD'),'repo_status':git('status','--porcelain'),'preflight':pre.__dict__,'isolation_probe':isolation,'pairs':pairs,'valid_pairs':sum(x['valid_pair'] for x in pairs),'invalid_pairs':sum(not x['valid_pair'] for x in pairs)}
 path=OUT/f'{a.tag}.json'; path.write_text(json.dumps(report,indent=2,ensure_ascii=False,sort_keys=True)+'\n'); print(path)
if __name__=='__main__': main()
