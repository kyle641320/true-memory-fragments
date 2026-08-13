#!/usr/bin/env python3
import argparse,hashlib,json,re
from pathlib import Path
HERE=Path(__file__).resolve().parent; M=json.loads((HERE/'manifest.json').read_text()); G={x['id']:x for x in map(json.loads,(HERE/'goldens/goldens.jsonl').read_text().splitlines())}
def citation_path(c): return c.rsplit(':',1)[0] if isinstance(c,str) and re.match(M['evidence']['citation_regex'],c) else None
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('run'); z=ap.parse_args(); p=Path(z.run); run=json.loads(p.read_text()); rows=[]
 for pair in run['pairs']:
  for r in pair['rows']:
   ans=r.get('parsed_answer') or {}; cites=ans.get('citations',[]); paths={citation_path(c) for c in cites}; supplied={x['path'] for x in r['source_manifest']}; required=set(G[r['task_id']]['must_cite']); citation_ok=bool(cites) and all(x and x in supplied for x in paths); coverage=len(required&paths)/len(required); task_ok=coverage==1.0
   rows.append({'task_id':r['task_id'],'arm':r['arm'],'valid':r['valid_arm'] and citation_ok,'task_correct':task_ok,'citation_correct':citation_ok and task_ok,'required_path_coverage':coverage,'total_tokens':r['total_tokens'],'latency_seconds':r['latency_seconds'],'source_lines':r['source_lines'],'source_files':r['source_files'],'tool_calls':r['tool_calls'],'tmf_adoption':r['tmf_adoption']})
 summary={}
 for arm in M['arms']:
  x=[r for r in rows if r['arm']==arm and r['valid']]; n=len(x); summary[arm]={'n':n,'task_accuracy':sum(r['task_correct'] for r in x)/n if n else None,'citation_accuracy':sum(r['citation_correct'] for r in x)/n if n else None,'mean_tokens':sum(r['total_tokens'] for r in x)/n if n else None,'mean_latency_seconds':sum(r['latency_seconds'] for r in x)/n if n else None,'mean_source_lines':sum(r['source_lines'] for r in x)/n if n else None,'mean_tool_calls':sum(r['tool_calls'] for r in x)/n if n else None,'tmf_adoption_rate':sum(r['tmf_adoption'] for r in x)/n if n else None}
 valid_pairs=sum(all(x['valid'] for x in rows if x['task_id']==q['pair_id']) for q in run['pairs']); floor=all(summary[a]['task_accuracy']==0 for a in M['arms'] if summary[a]['task_accuracy'] is not None)
 out={'schema':'tmf-java-agent-ab-v2-audit','source_run':str(p),'source_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'manifest_sha256':run['manifest_sha256'],'independent_scoring':'frozen required citation paths; no prompt adaptation','valid_pairs':valid_pairs,'rows':rows,'summary':summary,'both_arms_floor':floor,'recommendation':'STOP_NO_EXPANSION: common floor indicates unresolved agent navigation/task mediation; TMF net benefit not demonstrated.' if floor else 'Treat as small pilot only; expand solely under a separately preregistered protocol.'}
 q=p.with_suffix('.audit.json'); q.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n'); print(q)
if __name__=='__main__': main()
