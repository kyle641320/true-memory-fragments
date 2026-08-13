#!/usr/bin/env python3
import argparse,json
from pathlib import Path
H=Path(__file__).resolve().parent;M=json.loads((H/'manifest.json').read_text())
def audit(path):
 r=json.loads(Path(path).read_text());issues=[]
 if not r['preflight'].get('stateless') or r['preflight'].get('model')!=M['model']['id']:issues.append('preflight')
 for row in r['rows']:
  for x in row['sessions']:
   tp=x['trigger_provenance'];
   if not tp or tp.get('origin')!='agent_tool_trace':issues.append('trigger_not_trace')
   if x['source_lines']>M['budget']['max_source_lines'] or x['source_bytes']>M['budget']['max_source_bytes']:issues.append('source_budget')
   if x['injection_tokens']>M['budget']['injection_max_tokens']:issues.append('inject_budget')
   for e in x['transcript']:
    tools=e.get('available_tools',[])
    if row['arm']=='TMF_TOOL' and 'tmf_lookup' not in tools:issues.append('tool_missing')
    if row['arm']!='TMF_TOOL' and 'tmf_lookup' in tools:issues.append('tool_leak')
    if row['arm']!='TMF_INJECT_ONLY' and e.get('injection') is not None:issues.append('inject_leak')
  ss={x['phase']:x for x in row['sessions']}
  if row['arm']=='TMF_INJECT_ONLY':
   if not ss['fresh_revisit']['injection_hit']:issues.append('fresh_miss')
   if ss['unknown_region']['injection_hit']:issues.append('unknown_hit')
   if not ss['semantic_mutation']['injection_stale_pointer'] or ss['semantic_mutation']['injection_hit']:issues.append('stale_fact')
   if not ss['unrelated_mutation']['injection_hit']:issues.append('unrelated_invalidated')
 seqs=sorted({x['sequence'] for x in r['rows']});valid=sum(all(x['valid'] and x['correct'] and x['citation_ok'] for row in r['rows'] if row['sequence']==s for x in row['sessions']) for s in seqs)
 phases={}
 for ph in M['phases']:
  phases[ph]={}
  for arm in M['arms']:
   xs=[x for row in r['rows'] if row['arm']==arm for x in row['sessions'] if x['phase']==ph];phases[ph][arm]={'n':len(xs),'accuracy':sum(x['correct'] for x in xs)/len(xs),'citation':sum(x['citation_ok'] for x in xs)/len(xs),'source_lines':sum(x['source_lines'] for x in xs),'source_bytes':sum(x['source_bytes'] for x in xs),'source_files':sum(x['source_files'] for x in xs),'tokens':sum(x['prompt_tokens']+x['completion_tokens'] for x in xs),'injection_tokens':sum(x['injection_tokens'] for x in xs),'latency_seconds':sum(x['latency_seconds'] for x in xs),'tmf_calls':sum(x['tmf_calls'] for x in xs),'tmf_adoptions':sum(x['tmf_adoption'] for x in xs),'inject_hits':sum(x['injection_hit'] for x in xs),'inject_adoptions':sum(x['injection_adoption'] for x in xs),'repairs':sum(x['format_repair_used'] for x in xs)}
 inj=[x for row in r['rows'] if row['arm']=='TMF_INJECT_ONLY' for x in row['sessions']];st=[x for x in inj if x['phase']=='semantic_mutation'];metrics={'valid_sequences':valid,'stale_errors':sum(x['stale_trust_error'] for row in r['rows'] for x in row['sessions']),'stale_precision':1.0 if st and all(x['injection_stale_pointer'] and not x['injection_hit'] for x in st) else 0,'stale_recall':1.0 if st and all(x['injection_stale_pointer'] for x in st) else 0,'localized_precision':1.0 if st and all(x['source_files']==1 for x in st) else 0,'localized_recall':1.0 if st and all(x['source_files']==1 for x in st) else 0}
 passed=not issues and valid==len(seqs) and metrics['stale_errors']==0 and all(metrics[k]==1 for k in ('stale_precision','stale_recall','localized_precision','localized_recall'));out={'pass':passed,'issues':sorted(set(issues)),'metrics':metrics,'phases':phases};q=Path(path).with_suffix('.audit.json');q.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');q.with_suffix('.audit.md').write_text(f"# Audit\n\npass: **{passed}**; valid: **{valid}/{len(seqs)}**; issues: `{out['issues']}`\n\n```json\n{json.dumps(phases,indent=2)}\n```\n");print(q);return out
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('report');x=a.parse_args();raise SystemExit(0 if audit(x.report)['pass'] else 1)
