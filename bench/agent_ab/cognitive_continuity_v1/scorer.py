#!/usr/bin/env python3
import csv,json,sys
from pathlib import Path
p=Path(sys.argv[1]);d=json.loads(p.read_text());rows=[]
for pair in d['pairs']:
 x={r['arm']:r for r in pair['rows']};s=x['SOURCE_CONTINUITY'];t=x['TMF_CONTINUITY'];rows.append({'task_id':pair['task_id'],'valid':pair['valid'],'scenario':next(r for r in pair['rows'])['task_id'],'source_success':s['success'],'tmf_success':t['success'],'adoption':t['adoption'],'source_repeat_bytes':s['phase_b']['telemetry']['repeat_bytes'],'tmf_repeat_bytes':t['phase_b']['telemetry']['repeat_bytes'],'repeat_bytes_saved':s['phase_b']['telemetry']['repeat_bytes']-t['phase_b']['telemetry']['repeat_bytes'],'source_tokens':s['total_tokens'],'tmf_tokens':t['total_tokens'],'token_delta':t['total_tokens']-s['total_tokens'],'stale_error':t['stale_error']})
out=p.with_suffix('.paired.csv');f=out.open('w',newline='');w=csv.DictWriter(f,fieldnames=rows[0]);w.writeheader();w.writerows(rows);f.close();print(out)
