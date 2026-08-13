import csv,json
from pathlib import Path
R=Path(__file__).parent;o=json.loads((R/'results/smoke-2pair.json').read_text()); rows=[r for p in o['pairs'] for r in p['rows']]
fields=['task_id','arm','valid','success','citation_success','adoption','stale_error','attribution','source_reads','source_files','source_lines','source_bytes','tool_calls','tests','prompt_tokens','completion_tokens','injection_tokens','wall_seconds']
out=[]
for r in rows:
 t=r['telemetry'];out.append({**{k:r.get(k) for k in fields[:8]},**{k:t.get(k) for k in fields[8:]}})
with (R/'results/paired.csv').open('w',newline='') as f:w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(out)
arm={}
for a in ('SOURCE_ONLY','TMF_MIDDLEWARE'):
 rr=[x for x in out if x['arm']==a];arm[a]={'n':len(rr),'successes':sum(x['success'] for x in rr),'success_rate':sum(x['success'] for x in rr)/len(rr),'adoptions':sum(x['adoption'] for x in rr),'source_reads':sum(x['source_reads'] for x in rr),'source_bytes':sum(x['source_bytes'] for x in rr),'tool_calls':sum(x['tool_calls'] for x in rr),'prompt_tokens':sum(x['prompt_tokens'] for x in rr),'completion_tokens':sum(x['completion_tokens'] for x in rr),'injection_tokens':sum(x['injection_tokens'] for x in rr),'wall_seconds':sum(x['wall_seconds'] for x in rr)}
a={'valid_pairs':o['valid_pairs'],'attempted_pairs':len(o['pairs']),'full_run_executed':False,'stop_gate':'FAILED: fresh adoption 0; required >=1','product_decision':'TMF_MIDDLEWARE agent outcome value remains unproven; do not recommend for production value/cost claims. Mechanism remains qualified separately.','arms':arm,'errors':{'memory_caused':0,'stale_memory_caused':0,'post_reread_agent_failure':0,'baseline_agent_failure':0,'output_contract':0,'tool_runtime':0,'mechanism_errors':0}}
(R/'results/audit.json').write_text(json.dumps(a,indent=2)+'\n')
lines=['# Human audit — agent_middleware_value_v1','','Real `gpt-5.6-sol` controlled-tool Agent smoke: **2/2 valid paired sequences**. Both arms succeeded on both tasks. TMF adoption was **0/2**, so the frozen smoke stop gate fired and the 10-pair full run was not executed. No tuning followed.','','| Task | Type | SOURCE | TMF | Adoption | Source reads S/T |','|---|---|---:|---:|---:|---:|']
for p in o['pairs']:
 s=next(x for x in p['rows'] if x['arm']=='SOURCE_ONLY');t=next(x for x in p['rows'] if x['arm']=='TMF_MIDDLEWARE');lines.append(f"| {p['task_id']} | {next(x['kind'] for x in json.loads((R/'tasks.json').read_text()) if x['id']==p['task_id'])} | {int(s['success'])} | {int(t['success'])} | {int(t['adoption'])} | {s['telemetry']['source_reads']}/{t['telemetry']['source_reads']} |")
lines += ['','There were no attributed Agent, stale-memory, middleware, contract, or runtime errors. The negative outcome is specifically failure to demonstrate adoption/cost value, not a mechanism failure. Small N; no statistical claim.','',f"Aggregate telemetry: `{json.dumps(arm,sort_keys=True)}`"]
(R/'results/HUMAN_AUDIT.md').write_text('\n'.join(lines)+'\n')
