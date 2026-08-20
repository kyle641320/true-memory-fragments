#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, subprocess, tempfile, shutil
from pathlib import Path
HERE=Path(__file__).resolve().parent
TASKS=json.loads((HERE/'tasks.json').read_text())

def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def frozen_text():
    paths=[HERE/'tasks.json', HERE/'make_fixtures.py', HERE/'runner.py', HERE/'score.py', HERE/'validate.py']
    if (HERE/'fixtures').exists(): paths += sorted(p for p in (HERE/'fixtures').rglob('*') if p.is_file())
    return ''.join(f'{sha(p)}  {p.relative_to(HERE)}\n' for p in paths if p.exists())
def validate():
    errors=[]; report=[]
    if set(TASKS['arms'])!={'SOURCE_ONLY','TMF_STALE','TMF_FRESH'}: errors.append('arms must be three-arm design')
    for t in TASKS['tasks']:
        base=HERE/'fixtures'/t['id']/'base'; mutated=HERE/'fixtures'/t['id']/'mutated'
        if not base.is_dir() or not mutated.is_dir(): errors.append(f'{t["id"]}: missing fixtures'); continue
        for a in t['anchors']:
            if not (base/a).is_file(): errors.append(f'{t["id"]}: missing anchor {a}')
        changed=[]
        for m in t['mutations']:
            b=(base/m['file']).read_text(); mt=(mutated/m['file']).read_text()
            if b.count(m['find'])!=1: errors.append(f'{t["id"]}: base anchor not unique {m["file"]}')
            if m['replace'] not in mt: errors.append(f'{t["id"]}: mutation not applied {m["file"]}')
            if sha(base/m['file'])==sha(mutated/m['file']): errors.append(f'{t["id"]}: mutated file sha unchanged {m["file"]}')
            changed.append(m['file'])
        if not set(changed) & set(t['anchors']): errors.append(f'{t["id"]}: mutation does not touch claim anchors')
        report.append({'task_id':t['id'],'anchors':t['anchors'],'mutated_files':changed,'chain_len':len(t['entry_chain'])})
    return {'schema':'design-intent-v1-preflight','pass':not errors,'errors':errors,'tasks':report}
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--write-freeze',action='store_true'); ap.add_argument('--verify-freeze',action='store_true'); args=ap.parse_args()
    out=validate(); (HERE/'preflight.json').write_text(json.dumps(out,indent=2)+'\n')
    if args.write_freeze:
        if not out['pass']: raise SystemExit('preflight failed; not freezing')
        (HERE/'FROZEN.sha256').write_text(frozen_text())
    if args.verify_freeze:
        if (HERE/'FROZEN.sha256').read_text()!=frozen_text(): raise SystemExit('freeze mismatch')
    print(json.dumps(out,indent=2)); raise SystemExit(0 if out['pass'] else 1)
if __name__=='__main__': main()
