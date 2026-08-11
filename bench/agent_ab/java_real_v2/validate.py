#!/usr/bin/env python3
import hashlib,json,subprocess,sys,tempfile
from pathlib import Path
R=Path(__file__).resolve().parent
for p in R.rglob('*.json'):
    if p.stat().st_size:
        json.loads(p.read_text())
m=json.loads((R/'manifest.json').read_text()); ids=[x['id'] for x in m['tasks']]; assert len(ids)==len(set(ids))==9
assert len([x for x in m['tasks'] if x['repo']=='petclinic' and not x.get('freshness')])>=3
assert len([x for x in m['tasks'] if x['repo']=='jhipster' and not x.get('freshness')])>=4
assert len([x for x in m['tasks'] if x.get('freshness')])==2
assert json.loads((R/'artifacts/pollution-test.json').read_text())['pass']
if (R/'REPORT.json').exists():
 r=json.loads((R/'REPORT.json').read_text()); assert r['ordinary_valid_pairs']>=6; assert r['freshness_valid_pairs']>=2
 with tempfile.TemporaryDirectory() as tmp:
  before=hashlib.sha256((R/'REPORT.json').read_bytes()).hexdigest()
  subprocess.run([sys.executable,str(R/'evaluate.py')],check=True,cwd=R,stdout=subprocess.DEVNULL)
  after=hashlib.sha256((R/'REPORT.json').read_bytes()).hexdigest()
  assert before==after, 'REPORT.json is stale relative to raw artifacts/evaluator'
print('java_real_v2 validation: PASS')
