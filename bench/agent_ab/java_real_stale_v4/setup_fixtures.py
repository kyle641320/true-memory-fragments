#!/usr/bin/env python3
from __future__ import annotations
import json, shutil, subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
M = json.loads((HERE / 'manifest.json').read_text())
BASE = Path(M['source_repository']['path'])
OUT = Path('/root/.openclaw/workspace/experiments/tmf-java-real-v4')
ROOT = HERE.parents[2]

REPLACEMENTS = {
    'petclinic_api_route_mutated': [
        ('src/main/java/org/springframework/samples/petclinic/owner/ui/OwnerController.java', '@GetMapping("/owners/{ownerId}")', '@GetMapping("/owners/{ownerId}/profile")'),
    ],
    'petclinic_cache_name_mutated': [
        ('src/main/java/org/springframework/samples/petclinic/vet/internal/VetRepository.java', '@Cacheable("vets")', '@Cacheable("activeVets")'),
    ],
    'petclinic_transaction_readonly_mutated': [
        ('src/main/java/org/springframework/samples/petclinic/vet/internal/VetRepository.java', '@Transactional(readOnly = true)\n\t@Cacheable("vets")\n\tCollection<Vet> findAll() throws DataAccessException;', '@Transactional(readOnly = false)\n\t@Cacheable("vets")\n\tCollection<Vet> findAll() throws DataAccessException;'),
    ],
}

def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

def init_repo(repo: Path):
    run(['git','init'], repo)
    run(['git','config','user.email','tmf@example.com'], repo)
    run(['git','config','user.name','tmf'], repo)
    run(['git','add','.'], repo)
    run(['git','commit','-m','base before stale mutation'], repo)

def warm(repo: Path):
    run(['python3','-m','tmf.cli','warm','--repo',str(repo)], ROOT)

def mutate(repo: Path, reps):
    for rel, old, new in reps:
        p = repo / rel
        text = p.read_text()
        n = text.count(old)
        if n < 1:
            raise RuntimeError(f'{rel}: old text not found: {old!r}')
        text = text.replace(old, new)
        p.write_text(text)
    run(['git','add','.'], repo)
    run(['git','commit','-m','controlled stale-contract mutation'], repo)

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    rows=[]
    for repo_info in M['repositories']:
        rid=repo_info['id']; dest=Path(repo_info['path'])
        if dest.exists(): shutil.rmtree(dest)
        shutil.copytree(BASE, dest, ignore=shutil.ignore_patterns('target','.git','.tmf','.gradle','build'))
        init_repo(dest)
        base_commit=run(['git','rev-parse','HEAD'], dest).stdout.strip()
        warm(dest)
        mutate(dest, REPLACEMENTS[rid])
        mutation_commit=run(['git','rev-parse','HEAD'], dest).stdout.strip()
        rows.append({'id':rid,'path':str(dest),'base_commit':base_commit,'mutation_commit':mutation_commit,'mutation':repo_info['mutation']})
    (HERE/'results'/'setup_fixtures.json').write_text(json.dumps({'schema':'java_real_stale_v4_setup','repositories':rows},indent=2)+'\n')
    print(json.dumps({'created':len(rows),'repositories':rows},indent=2))
if __name__ == '__main__': main()
