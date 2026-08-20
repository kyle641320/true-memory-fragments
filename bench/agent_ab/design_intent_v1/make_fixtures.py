#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, shutil, hashlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
TASKS=json.loads((HERE/'tasks.json').read_text())
SRC=Path(TASKS['eventbus_source']).resolve()
FIX=HERE/'fixtures'
class AnchorError(RuntimeError): pass
def copy_base(task_id):
    dest=FIX/task_id/'base'
    if dest.exists(): shutil.rmtree(dest)
    dest.parent.mkdir(parents=True,exist_ok=True)
    shutil.copytree(SRC,dest)
    return dest
def apply_mutations(base, task):
    dest=FIX/task['id']/'mutated'
    if dest.exists(): shutil.rmtree(dest)
    shutil.copytree(base,dest)
    records=[]
    for m in task['mutations']:
        p=dest/m['file']; text=p.read_text()
        n=text.count(m['find'])
        if n!=1: raise AnchorError(f"{task['id']} {m['file']} anchor count {n}")
        p.write_text(text.replace(m['find'],m['replace']))
        records.append({'file':m['file'],'find_sha256':hashlib.sha256(m['find'].encode()).hexdigest()})
    return dest, records
def digest_tree(root):
    out={}
    for p in sorted(root.glob('*.java')):
        out[p.name]=hashlib.sha256(p.read_bytes()).hexdigest()
    return out
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--check',action='store_true'); args=ap.parse_args()
    manifest=[]
    for task in TASKS['tasks']:
        if args.check:
            import tempfile
            with tempfile.TemporaryDirectory() as td:
                scratch=Path(td)/'base'; shutil.copytree(SRC,scratch)
                mut=Path(td)/'mut'; shutil.copytree(scratch,mut)
                for m in task['mutations']:
                    p=mut/m['file']; text=p.read_text(); n=text.count(m['find'])
                    if n!=1: raise AnchorError(f"{task['id']} {m['file']} anchor count {n}")
            print(f"CHECK {task['id']}")
            continue
        base=copy_base(task['id']); mut,recs=apply_mutations(base,task)
        manifest.append({'task_id':task['id'],'base':str(base.relative_to(HERE)),'mutated':str(mut.relative_to(HERE)),'mutations':recs,'base_sha256':digest_tree(base),'mutated_sha256':digest_tree(mut)})
        print(f"GENERATED {task['id']}")
    if not args.check:
        FIX.mkdir(exist_ok=True)
        (FIX/'MANIFEST.json').write_text(json.dumps({'schema':'design-intent-fixtures-v1','source':str(SRC),'real_guava_root':TASKS.get('real_guava_root'),'tasks':manifest},indent=2)+'\n')
        print('wrote fixtures/MANIFEST.json')
if __name__=='__main__': main()
