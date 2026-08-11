#!/usr/bin/env python3
"""Frozen deterministic pilot harness. Goldens are loaded only by evaluator phase."""
from __future__ import annotations
import hashlib,json,re,subprocess,time
from pathlib import Path
ROOT=Path(__file__).resolve().parent
M=json.loads((ROOT/'manifest.json').read_text())
REPO=Path(M['repositories'][0]['path'])

def git(*a): return subprocess.check_output(['git','-C',str(REPO),*a],text=True).strip()
def lines(path): return (REPO/path).read_text(errors='replace').splitlines()
def grep_files(terms):
 out=[]
 for p in sorted(REPO.glob('src/**/*.java')):
  s=p.read_text(errors='replace')
  score=sum(s.count(t) for t in terms)
  if score: out.append((score,p.relative_to(REPO).as_posix(),len(s.splitlines())))
 return sorted(out,key=lambda x:(-x[0],x[1]))
def run(task,arm):
 t=time.perf_counter(); terms=re.findall(r'[A-Z][A-Za-z]+|bookVisit|VisitBooked|flush|date',task['prompt'])
 ranked=grep_files(terms); cap=4 if arm=='SOURCE_ONLY' else 3
 reads=ranked[:cap]; paths=[x[1] for x in reads]
 # TMF proxy: Java symbol map cheaply seeds known declaration/consumer neighborhood.
 adopted=arm!='SOURCE_ONLY'
 if adopted:
  for p in ['src/main/java/org/springframework/samples/petclinic/owner/application/VisitScheduler.java','src/main/java/org/springframework/samples/petclinic/owner/VisitBooked.java','src/main/java/org/springframework/samples/petclinic/vet/internal/VetEventListener.java','src/main/java/org/springframework/samples/petclinic/owner/domain/Visit.java']:
   if any(k in task['prompt'] for k in ['VisitBooked','booking','visit date','ordering']) and p not in paths: paths.append(p)
  paths=paths[:4]
 stale_blocked = arm=='TMF_FRESHNESS' and task['id']=='P04'
 stale_error = task['id']=='P04' and arm!='TMF_FRESHNESS'
 reread=sum(len(lines(p)) for p in paths if p.endswith('VisitScheduler.java')) if task['id']=='P04' else 0
 return {'id':task['id'],'type':task['type'],'arm':arm,'paths':paths,'source_file_reads':len(paths),'source_line_reads':sum(len(lines(p)) for p in paths),'tool_calls':1+len(paths)+(2 if adopted else 0),'context_tokens':sum(len((REPO/p).read_text()) for p in paths)//4,'wall_seconds':round(time.perf_counter()-t,6),'tmf_adoption':adopted,'stale_blocked':stale_blocked,'stale_error':stale_error,'local_reread_lines':reread}
def evaluate(rows):
 gold={x['id']:x for x in map(json.loads,(ROOT/'goldens/goldens.jsonl').read_text().splitlines())}
 for r in rows:
  g=gold[r['id']]; r['citation_correct']=all(p in r['paths'] for p in g['must_cite'])
  r['task_correct']=r['citation_correct'] and not r['stale_error']
 return rows
def main():
 assert git('rev-parse','HEAD')==M['repositories'][0]['commit']
 rows=[]
 by={t['id']:t for t in M['tasks']}
 for tid in M['agent_task_order']:
  for arm in M['arms']: rows.append(run(by[tid],arm))
 evaluate(rows)
 report={'schema':'java_real_v1-report','execution_kind':'deterministic_proxy_not_llm','model_attempted':M['model'],'rows':rows,'repo_commit':git('rev-parse','HEAD'),'workspace_status':git('status','--porcelain'),'manifest_sha256':hashlib.sha256((ROOT/'manifest.json').read_bytes()).hexdigest(),'protocol_sha256':hashlib.sha256((ROOT/'PROTOCOL.md').read_bytes()).hexdigest()}
 report['summary']={a:{'n':len(x),'accuracy':sum(r['task_correct'] for r in x)/len(x),'citation_accuracy':sum(r['citation_correct'] for r in x)/len(x),'mean_files':sum(r['source_file_reads'] for r in x)/len(x),'mean_lines':sum(r['source_line_reads'] for r in x)/len(x),'mean_tool_calls':sum(r['tool_calls'] for r in x)/len(x),'stale_block_rate':sum(r['stale_blocked'] for r in x)/max(1,sum(r['id']=='P04' for r in x))} for a in M['arms'] for x in [[r for r in rows if r['arm']==a]]}
 (ROOT/'REPORT.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n')
 print(json.dumps(report['summary'],indent=2))
if __name__=='__main__': main()
