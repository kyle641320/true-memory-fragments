#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,os,re,socket,subprocess,sys,time
from pathlib import Path
HERE=Path(__file__).resolve().parent; ROOT=HERE.parents[2]; sys.path.insert(0,str(ROOT))
from bench.agent_ab.adapter import JsonBrokerAdapter
M=json.loads((HERE/'manifest.json').read_text()); REPO=Path(M['repository']['path']); OUT=HERE/'results'
SECRETS=('AISZ_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY','OPENCLAW_GATEWAY_TOKEN')
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def git(*a): return subprocess.check_output(['git','-C',str(REPO),*a],text=True).strip()
def assignment(tid): return sorted(M['arms'],key=lambda a:hashlib.sha256(f"{M['seed']}:{tid}:{a}".encode()).hexdigest())
def catalog(task):
 terms=set(re.findall(r'[A-Z][A-Za-z]+|[a-z][A-Z][A-Za-z]+',task['prompt'])); rows=[]
 for p in sorted(REPO.glob('src/**/*.java')):
  s=p.read_text(errors='replace'); score=sum(s.count(t) for t in terms)
  rows.append((score,p.relative_to(REPO).as_posix(),len(s.splitlines())))
 return [{'path':p,'lines':n} for score,p,n in sorted(rows,key=lambda x:(-x[0],x[1]))[:M['budgets']['selection_candidates']]]
def tmf(task):
 old=Path('bench/agent_ab/java_real_v1/petclinic_tmf_locator.py')
 cp=subprocess.run([sys.executable,str(ROOT/old),task['prompt'],'--max-chars',str(M['budgets']['tmf_max_chars'])],capture_output=True,text=True,timeout=120)
 if cp.returncode: raise RuntimeError(cp.stderr[-500:])
 return json.loads(cp.stdout)['result']
def selection_prompt(task,cat,arm,t):
 extra='' if arm=='SOURCE_ONLY' else '\nTMF NAVIGATION HINTS (source is authoritative):\n'+json.dumps(t,sort_keys=True)
 return f"""Frozen Java source-navigation step. Select up to {M['budgets']['selected_files']} paths likely needed to answer the task. Choose only from CANDIDATES. Return JSON {{\"paths\":[...]}}. Do not answer the task.\nTASK: {task['prompt']}\nCANDIDATES:\n"""+'\n'.join(f"{x['path']} ({x['lines']} lines)" for x in cat)+extra
def parse_selection(raw,cat):
 try: x=json.loads(raw); requested=x['paths'] if isinstance(x,dict) else []
 except Exception: requested=[]
 allowed={x['path'] for x in cat}; chosen=[]
 for p in requested:
  if isinstance(p,str) and p in allowed and p not in chosen: chosen.append(p)
 for x in cat:
  if len(chosen)>=M['budgets']['selected_files']: break
  if x['path'] not in chosen: chosen.append(x['path'])
 return chosen[:M['budgets']['selected_files']], isinstance(requested,list)
def evidence(paths,cat):
 order=paths+[x['path'] for x in cat if x['path'] not in paths]; out=[]; remaining=M['budgets']['source_lines']
 for rel in order:
  if remaining<=0: break
  lines=(REPO/rel).read_text(errors='replace').splitlines(); take=min(len(lines),remaining)
  out.append({'path':rel,'start':1,'end':take,'lines':take,'content':'\n'.join(f'{i+1}: {v}' for i,v in enumerate(lines[:take]))}); remaining-=take
 if remaining: raise RuntimeError('candidate catalog cannot fill source budget')
 return out
def answer_prompt(task,ev):
 body='\n\n'.join(f"FILE {x['path']} lines 1-{x['end']}\n{x['content']}" for x in ev)
 return f"""Frozen Java answer step. Use only supplied source; source is authoritative. Return concise JSON with keys answer, citations (array), confidence. Every citation must be exact file:line or file:start-end and supported by evidence.\nTASK: {task['prompt']}\nSOURCE EVIDENCE:\n{body}"""
def probe():
 code="import json,os,socket; x={'ambient_secrets':[k for k in %r if k in os.environ],'inet_blocked':False};\ntry: socket.socket().connect(('1.1.1.1',53))\nexcept OSError: x['inet_blocked']=True\nprint(json.dumps(x))"%(SECRETS,)
 return json.loads(subprocess.check_output(['unshare','--net','--',sys.executable,'-c',code],text=True,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'}))
def run_arm(task,arm,cat,t,adapter):
 started=time.time(); sp=selection_prompt(task,cat,arm,t); a=adapter.answer(sp,budget=1); paths,sel_valid=parse_selection(a['answer'],cat); ev=evidence(paths,cat); ap=answer_prompt(task,ev); b=adapter.answer(ap,budget=1)
 try: parsed=json.loads(b['answer']); schema=isinstance(parsed,dict) and isinstance(parsed.get('citations'),list)
 except Exception: parsed=None; schema=False
 usage=[a.get('usage') or {},b.get('usage') or {}]; total=sum(int(u.get('total_tokens',0)) for u in usage)
 tmf_text=json.dumps(t,sort_keys=True); adoption=arm=='TMF_MAP' and any(p in tmf_text for p in paths)
 return {'task_id':task['id'],'arm':arm,'selection_paths':paths,'selection_schema_valid':sel_valid,'candidate_sha256':hashlib.sha256(json.dumps(cat,sort_keys=True).encode()).hexdigest(),'source_manifest':[{k:x[k] for k in ('path','start','end','lines')} for x in ev],'source_lines':sum(x['lines'] for x in ev),'source_files':len(ev),'tool_calls':2,'tmf_available':arm=='TMF_MAP','tmf_adoption':adoption,'broker_calls':2,'usage':usage,'total_tokens':total,'latency_seconds':time.time()-started,'raw_answer':b['answer'],'parsed_answer':parsed,'answer_schema_valid':schema,'valid_arm':sel_valid and schema and sum(x['lines'] for x in ev)==M['budgets']['source_lines'] and a.get('calls')==1 and b.get('calls')==1}
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('--pairs',type=int,required=True); ap.add_argument('--tag',required=True); z=ap.parse_args()
 assert 1<=z.pairs<=3 and git('rev-parse','HEAD')==M['repository']['commit'] and subprocess.run(['git','-C',str(REPO),'diff','--quiet']).returncode==0 and subprocess.run(['git','-C',str(REPO),'diff','--cached','--quiet']).returncode==0
 adapter=JsonBrokerAdapter(['/usr/bin/unshare','--net','--','/opt/tmf-model-broker/client'],expected_model=M['model']['id'],timeout_seconds=M['model']['timeout_seconds']); pre=adapter.preflight(); iso=probe(); pairs=[]
 for task in M['tasks'][:z.pairs]:
  cat=catalog(task); t=tmf(task); rows=[run_arm(task,a,cat,t,adapter) for a in assignment(task['id'])]; pairs.append({'pair_id':task['id'],'order':assignment(task['id']),'rows':rows,'valid_pair':all(r['valid_arm'] for r in rows) and len({r['candidate_sha256'] for r in rows})==1 and len({r['source_lines'] for r in rows})==1})
 report={'schema':'tmf-java-agent-ab-v2-run','tag':z.tag,'manifest_sha256':sha(HERE/'manifest.json'),'protocol_sha256':sha(HERE/'PROTOCOL.md'),'created_at':time.strftime('%FT%TZ',time.gmtime()),'repo_commit':git('rev-parse','HEAD'),'preflight':pre.__dict__,'isolation_probe':iso,'pairs':pairs,'valid_pairs':sum(p['valid_pair'] for p in pairs)}
 OUT.mkdir(exist_ok=True); p=OUT/f'{z.tag}.json'; p.write_text(json.dumps(report,indent=2,sort_keys=True)+'\n'); print(p)
if __name__=='__main__': main()
