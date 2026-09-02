#!/usr/bin/env python3
import json
import re
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tmf.store import Store
from tmf.git import GitRepo
from tmf.freshness import check_freshness

R = Path(__file__).resolve().parent
repo = Path('/root/.openclaw/workspace/experiments/tmf-java-real-v3/petclinic-event-type')
git = GitRepo(repo)
claims = []
for claim in Store(repo).iter_claims():
    raw = json.dumps(claim.to_dict())
    if 'VisitBooked' in raw:
        f = check_freshness(git, claim)
        claims.append({'id': claim.id, 'fresh': f.fresh, 'stale_bindings': f.stale_bindings, 'kind': claim.body.get('edge_kind') or claim.body.get('node_kind'), 'qualname': claim.body.get('qualname') or claim.body.get('type_qualname')})
paths = {
    'event': repo/'src/main/java/org/springframework/samples/petclinic/owner/VisitScheduled.java',
    'producer': repo/'src/main/java/org/springframework/samples/petclinic/owner/application/VisitScheduler.java',
    'listener': repo/'src/main/java/org/springframework/samples/petclinic/vet/internal/VetEventListener.java',
    'consumer': repo/'src/main/java/org/springframework/samples/petclinic/vet/internal/VetRoster.java',
}
source_checks = {}
for key, path in paths.items():
    txt = path.read_text()
    source_checks[key] = {
        'path': str(path.relative_to(repo)),
        'has_VisitScheduled': 'VisitScheduled' in txt,
        'has_VisitBooked': 'VisitBooked' in txt,
        'lines': [i for i,l in enumerate(txt.splitlines(),1) if 'VisitScheduled' in l or 'publishEvent' in l or 'assignVet' in l or 'void on(' in l][:12],
    }
relevant_kinds = {'publishes_type', 'listens_type', 'uses_type'}
relevant = [c for c in claims if c['kind'] in relevant_kinds or (c['kind'] == 'class' and c['qualname'] == 'VisitBooked')]
summary = {
    'old_visitbooked_claims': len(claims),
    'event_contract_relevant_claims': len(relevant),
    'stale_relevant_claims': sum(not c['fresh'] for c in relevant),
    'all_event_contract_relevant_claims_stale': bool(relevant) and all(not c['fresh'] for c in relevant),
    'current_event_type': 'VisitScheduled' if all(source_checks[k]['has_VisitScheduled'] for k in ['event','producer','listener','consumer']) else 'unknown',
    'current_sources_have_no_VisitBooked': all(not v['has_VisitBooked'] for v in source_checks.values()),
    'verdict': 'DETERMINISTIC_STALE_TASK_VALID' if relevant and all(not c['fresh'] for c in relevant) and all(not v['has_VisitBooked'] for v in source_checks.values()) else 'FAIL',
}
out={'schema':'java_real_stale_v3_deterministic_eval','repo':str(repo),'summary':summary,'claims':claims,'event_contract_relevant_claims':relevant,'source_checks':source_checks}
(R/'results'/'deterministic_eval.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(summary,indent=2))
