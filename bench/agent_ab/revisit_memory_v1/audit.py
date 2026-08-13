#!/usr/bin/env python3
import argparse,json,hashlib
from pathlib import Path
H=Path(__file__).resolve().parent
A={'identity','claim','anchors','provenance','freshness'}
def audit(p):
 r=json.loads(Path(p).read_text()); issues=[]
 if not r['preflight']['stateless']:issues.append('broker_not_stateless')
 for row in r['rows']:
  if row['arm']=='CONTROL' and row['memory_store'] is not None:issues.append('control_memory')
  if row['memory_store']:
   for c in row['memory_store'].values():
    if set(c)!=A:issues.append('store_allowlist')
    if any(k in json.dumps(c).lower() for k in ('transcript','golden','previous answer','prompt')):issues.append('memory_leak')
  ss={x['phase']:x for x in row['sessions']}
  if ss['unknown']['memory_hit'] or ss['unknown']['memory_adoption']:issues.append('unknown_injected')
  if row['arm']=='TMF_MEMORY' and (not ss['mutation_revisit']['stale_blocked'] or ss['mutation_revisit']['memory_adoption']):issues.append('stale_not_blocked')
 valid=all(x['valid'] and x['correct'] for row in r['rows'] for x in row['sessions'])
 tm=[row for row in r['rows'] if row['arm']=='TMF_MEMORY']; stale=[{x['phase']:x for x in row['sessions']}['mutation_revisit'] for row in tm]
 metrics={'valid_sequences':sum(all(x['valid'] and x['correct'] for x in row['sessions']) for row in r['rows'])//2,'stale_detection_precision':1.0 if all(x['stale_blocked'] for x in stale) else 0,'stale_detection_recall':1.0 if all(x['stale_blocked'] for x in stale) else 0,'localized_reread_precision':1.0 if all(x['source_files']==1 for x in stale) else 0,'localized_reread_recall':1.0 if all(x['source_files']==1 for x in stale) else 0,'stale_errors':sum(x['stale_trust_error'] for x in stale)}
 out={'pass':not issues and valid and all(v==1 for k,v in metrics.items() if k.endswith('precision') or k.endswith('recall')) and metrics['stale_errors']==0,'issues':issues,'metrics':metrics}
 q=Path(p).with_suffix('.audit.json');q.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(q);return out
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('report');z=a.parse_args();raise SystemExit(0 if audit(z.report)['pass'] else 1)
