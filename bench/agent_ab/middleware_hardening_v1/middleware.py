from __future__ import annotations
from dataclasses import dataclass,field
from hashlib import sha256
import json,posixpath

ALLOWED={'claim_id','path','line','region','freshness','provenance','non_instruction','pointer'}
def digest(data:bytes)->str:return sha256(data).hexdigest()
def canon(path:str)->str:
 p=posixpath.normpath(path.replace('\\','/')).lstrip('/')
 if p=='..' or p.startswith('../'):raise ValueError('path_escape')
 return p
@dataclass(frozen=True)
class Target:
 repo:str;branch:str;path:str;session:str;agent:str;symbol:str|None=None;region:tuple[int,int]|None=None;round_id:str='0'
@dataclass
class Claim:
 claim_id:str;repo:str;branch:str;path:str;session:str;agent:str;symbol:str|None;region:tuple[int,int]|None;source_hash:str;line:int;fact:str='withheld-from-wire'
@dataclass
class GateState:
 blocked:bool=False;required_path:str|None=None;required_region:tuple[int,int]|None=None;reason:str='';read_evidence:list=field(default_factory=list)

def relevance(target:Target,prior:Target|None,claim:Claim)->tuple[bool,str]:
 try:p=canon(target.path)
 except ValueError:return False,'invalid_path'
 checks=[('no_prior',prior is None),('repo_mismatch',claim.repo!=target.repo or (prior and prior.repo!=target.repo)),('path_mismatch',canon(claim.path)!=p or (prior and canon(prior.path)!=p)),('session_mismatch',claim.session!=target.session or (prior and prior.session!=target.session)),('agent_mismatch',claim.agent!=target.agent or (prior and prior.agent!=target.agent)),('branch_mismatch',claim.branch!=target.branch or (prior and prior.branch!=target.branch)),('symbol_mismatch',bool(claim.symbol or target.symbol) and claim.symbol!=target.symbol),('region_mismatch',bool(claim.region or target.region) and claim.region!=target.region)]
 for reason,bad in checks:
  if bad:return False,reason
 return True,'exact_target_identity'

def before_read(target:Target,prior:Target|None,claims:list[Claim],source_bytes:bytes|None,*,top_k=3,seen:set|None=None,store_ok=True)->tuple[dict,GateState]:
 state=GateState();base={'kind':'MISS','reason':'no_exact_claim','items':[],'provenance':{'hook':'before_read','target_origin':'tool_router'},'non_instruction':True}
 if not store_ok:return {**base,'reason':'store_unavailable_safe_degrade'},state
 matched=[];reasons=[]
 for c in claims:
  try:ok,r=relevance(target,prior,c)
  except Exception:ok,r=False,'corrupt_record'
  reasons.append(r)
  if ok:matched.append(c)
 if not matched:return {**base,'reason':reasons[0] if reasons else 'empty_store'},state
 current=digest(source_bytes) if source_bytes is not None else None
 for c in matched[:max(0,min(top_k,3))]:
  key=(target.round_id,c.claim_id,current)
  if seen is not None and key in seen:continue
  if seen is not None:seen.add(key)
  prov={'repo':c.repo,'branch':c.branch,'source_sha256':c.source_hash,'gate_reason':'exact_target_identity'}
  if current==c.source_hash:
   item={'claim_id':c.claim_id,'path':c.path,'line':c.line,'region':list(c.region) if c.region else None,'freshness':'fresh','provenance':prov,'non_instruction':True}
   base['items'].append(item)
  else:
   item={'claim_id':c.claim_id,'path':c.path,'line':c.line,'region':list(c.region) if c.region else None,'freshness':'stale','provenance':prov,'non_instruction':True,'pointer':'Read current source definition/affected region before final or edit.'}
   base['items'].append(item);state=GateState(True,c.path,c.region,'freshness_mismatch')
 base['kind']='STALE' if state.blocked else ('FRESH' if base['items'] else 'MISS');base['reason']='freshness_mismatch' if state.blocked else ('exact_target_identity' if base['items'] else 'same_round_dedupe')
 text=json.dumps(base,separators=(',',':'))
 while len(text)>4800 and base['items']:
  base['items'].pop();text=json.dumps(base,separators=(',',':'))
 if any(set(x)-ALLOWED for x in base['items']):raise AssertionError('wire allowlist')
 return base,state

def record_read(state:GateState,*,path:str,start:int,end:int,success:bool,source_hash:str|None)->bool:
 evidence={'path':path,'start':start,'end':end,'success':success,'source_sha256':source_hash};state.read_evidence.append(evidence)
 if not state.blocked:return True
 if not success or canon(path)!=canon(state.required_path or '') or not source_hash:return False
 if state.required_region and (start>state.required_region[0] or end<state.required_region[1]):return False
 state.blocked=False;state.reason='verified_current_source_region';return True
def allow_final_or_edit(state:GateState)->bool:return not state.blocked
