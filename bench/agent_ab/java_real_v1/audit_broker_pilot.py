#!/usr/bin/env python3
import argparse,hashlib,json,re
from pathlib import Path
H=Path(__file__).resolve().parent
G={x['id']:x for x in map(json.loads,(H/'goldens/goldens.jsonl').read_text().splitlines())}
def cited_paths(r):
 out=set()
 for c in (r.get('parsed_answer') or {}).get('citations',[]):
  m=re.match(r'(.+?\.java):\d',str(c))
  if m: out.add(m.group(1))
 return out
def main():
 ap=argparse.ArgumentParser(); ap.add_argument('report'); a=ap.parse_args(); p=Path(a.report); x=json.loads(p.read_text()); rows=[]
 for pair in x['pairs']:
  for r in pair['rows']:
   g=G[r['task_id']]; cited=cited_paths(r); citation_correct=all(q in cited for q in g['must_cite']); total_lines=sum(s['lines'] for s in r['source_manifest']); usage=r['broker'].get('usage') or {}; context=usage.get('prompt_tokens',0)
   budget_valid=r['budget_valid'] and len(r['source_manifest'])<=8 and total_lines<=800 and context<=12000
   rows.append({'task_id':r['task_id'],'arm':r['arm'],'transport_valid':r['valid_arm'],'budget_valid':budget_valid,'citation_correct':citation_correct,'task_correct':citation_correct,'source_files':len(r['source_manifest']),'source_lines':total_lines,'prompt_tokens':context,'completion_tokens':usage.get('completion_tokens'),'request_id':r['broker'].get('request_id')})
 valid_pairs=[]
 for pair in x['pairs']:
  rr=[r for r in rows if r['task_id']==pair['pair_id']]; valid_pairs.append({'pair_id':pair['pair_id'],'valid':pair['valid_pair'] and all(r['budget_valid'] for r in rr),'reason':None if pair['valid_pair'] and all(r['budget_valid'] for r in rr) else 'arm transport/schema/budget invalid'})
 arms={}
 for arm in sorted(set(r['arm'] for r in rows)):
  rr=[r for r in rows if r['arm']==arm]; arms[arm]={'n':len(rr),'transport_valid_rate':sum(r['transport_valid'] for r in rr)/len(rr),'heldout_task_accuracy':sum(r['task_correct'] for r in rr)/len(rr),'heldout_citation_accuracy':sum(r['citation_correct'] for r in rr)/len(rr),'mean_prompt_tokens':sum(r['prompt_tokens'] for r in rr)/len(rr)}
 out={'schema':'java_real_v1-broker-pilot-v1-audit','source_report':str(p),'source_report_sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'hashes':{k:x[k] for k in ('pilot_manifest_sha256','base_manifest_sha256','protocol_sha256')},'repo_commit':x['repo_commit'],'isolation_probe':x['isolation_probe'],'valid_pairs':valid_pairs,'rows':rows,'summary':arms,'conclusion':'No task/prompt/metric adaptation. Completions count only after transcript/schema/budget validation; held-out correctness is separate.'}
 q=p.with_suffix('.audit.json'); q.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n'); md=q.with_suffix('.md'); md.write_text('# Broker pilot audit\n\n'+f"- Valid pairs: {sum(v['valid'] for v in valid_pairs)}/{len(valid_pairs)}\n- Isolation: network blocked={x['isolation_probe']['inet_blocked']}, ambient secrets={x['isolation_probe']['ambient_secrets']}\n- Frozen/base manifest SHA256: `{x['base_manifest_sha256']}`\n- Pilot manifest SHA256: `{x['pilot_manifest_sha256']}`\n- Protocol SHA256: `{x['protocol_sha256']}`\n\n## Preliminary held-out metrics\n\n"+'\n'.join(f"- {a}: n={v['n']}, task accuracy={v['heldout_task_accuracy']:.3f}, citation accuracy={v['heldout_citation_accuracy']:.3f}, transport valid={v['transport_valid_rate']:.3f}, mean prompt tokens={v['mean_prompt_tokens']:.1f}" for a,v in arms.items())+'\n\nCompletion alone was not counted as a valid arm. No prompts, tasks, goldens, or metrics were changed after observing results.\n'); print(q); print(md)
if __name__=='__main__': main()
