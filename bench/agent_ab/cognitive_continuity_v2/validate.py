#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,shutil,subprocess,tempfile
from pathlib import Path
import sys
HERE=Path(__file__).resolve().parent; sys.path.insert(0,str(HERE.parents[2]))
from tmf.git import GitRepo
from tmf.derive import derive_claims_for_path
from tmf.store import Store

def run(cmd,cwd): return subprocess.run(cmd,cwd=cwd,text=True,capture_output=True,timeout=30)
def init_repo(src):
 d=Path(tempfile.mkdtemp())/'repo';shutil.copytree(src,d)
 for c in (['git','init','-b','master'],['git','config','user.email','bench@local'],['git','config','user.name','bench'],['git','add','.'],['git','commit','-m','fixture']):
  r=run(c,d);assert r.returncode==0,r.stderr
 return d
def claim_match(c,want):
 body=c.body
 return all(body.get(k)==v or body.get('graph',{}).get(k)==v or any(isinstance(x,dict) and x.get(k)==v for x in body.get('graph',{}).get('callees',[])) for k,v in want.items())
def validate():
 ts=json.loads((HERE/'tasks.json').read_text()); errors=[]; report=[]
 assert len(ts)==10 and len({t['id'] for t in ts})==10
 for t in ts:
  w=init_repo(HERE/'fixtures'/t['id']/'base'); entry=t['entry']; pre=None;post=None
  if 'oracle' in t:
   a=run(t['oracle'],w); pre=a.stdout.strip();
   if a.returncode or pre!=t['golden']:errors.append(f"{t['id']}: oracle {a.returncode}/{pre!r} != {t['golden']!r}")
  if 'test' in t:
   a=run(t['test'],w)
   if a.returncode==0:errors.append(f"{t['id']}: initial test unexpectedly passes")
   p=w/entry;s=p.read_text();patch=t['patch']
   if s.count(patch['old'])!=1:errors.append(f"{t['id']}: patch assertion")
   else:p.write_text(s.replace(patch['old'],patch['new']))
   if run(t['test'],w).returncode:errors.append(f"{t['id']}: patched test fails")
  claims=derive_claims_for_path(GitRepo(w),entry);store=Store(w)
  for c in claims:store.put_claim(c)
  persisted=[store.get_claim(c.id) for c in claims]
  coverage=[c.id for c in claims if t.get('coverage') and claim_match(c,t['coverage'])]
  if 'mutation' in t:
   m=t['mutation'];p=w/m.get('path',entry);s=p.read_text();assert s.count(m['old'])==1;p.write_text(s.replace(m['old'],m['new']))
   if 'oracle' in t:post=run(t['oracle'],w).stdout.strip();
   if 'oracle' in t and post==pre:errors.append(f"{t['id']}: semantic oracle unchanged")
   # old persisted claim must no longer match current blob for a changed binding
   changed=str(p.relative_to(w)); fresh=[]
   for c in persisted:
    if c and any(b.path==changed and b.file_blob==GitRepo(w).blob_sha(changed) for b in c.bindings):fresh.append(c.id)
   if fresh:errors.append(f"{t['id']}: old claims incorrectly fresh {fresh}")
  report.append({'id':t['id'],'derived_claims':len(claims),'coverage_claim_ids':coverage,'oracle_before':pre,'oracle_after_mutation':post})
 return {'schema':'cognitive-continuity-v2-preflight','pass':not errors,'errors':errors,'tasks':report}
def frozen():
 rows=[]
 for p in sorted([HERE/'tasks.json',HERE/'goldens/goldens.json',*filter(Path.is_file,(HERE/'fixtures').rglob('*'))]):rows.append(f"{hashlib.sha256(p.read_bytes()).hexdigest()}  {p.relative_to(HERE)}")
 return '\n'.join(rows)+'\n'
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--write-freeze',action='store_true');ap.add_argument('--verify-freeze',action='store_true');a=ap.parse_args()
 out=validate();(HERE/'preflight.json').write_text(json.dumps(out,indent=2)+'\n')
 if a.write_freeze:
  assert out['pass'],out;(HERE/'FROZEN.sha256').write_text(frozen())
 if a.verify_freeze: assert (HERE/'FROZEN.sha256').read_text()==frozen()
 print(json.dumps(out,indent=2));raise SystemExit(0 if out['pass'] else 1)
if __name__=='__main__':main()
