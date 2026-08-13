#!/usr/bin/env python3
import argparse,json
from pathlib import Path
H=Path(__file__).resolve().parent;M=json.loads((H/'manifest.json').read_text())
def audit(path):
 r=json.loads(Path(path).read_text());issues=[]
 if not r['preflight'].get('stateless') or r['preflight'].get('model')!=M['model']['id']:issues.append('preflight')
 for row in r['rows']:
  nav=row.get('prior_navigation_state') or {}
  if any(k in nav for k in ('answer','prompt','golden','transcript','task')):issues.append('answer_or_prompt_leak')
  for x in row['sessions']:
   if x['source_lines']>M['budget']['max_source_lines'] or x['source_bytes']>M['budget']['max_source_bytes']:issues.append('source_budget')
   if x['source_files']!=len({e.get('model_action',{}).get('path') for e in x['transcript'] if e.get('model_action',{}).get('action')=='read'}):issues.append('distinct_path_metric')
   for e in x['transcript']:
    tools=e.get('available_tools',[])
    if row['arm']=='TMF_TOOL' and 'tmf_lookup' not in tools:issues.append('tool_missing')
    if row['arm']!='TMF_TOOL' and 'tmf_lookup' in tools:issues.append('tool_leak')
    if row['arm']!='TMF_INJECT_ONLY' and e.get('injection') is not None:issues.append('inject_leak')
   if x['injection_fired'] and (not x['injection_before_first_read'] or (x['trigger_provenance'] or {}).get('provenance')!='prior_tool_trace'):issues.append('bad_pre_read_trigger')
  ss={x['phase']:x for x in row['sessions']}
  if row['arm']=='TMF_INJECT_ONLY':
   if not ss['fresh_revisit']['injection_hit']:issues.append('fresh_miss')
   if not ss['unknown_region']['injection_hit']:issues.append('conservative_unknown_not_injected')
   if not ss['unknown_region']['injection_noise']:issues.append('noise_not_counted')
   if not ss['semantic_mutation']['injection_stale_pointer'] or ss['semantic_mutation']['injection_hit']:issues.append('stale_fact')
   if not ss['unrelated_mutation']['injection_hit']:issues.append('unrelated_invalidated')
 seqs=sorted({z['sequence'] for z in r['rows']});valid=sum(all(x['valid'] and x['correct'] and x['citation_ok'] for row in r['rows'] if row['sequence']==s for x in row['sessions']) for s in seqs)
 phases={}
 for ph in M['phases']:
  phases[ph]={}
  for arm in M['arms']:
   xs=[x for row in r['rows'] if row['arm']==arm for x in row['sessions'] if x['phase']==ph];n=len(xs)
   phases[ph][arm]={'n':n,'accuracy':sum(x['correct'] for x in xs)/n,'citation':sum(x['citation_ok'] for x in xs)/n,'fresh_direct_answer_rate':sum(x['injection_adoption'] for x in xs)/n,'source_lines':sum(x['source_lines'] for x in xs),'source_bytes':sum(x['source_bytes'] for x in xs),'distinct_files':sum(x['source_files'] for x in xs),'read_calls':sum(x['read_calls'] for x in xs),'total_tokens':sum(x['total_tokens'] for x in xs),'injection_tokens':sum(x['injection_tokens'] for x in xs),'latency_seconds':sum(x['latency_seconds'] for x in xs),'tmf_calls':sum(x['tmf_calls'] for x in xs),'tmf_adoptions':sum(x['tmf_adoption'] for x in xs),'inject_hits':sum(x['injection_hit'] for x in xs),'inject_adoptions':sum(x['injection_adoption'] for x in xs),'inject_noise':sum(x['injection_noise'] for x in xs),'repairs':sum(x['format_repair_used'] for x in xs)}
 stale=[x for row in r['rows'] if row['arm']=='TMF_INJECT_ONLY' for x in row['sessions'] if x['phase']=='semantic_mutation'];fresh=phases['fresh_revisit'];gate=(fresh['TMF_INJECT_ONLY']['accuracy']>=fresh['SOURCE_ONLY']['accuracy'] and (fresh['TMF_INJECT_ONLY']['read_calls']<fresh['SOURCE_ONLY']['read_calls'] or fresh['TMF_INJECT_ONLY']['source_lines']<fresh['SOURCE_ONLY']['source_lines'] or fresh['TMF_INJECT_ONLY']['total_tokens']<fresh['SOURCE_ONLY']['total_tokens']))
 metrics={'valid_sequences':valid,'stale_errors':sum(x['stale_trust_error'] for row in r['rows'] for x in row['sessions']),'localized_precision':1.0 if stale and all(x['source_files']==1 and x['read_calls']>=1 for x in stale) else 0,'localized_read_calls':sum(x['read_calls'] for x in stale),'product_gate':gate}
 passed=not issues and valid==len(seqs) and metrics['stale_errors']==0 and metrics['localized_precision']==1 and gate;out={'pass':passed,'issues':sorted(set(issues)),'metrics':metrics,'phases':phases};q=Path(path).with_suffix('.audit.json');q.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');q.with_suffix('.audit.md').write_text(f"# v2 Audit\n\npass: **{passed}**; valid: **{valid}/{len(seqs)}**; issues: `{out['issues']}`; product gate: **{gate}**\n\n```json\n{json.dumps(phases,indent=2)}\n```\n");print(q);return out
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('report');x=a.parse_args();raise SystemExit(0 if audit(x.report)['pass'] else 1)
