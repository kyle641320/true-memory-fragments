#!/usr/bin/env python3
from __future__ import annotations
import json, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT))
from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.store import Store
from tmf.warm import warm_repo
def run(a,c): subprocess.run(a,cwd=c,check=True,capture_output=True)
def produce():
 with tempfile.TemporaryDirectory() as td:
  repo=Path(td)/'repo'; shutil.copytree(ROOT/'fixtures/java-feign-heldout',repo); run(['git','init'],repo); run(['git','config','user.email','heldout@example.invalid'],repo); run(['git','config','user.name','TMF heldout'],repo); run(['git','add','.'],repo); run(['git','commit','-m','fixture'],repo); warm_repo(repo)
  apis=sorted((c for c in Store(repo).iter_claims() if c.scope=='api'),key=lambda c:c.body.get('handler_qualname','')); client=[c for c in apis if c.body.get('rpc_adapter')][0]; server=[c for c in apis if not c.body.get('rpc_adapter')][0]
  checks={'client_exact':client.body['service_name']=='inventory' and client.body['service_url']=='https://inventory.invalid' and client.body['route_path']=='/api/stock','server_reuse':server.body['route_path']=='/api/stock','dual_fresh':len(client.bindings)==2 and check_freshness(GitRepo(repo),client).fresh,'decoy_absent':len(apis)==2}
  old=client; f=repo/'src/main/java/heldout/rpc/InventoryClient.java'; f.write_text(f.read_text().replace('https://inventory.invalid','https://changed.invalid')); checks['route_mutation_stales']=not check_freshness(GitRepo(repo),old).fresh; warm_repo(repo); checks['route_mutation_reconciles']=Store(repo).get_claim(old.id) is not None
  f.write_text(f.read_text().replace('String stock();','String stock(String sku);')); checks['method_mutation_stales']=not check_freshness(GitRepo(repo),Store(repo).get_claim(old.id)).fresh; warm_repo(repo)
  f.unlink(); warm_repo(repo); checks['deletion_reconciles']=not any(c.body.get('rpc_adapter') for c in Store(repo).iter_claims())
  return checks

def main():
 a=produce(); b=produce(); ok=all(a.values()) and a==b; report={'format':'tmf.java-feign-qualification.v1','checks':a,'deterministic':a==b,'precision':1.0 if ok else 0.0,'recall':1.0 if ok else 0.0,'limitations':['source-only exact explicit imports and literals','no runtime, discovery, balancing, serialization, auth, retry, fallback or client/server equivalence inference']}; out=ROOT/'reports/java-feign-qualification'; out.mkdir(parents=True,exist_ok=True); (out/'report.json').write_text(json.dumps(report,indent=2,sort_keys=True)+'\n'); (out/'report.md').write_text(f"# Java Feign qualification: {'PASS' if ok else 'FAIL'}\n\n- Checks: {sum(map(bool,a.values()))}/{len(a)}\n- Precision/recall: {report['precision']:.3f}/{report['recall']:.3f}\n- Deterministic repeat: {a==b}\n"); print(f"JAVA FEIGN QUALIFICATION: {'PASS' if ok else 'FAIL'} ({sum(map(bool,a.values()))}/{len(a)})"); return 0 if ok else 1
if __name__=='__main__': raise SystemExit(main())
