#!/usr/bin/env python3
from __future__ import annotations
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from tmf.store import Store
from tmf.git import GitRepo
from tmf.freshness import check_freshness

HERE=Path(__file__).resolve().parent
M=json.loads((HERE/'manifest.json').read_text())

TARGETS={
 'RV4F01': {
  'repo':'petclinic_api_route_mutated', 'query':'/owners/{ownerId}', 'new':'@GetMapping("/owners/{ownerId}/profile")', 'old':'@GetMapping("/owners/{ownerId}")',
  'paths':['src/main/java/org/springframework/samples/petclinic/owner/ui/OwnerController.java'],
  'claim_filter': lambda raw, body: body.get('qualname') == 'OwnerController.showOwner' and body.get('method') == 'GET' and '/owners/{ownerId}' in raw,
 },
 'RV4F02': {
  'repo':'petclinic_cache_name_mutated', 'query':'vets', 'new':'@Cacheable("activeVets")', 'old':'@Cacheable("vets")',
  'paths':['src/main/java/org/springframework/samples/petclinic/vet/internal/VetRepository.java'],
  'claim_filter': lambda raw, body: body.get('edge_kind') == 'declares_cache_metadata' and body.get('cache_names') == ['vets'],
 },
 'RV4F03': {
  'repo':'petclinic_transaction_readonly_mutated', 'query':'readOnly = true', 'new':'@Transactional(readOnly = false)', 'old':'@Transactional(readOnly = true)',
  'paths':['src/main/java/org/springframework/samples/petclinic/vet/internal/VetRepository.java'],
  'claim_filter': lambda raw, body: body.get('edge_kind') == 'declares_transaction_metadata' and body.get('owner_qualname') == 'VetRepository.findAll',
 },
}

def repo_by_id(rid):
    return next(x for x in M['repositories'] if x['id']==rid)

def line_hits(path:Path,*needles):
    txt=path.read_text()
    return [i for i,l in enumerate(txt.splitlines(),1) if any(n in l for n in needles)]

def main():
    rows=[]
    for task in M['tasks']:
        tid=task['id']; spec=TARGETS[tid]; repo=Path(repo_by_id(spec['repo'])['path'])
        git=GitRepo(repo); store=Store(repo); claims=[]
        for claim in store.iter_claims():
            raw=json.dumps(claim.to_dict(),ensure_ascii=False)
            if spec['claim_filter'](raw, claim.body):
                f=check_freshness(git, claim)
                claims.append({'id':claim.id,'fresh':f.fresh,'kind':claim.body.get('edge_kind') or claim.body.get('node_kind') or claim.body.get('spring_declaration',{}).get('kind'), 'qualname':claim.body.get('qualname') or claim.body.get('owner_qualname'), 'stale_bindings':f.stale_bindings})
        checks={}
        for rel in spec['paths']:
            p=repo/rel; txt=p.read_text()
            has_target_old = spec['old'] in txt
            if tid == 'RV4F03':
                # The Pageable overload still legitimately has readOnly=true; only the no-arg findAll target site matters.
                target_window = txt.split('Collection<Vet> findAll() throws DataAccessException;')[0].split('/**')[-1]
                has_target_old = spec['old'] in target_window
            checks[rel]={'has_new':spec['new'] in txt,'has_target_old':has_target_old,'lines':line_hits(p,spec['new'],spec['old'])}
        relevant=claims
        verdict = 'DETERMINISTIC_STALE_TASK_VALID' if relevant and all(not c['fresh'] for c in relevant) and all(v['has_new'] for v in checks.values()) and not any(v['has_target_old'] for v in checks.values()) else 'FAIL'
        rows.append({'task_id':tid,'repo':str(repo),'old_note':task['old_note'],'claim_count':len(claims),'stale_claim_count':sum(not c['fresh'] for c in claims),'all_claims_stale':bool(claims) and all(not c['fresh'] for c in claims),'source_checks':checks,'claims':claims,'verdict':verdict})
    out={'schema':'java_real_stale_v4_deterministic_eval','rows':rows,'valid_tasks':sum(r['verdict']=='DETERMINISTIC_STALE_TASK_VALID' for r in rows),'all_valid':all(r['verdict']=='DETERMINISTIC_STALE_TASK_VALID' for r in rows)}
    (HERE/'results'/'deterministic_eval.json').write_text(json.dumps(out,indent=2)+'\n')
    print(json.dumps({'valid_tasks':out['valid_tasks'],'all_valid':out['all_valid'],'rows':[{k:r[k] for k in ['task_id','claim_count','stale_claim_count','verdict']} for r in rows]},indent=2))
if __name__=='__main__': main()
