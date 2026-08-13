#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,sys,time
from pathlib import Path
H=Path(__file__).resolve().parent; ROOT=H.parents[2]; sys.path.insert(0,str(ROOT)); sys.path.insert(0,str(H))
from bench.agent_ab.adapter import JsonBrokerAdapter
from scorer import score,structural_errors
M=json.loads((H/'manifest.json').read_text()); G={(x['sequence'],x['phase']):x for x in map(json.loads,(H/'goldens/goldens.jsonl').read_text().splitlines())}
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def read(s,ver,path):
 p=H/'fixture'/s['id']/ver/path;x=p.read_text();return {'path':path,'lines':len(x.splitlines()),'bytes':len(x.encode()),'content':x}
def tree(s,ver):
 d=H/'fixture'/s['id']/ver;return {p.relative_to(d).as_posix():sha(p) for p in sorted(d.rglob('*.java'))}
def fp(s,ver): return hashlib.sha256(json.dumps(tree(s,ver),sort_keys=True).encode()).hexdigest()
def claim(s): return {'identity':s['identity'],'claim':{'value':s['base_value']},'anchors':[{'path':s['region_path'],'lines':[4]}],'freshness':'fresh','provenance':{'file_sha256':tree(s,'base')[s['region_path']],'tree_fingerprint':fp(s,'base')}}
def evidence(s,arm,phase,store):
 ver='mutated' if phase=='mutation_revisit' else 'base';hit=adopt=blocked=False
 if arm=='TMF_MEMORY' and phase!='first_visit':
  ident=s['unknown_identity'] if phase=='unknown_region' else s['identity'];hit=ident in store
  if hit and store[ident]['provenance']['file_sha256']==tree(s,ver)[s['region_path']]: return [{'kind':'memory','claim':store[ident]}],hit,True,False
  path=s['unknown_path'] if phase=='unknown_region' else s['region_path'];blocked=hit
  return ([{'kind':'stale_block','identity':ident}] if blocked else [])+[{'kind':'source','data':read(s,ver,path)}],hit,False,blocked
 paths=[s['unknown_path']] if phase=='unknown_region' else [s['region_path'],s['service_path']]
 return [{'kind':'source','data':read(s,ver,p)} for p in paths],hit,adopt,blocked
def schema(field):
 typ='integer' if field=='value' else 'boolean'
 return {'type':'object','additionalProperties':False,'required':['evidence_source','memory_hit',field,'citations'],'properties':{'evidence_source':{'enum':['SOURCE','MEMORY','NONE']},'memory_hit':{'enum':['HIT','MISS','NOT_APPLICABLE']},field:{'type':typ},'citations':{'type':'array','minItems':1,'items':{'type':'object','additionalProperties':False,'required':['path','line'],'properties':{'path':{'type':'string'},'line':{'type':'integer','minimum':1}}}}}}
def prompt(s,arm,phase,ev,sch):
 expected_source='MEMORY' if arm=='TMF_MEMORY' and phase=='fresh_revisit' else 'SOURCE'
 expected_hit='HIT' if arm=='TMF_MEMORY' and phase in ('fresh_revisit','mutation_revisit') else 'MISS' if arm=='TMF_MEMORY' and phase=='unknown_region' else 'NOT_APPLICABLE'
 return f"Controlled stateless task: {s['tasks'][phase]}\nUse only evidence. Return ONLY JSON conforming exactly to this schema: {json.dumps(sch,sort_keys=True)}. Instrumentation: evidence_source={expected_source}; memory_hit={expected_hit}. Citation must cover the declaration/return establishing the answer. Evidence:\n{json.dumps(ev,sort_keys=True)}"
def parse(raw):
 try:return json.loads(raw)
 except Exception:return None
def repair_prompt(raw,sch,errors,ev):
 # Deliberately excludes task, golden and expected answer. Evidence is the same already-read evidence only for citation recovery.
 return 'FORMAT REPAIR ONLY. Preserve every semantic answer value and enum from the raw output; do not infer or change the answer and do not add unread source. Return only schema-valid JSON. If citation is empty, copy a path:line only from raw output or supplied already-read evidence. Raw output:\n'+raw+'\nJSON schema:\n'+json.dumps(sch,sort_keys=True)+'\nMissing/type errors:\n'+json.dumps(errors)+'\nAlready-read evidence (citation recovery only):\n'+json.dumps(ev,sort_keys=True)
def call(ad,p,budget=1):
 t=time.perf_counter();z=ad.answer(p,budget=budget);return z,time.perf_counter()-t
def run(mode,tag):
 ad=JsonBrokerAdapter(['/usr/bin/unshare','--net','--','/opt/tmf-model-broker/client'],expected_model=M['model']['id'],timeout_seconds=120);pre=ad.preflight();rows=[]
 for i,s in enumerate(M['sequences'][:1 if mode=='smoke' else 3]):
  for arm in (['CONTROL','TMF_MEMORY'] if i%2==0 else ['TMF_MEMORY','CONTROL']):
   store={};sessions=[]
   for phase in M['phases']:
    t0=time.perf_counter();ev,hit,adopt,blocked=evidence(s,arm,phase,store);lookup=(time.perf_counter()-t0)*1000;field='exists' if phase=='unknown_region' else 'value';sch=schema(field)
    z,lat=call(ad,prompt(s,arm,phase,ev,sch)); raw=z['answer']; a=parse(raw);errs=structural_errors(a,field); repaired=False;rz=None
    if errs:
     rz,rlat=call(ad,repair_prompt(raw,sch,errs,ev));lat+=rlat;a=parse(rz['answer']);repaired=True
    if arm=='TMF_MEMORY' and phase=='first_visit':store[s['identity']]=claim(s)
    sc=score(a,G[(s['id'],phase)],arm);src=[e['data'] for e in ev if e['kind']=='source'];usage=[z]+([rz] if rz else [])
    sessions.append({'phase':phase,'answer':a,'initial_structural_errors':errs,'format_repair_used':repaired,**sc,'memory_hit':hit,'memory_adoption':adopt,'stale_blocked':blocked,'source_lines':sum(x['lines'] for x in src),'source_bytes':sum(x['bytes'] for x in src),'source_files':len(src),'prompt_tokens':sum(int((q.get('usage')or{}).get('prompt_tokens',0)) for q in usage),'completion_tokens':sum(int((q.get('usage')or{}).get('completion_tokens',0)) for q in usage),'latency_seconds':lat,'tmf_lookup_ms':lookup,'stale_trust_error':phase=='mutation_revisit' and adopt})
   rows.append({'sequence':s['id'],'arm':arm,'memory_store':store if arm=='TMF_MEMORY' else None,'sessions':sessions})
 out={'schema':'revisit-memory-v3-run','mode':mode,'preflight':pre.__dict__,'rows':rows};p=H/'results'/f'{tag}.json';p.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(p)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--mode',choices=['smoke','pilot'],required=True);a.add_argument('--tag',required=True);x=a.parse_args();run(x.mode,x.tag)
