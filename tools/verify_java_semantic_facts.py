#!/usr/bin/env python3
import argparse,json,sys
from pathlib import Path
from tmf.java_semantic import FORMAT, JavaSemanticFactsBackend
from tmf.git import GitRepo
from tmf.derive import derive_claims_for_path
p=argparse.ArgumentParser(); p.add_argument('repo'); p.add_argument('facts'); p.add_argument('path'); a=p.parse_args()
b=JavaSemanticFactsBackend(a.facts,enabled=True); claims=derive_claims_for_path(GitRepo(a.repo),a.path,semantic_backend=b)
out={'format':FORMAT,'status':b.last_status,'claim_ids':sorted(c.id for c in claims if c.id.startswith('claim_java_semantic_'))}
print(json.dumps(out,sort_keys=True)); sys.exit(0 if out['status'].get('reason')=='accepted' else 1)
