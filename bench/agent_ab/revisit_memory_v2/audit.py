#!/usr/bin/env python3
import argparse,json
from pathlib import Path
H=Path(__file__).resolve().parent; ALLOW={'identity','claim','anchors','freshness','provenance'}
def audit(path):
 r=json.loads(Path(path).read_text());issues=[]
 if not r['preflight'].get('stateless'):issues.append('broker_not_stateless')
 for row in r['rows']:
  if row['arm']=='CONTROL' and row['memory_store'] is not None:issues.append('control_memory')
  for c in (row['memory_store'] or {}).values():
   if set(c)!=ALLOW:issues.append('memory_allowlist')
   text=json.dumps(c).lower()
   if any(x in text for x in ('transcript','prompt','previous answer','golden','citations')):issues.append('memory_leak')
  ss={x['phase']:x for x in row['sessions']}
  if row['arm']=='TMF_MEMORY':
   if ss['unknown_region']['memory_hit'] or ss['unknown_region']['memory_adoption']:issues.append('unknown_not_miss')
   if not ss['mutation_revisit']['stale_blocked'] or ss['mutation_revisit']['memory_adoption']:issues.append('stale_not_blocked')
  for x in row['sessions']:
   if x['source_lines']>24 or x['source_bytes']>1600:issues.append('budget')
 seqs=sorted(set(x['sequence'] for x in r['rows'])); valid=sum(all(x['valid'] and x['correct'] for row in r['rows'] if row['sequence']==s for x in row['sessions']) for s in seqs)
 tm=[{x['phase']:x for x in row['sessions']} for row in r['rows'] if row['arm']=='TMF_MEMORY']; stale=[x['mutation_revisit'] for x in tm]
 metrics={'valid_sequences':valid,'stale_errors':sum(x['stale_trust_error'] for x in stale),'stale_detection_precision':1.0 if stale and all(x['stale_blocked'] for x in stale) else 0.0,'stale_detection_recall':1.0 if stale and all(x['stale_blocked'] for x in stale) else 0.0,'localized_reread_precision':1.0 if stale and all(x['source_files']==1 for x in stale) else 0.0,'localized_reread_recall':1.0 if stale and all(x['source_files']==1 for x in stale) else 0.0}
 phases={}
 for phase in ['first_visit','fresh_revisit','unknown_region','mutation_revisit']:
  phases[phase]={}
  for arm in ['CONTROL','TMF_MEMORY']:
   xs=[x for row in r['rows'] if row['arm']==arm for x in row['sessions'] if x['phase']==phase]
   phases[phase][arm]={'n':len(xs),'correct_rate':sum(x['correct'] for x in xs)/len(xs),'citation_rate':sum(x['citation_ok'] for x in xs)/len(xs),'source_lines':sum(x['source_lines'] for x in xs),'source_bytes':sum(x['source_bytes'] for x in xs),'prompt_tokens':sum(x['prompt_tokens'] for x in xs),'completion_tokens':sum(x['completion_tokens'] for x in xs),'latency_seconds':sum(x['latency_seconds'] for x in xs),'memory_hits':sum(x['memory_hit'] for x in xs),'memory_adoptions':sum(x['memory_adoption'] for x in xs)}
 passed=not issues and valid==len(seqs) and metrics['stale_errors']==0 and all(metrics[k]==1 for k in ('stale_detection_precision','stale_detection_recall','localized_reread_precision','localized_reread_recall'))
 out={'pass':passed,'issues':issues,'metrics':metrics,'phases':phases};q=Path(path).with_suffix('.audit.json');q.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');q.with_suffix('.audit.md').write_text(f"# Audit\n\npass: **{passed}**; valid sequences: **{valid}/{len(seqs)}**; issues: `{issues}`\n\n```json\n{json.dumps(phases,indent=2)}\n```\n");print(q);return out
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('report');x=a.parse_args();raise SystemExit(0 if audit(x.report)['pass'] else 1)
