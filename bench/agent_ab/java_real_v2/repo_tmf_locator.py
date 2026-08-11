#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,subprocess,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent; TMF_ROOT=HERE.parents[2]; sys.path.insert(0,str(TMF_ROOT))
M=json.loads((HERE/'manifest.json').read_text()); ap=argparse.ArgumentParser(); ap.add_argument('repo',choices=['petclinic','jhipster']); ap.add_argument('question',nargs='?'); ap.add_argument('--max-chars',type=int,default=10000); ap.add_argument('--status',action='store_true'); ap.add_argument('--warm',action='store_true'); a=ap.parse_args()
r=next(x for x in M['repositories'] if x['id']==a.repo); p=Path(r['path']).resolve(); actual=subprocess.check_output(['git','-C',str(p),'rev-parse','HEAD'],text=True).strip()
if actual != r['commit']: raise SystemExit(f'commit drift: {actual}')
from tmf.mcp_server import McpService
s=McpService(p); result=s.tmf_status() if a.status else s.tmf_warm() if a.warm else s.tmf_context(a.question or '',a.max_chars)
print(json.dumps({'repo_id':a.repo,'repo':str(p),'commit':actual,'result':result},ensure_ascii=False,sort_keys=True))
