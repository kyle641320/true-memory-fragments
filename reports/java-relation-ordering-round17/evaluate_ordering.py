#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, re, subprocess, sys
from collections import Counter
from contextlib import ExitStack
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
V2=ROOT/'bench/agent_ab/java_real_v2'
sys.path.insert(0,str(ROOT))
from tmf.mcp_server import McpService
from tmf.retrieve import retrieve_text
from bench.agent_ab.java_real_v2.store_lock import disposable_repository, verify_lock

BUDGETS=(3000,10000)
FROZEN=('manifest.json','goldens/goldens.jsonl','REPORT.json')
TOKEN_RE=re.compile(r'[A-Za-z_][A-Za-z0-9_]{2,}')

def toks(s):
    out=[]
    for raw in TOKEN_RE.findall(str(s)):
        # Keep both source identifier and camel-case pieces; deterministic lexical only.
        low=raw.lower(); out.append(low)
        out.extend(x.lower() for x in re.findall(r'[A-Z]?[a-z]+|[A-Z]+(?![a-z])|[0-9]+',raw) if len(x)>=3)
    return set(out)

def relation_text(svc,r,mode):
    pieces=[r.get('kind','')]
    for field,hint in sorted(r.get('endpoint_hints',{}).items()):
        pieces += [field,hint.get('qualname',''),hint.get('path',''),hint.get('anchor','')]
    if mode=='trusted_text':
        edge=svc.store.get_claim(r.get('edge_id'))
        if edge: pieces += [edge.claim, json.dumps(edge.body,sort_keys=True)]
        for cid in r.get('endpoints',{}).values():
            claim=svc.store.get_claim(cid) if isinstance(cid,str) else None
            if claim: pieces += [claim.claim,claim.body.get('qualname',''),claim.bindings[0].path if claim.bindings else '',json.dumps(claim.body.get('anchors',[]),sort_keys=True)]
    return ' '.join(map(str,pieces))

def order(name,svc,q,rels):
    if name=='baseline': return list(rels)
    qt=toks(q)
    mode='trusted_text' if name.endswith('trusted_text') else 'hints'
    scored=[]
    for i,r in enumerate(rels):
        rt=toks(relation_text(svc,r,mode)); overlap=len(qt & rt)
        scored.append((overlap,i,r))
    if name.startswith('overlap'):
        return [r for _,_,r in sorted(scored,key=lambda x:(-x[0],x[1]))]
    if name.startswith('partition2'):
        return [r for _,_,r in sorted(scored,key=lambda x:(0 if x[0]>=2 else 1,x[1]))]
    if name.startswith('partition3'):
        return [r for _,_,r in sorted(scored,key=lambda x:(0 if x[0]>=3 else 1,x[1]))]
    raise ValueError(name)

def compact(r):
    return {k:r[k] for k in ('for','kind','edge_id','endpoints','endpoint_hints','coverage','unresolved') if k in r}

def pack(base,relations,budget):
    size=lambda o:len(json.dumps(o,ensure_ascii=False,sort_keys=True))
    p=dict(base); p['truncated']=True; claims=list(p.get('claims',[])); p['relations']=[]; p['claims']=[]
    for r in relations:
        trial=dict(p); trial['relations']=[*p['relations'],compact(r)]
        if size(trial)<=budget:p=trial
        else:break
    packed=[]; trial=dict(p); trial['claims']=packed
    for c in claims:
        full=dict(trial); full['claims']=[*packed,c]
        if size(full)<=budget:packed.append(c); trial=full; continue
        stub={'stub':True,'claim_id':c.get('id'),'scope':c.get('scope'),'qualname':c.get('qualname'),'anchor':(c.get('anchors') or [None])[0],'expand':'tmf_explain'}
        st=dict(trial); st['claims']=[*packed,stub]
        if size(st)<=budget:packed.append(stub); trial=st
        else:break
    return trial

def main():
    manifest=json.loads((V2/'manifest.json').read_text()); gold={x['id']:x for x in map(json.loads,(V2/'goldens/goldens.jsonl').read_text().splitlines())}
    store_lock=json.loads((V2/'store-lock.json').read_text())
    frozen={f:hashlib.sha256((V2/f).read_bytes()).hexdigest() for f in FROZEN}
    repos={r['id']:r for r in manifest['repositories']}; services={}
    with ExitStack() as stack:
      for rid,r in repos.items():
          actual=subprocess.check_output(['git','-C',r['path'],'rev-parse','HEAD'],text=True).strip()
          if actual!=r['commit']:raise SystemExit(f'{rid} commit drift {actual}')
          try: verify_lock(rid,actual,Path(r['path'])/'.tmf',store_lock)
          except ValueError as exc: raise SystemExit(str(exc)) from exc
          copy=stack.enter_context(disposable_repository(Path(r['path'])))
          services[rid]=McpService(copy)
      # Stabilize read-through freshness only in disposable copies so evaluation is
      # repeatable and never rewrites the pinned source repositories or stores.
      for task in manifest['tasks']:
        svc=services[task['repo']]
        for budget in BUDGETS: svc._context_payload(task['prompt'],budget)
      names=('baseline','overlap_hints','partition2_hints','partition3_hints','overlap_trusted_text','partition2_trusted_text','partition3_trusted_text')
      results={n:{str(b):[] for b in BUDGETS} for n in names}
      for task in manifest['tasks']:
       svc=services[task['repo']]; required=gold[task['id']]['must_cite']
       for budget in BUDGETS:
        limit=8 if budget<=3000 else 16
        retrieval=retrieve_text(svc.repo.root,task['prompt'],limit=limit)
        claims=[__import__('tmf.explain',fromlist=['thin_view']).thin_view(__import__('tmf.explain',fromlist=['explain_claim']).explain_claim(svc.repo,x.claim)) for x in retrieval.claims]
        relation_budget=3 if budget<=3000 else 8
        # Candidate pool contains only relations already admitted by production trust/freshness logic.
        pool=svc._bounded_relations([x.claim for x in retrieval.claims],edge_budget=100000)
        base=svc._context_payload(task['prompt'],budget)
        for name in names:
          rels=order(name,svc,task['prompt'],pool)[:relation_budget]
          payload=svc.tmf_context(task['prompt'],budget) if name=='baseline' else pack(base,rels,budget)
          paths={h.get('path') for r in payload['relations'] for h in r.get('endpoint_hints',{}).values()}
          hit=[p for p in required if any(str(x).endswith(p) for x in paths if x)]
          actionable=all(all(h.get(k) for k in ('qualname','path','anchor')) for r in payload['relations'] for h in r.get('endpoint_hints',{}).values())
          results[name][str(budget)].append({'id':task['id'],'chars':len(json.dumps(payload,ensure_ascii=False,sort_keys=True)),'pool_relations':len(pool),'packed_relations':len(payload['relations']),'claims':len(payload['claims']),'full_claims':sum(not c.get('stub',False) for c in payload['claims']),'stub_claims':sum(c.get('stub',False) for c in payload['claims']),'required_hits':len(hit),'required_total':len(required),'hit_paths':hit,'actionable':actionable,'edge_ids':[r['edge_id'] for r in payload['relations']]})
    summary={}
    for name,byb in results.items():
      summary[name]={}
      for b,rows in byb.items():
        summary[name][b]={'chars':sum(r['chars'] for r in rows),'relations':sum(r['packed_relations'] for r in rows),'claims':sum(r['claims'] for r in rows),'full_claims':sum(r['full_claims'] for r in rows),'stub_claims':sum(r['stub_claims'] for r in rows),'required_hits':sum(r['required_hits'] for r in rows),'required_total':sum(r['required_total'] for r in rows),'actionable':all(r['actionable'] for r in rows)}
    out={'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'frozen_hashes':frozen,'strategies':list(names),'summary':summary,'per_query':results}
    print(json.dumps(out,indent=2,sort_keys=True))
if __name__=='__main__':main()
