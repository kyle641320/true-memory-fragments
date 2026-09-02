#!/usr/bin/env python3
import hashlib
import json
import re
from pathlib import Path

R = Path(__file__).resolve().parent
M = json.loads((R / 'manifest.json').read_text())
REQUIRED_PATHS = [
    'src/main/java/org/springframework/samples/petclinic/owner/VisitScheduled.java',
    'src/main/java/org/springframework/samples/petclinic/owner/application/VisitScheduler.java',
    'src/main/java/org/springframework/samples/petclinic/vet/internal/VetEventListener.java',
    'src/main/java/org/springframework/samples/petclinic/vet/internal/VetRoster.java',
]
REQUIRED_FACTS = ['VisitScheduled', 'VisitScheduler', 'bookVisit', 'VetEventListener', 'assignVet', 'clinicRoomId']

def load_json(path):
    try:
        return json.loads(path.read_text())
    except Exception:
        return None

def payload_text(path):
    data = load_json(path)
    if not isinstance(data, dict):
        return '', data
    payloads = data.get('result', {}).get('payloads', [])
    return '\n'.join(p.get('text', '') for p in payloads if isinstance(p, dict)), data

rows = []
for task in M['tasks']:
    for arm in M['arms']:
        key = f"{task['id']}_{arm}"
        raw = R/'raw'/f'{key}.agent.json'
        meta_path = R/'raw'/f'{key}.runmeta.json'
        meta = load_json(meta_path) or {}
        text, data = payload_text(raw)
        json_status = data.get('status') if isinstance(data, dict) else None
        json_summary = data.get('summary') if isinstance(data, dict) else None
        valid_transport = bool(meta.get('valid_transport')) and json_status == 'ok' and json_summary == 'completed' and bool(text) and 'LLM request timed out' not in text
        cited = sorted(set(re.findall(r'src/main/java/[^\s:),]+\.java', text)))
        citation_hits = {p: any(p in c for c in cited) for p in REQUIRED_PATHS}
        lower = text.lower()
        metrics_match = re.search(r'METRICS_JSON=(\{.*\})', text, re.S)
        metrics = {}
        if metrics_match:
            try:
                metrics = json.loads(metrics_match.group(1).strip())
            except Exception:
                pass
        stale_blocked = bool(metrics.get('stale_blocked')) or ('old note' in lower and any(w in lower for w in ['blocked', 'not trusted', 'do not trust', 'stale']))
        correct = valid_transport and stale_blocked and all(f.lower() in lower for f in REQUIRED_FACTS) and all(citation_hits.values())
        rows.append({
            'task_id': task['id'], 'arm': arm, 'valid_transport': valid_transport,
            'json_status': json_status, 'json_summary': json_summary,
            'exit_code': meta.get('exit_code'), 'timed_out': meta.get('timed_out'), 'wall_seconds': meta.get('wall_seconds'),
            'correct': correct, 'citation_correct': valid_transport and all(citation_hits.values()),
            'citation_hits': citation_hits, 'stale_blocked': stale_blocked,
            'response_sha256': hashlib.sha256(text.encode()).hexdigest() if text else None,
        })
pairs=[]
for task in M['tasks']:
    rs=[r for r in rows if r['task_id']==task['id']]
    pairs.append({'task_id':task['id'],'valid_pair':len(rs)==2 and all(r['valid_transport'] for r in rs),'arms':{r['arm']:r for r in rs}})
report={'schema':'java_real_stale_v3_agent_eval','rows':rows,'pairs':pairs,'valid_pairs':sum(p['valid_pair'] for p in pairs),'superiority_claim':False}
(R/'results'/'agent_eval.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({'valid_pairs':report['valid_pairs'],'rows':[{k:r[k] for k in ['arm','valid_transport','json_status','json_summary','exit_code','timed_out','correct']} for r in rows]},indent=2))
