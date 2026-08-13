#!/usr/bin/env python3
from __future__ import annotations
import argparse,hashlib,json,random,sys,time,uuid
from pathlib import Path
H=Path(__file__).resolve().parent;ROOT=H.parents[2];sys.path[:0]=[str(ROOT),str(H)]
from bench.agent_ab.adapter import JsonBrokerAdapter
from scorer import score,structural_errors
M=json.loads((H/'manifest.json').read_text());G={(x['sequence'],x['phase']):x for x in map(json.loads,(H/'goldens/goldens.jsonl').read_text().splitlines())}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def version(ph):return 'semantic' if ph=='semantic_mutation' else 'unrelated' if ph=='unrelated_mutation' else 'base'
def files(s,ph):
 d=H/'fixtures'/s['id']/version(ph);return {p.relative_to(d).as_posix():p for p in d.rglob('*.java')}
def search(s,ph,q):
 words={w.lower() for w in ''.join(c if c.isalnum() else ' ' for c in q).split() if len(w)>2};out=[]
 for rel,p in files(s,ph).items():
  n=sum(w in (rel+' '+p.read_text()).lower() for w in words)
  if n:out.append({'path':rel,'score':n})
 return sorted(out,key=lambda x:(-x['score'],x['path']))[:5]
def read_source(s,ph,path):
 p=files(s,ph).get(path)
 if not p:return None
 x=p.read_text();return {'path':path,'content':x,'lines':len(x.splitlines()),'bytes':len(x.encode()),'sha256':sha(p)}
def make_claim(s,nav):
 return {'identity':s['identity'],'path':nav['path'],'line':4,'claim':f"{s['symbol']} returns integer {s['base_value']} for input {s['input']}",'value':s['base_value'],'freshness':'fresh','anchor':{'path':nav['path'],'line':4},'provenance':{'kind':'first_visit_source_tool_trace','file_sha256':nav['source_sha256'],'session_id':nav['session_id'],'event_id':nav['event_id']},'source_authoritative':True,'non_instruction':True}
def middleware(s,store,prior,ph):
 # Inputs intentionally restricted to prior navigation, claim store, current source fingerprint, and static budget.
 path=prior['path'];current=sha(files(s,ph)[path]) if path in files(s,ph) else None;cs=[c for c in store.values() if c['path']==path][:M['budget']['injection_top_k']]
 fresh=[c for c in cs if c['provenance']['file_sha256']==current];stale=[c for c in cs if c not in fresh]
 if fresh: kind='FRESH';items=fresh
 elif stale: kind='STALE';items=[{'path':c['path'],'freshness':'stale','claim':None,'pointer':'Source changed; read affected path before final.','source_authoritative':True} for c in stale]
 else:kind='MISS';items=[]
 payload={'kind':kind,'trigger':{'origin':'prior_source_tool_trace','path':path,'event_id':prior['event_id'],'prior_session_id':prior['session_id']},'items':items}
 text=json.dumps(payload,sort_keys=True);tok=(len(text)+3)//4
 while tok>M['budget']['injection_max_tokens'] and payload['items']:payload['items'].pop();text=json.dumps(payload,sort_keys=True);tok=(len(text)+3)//4
 return payload,tok,current

def prompt(task,tools,h,pre):return f'''Controlled code task: {task}\nActions {tools}. Return ONLY one JSON action: search={{"action":"search","query":"..."}} read={{"action":"read","path":"..."}} finish={{"action":"finish","answer":integer_or_boolean,"citations":[{{"path":"...","line":1}}]}}. Search before read unless a FRESH middleware item answers it. FRESH anchors may be cited. STALE requires reading its path before finish. Source authoritative.\nMIDDLEWARE_PRE_READ:{pre}\nTRACE:{json.dumps(h)}'''
def call(ad,p):t=time.perf_counter();z=ad.answer(p,budget=1);return z,time.perf_counter()-t
def parse(x):
 try:return json.loads(x)
 except:return {}
def attribution(arm,valid,correct,claim_wrong,used_fresh,stale_trusted,affected_read,ph):
 if not valid:return 'output-contract failure'
 if correct:return 'none'
 if (claim_wrong and used_fresh) or stale_trusted:return 'memory-caused'
 if ph=='semantic_mutation' and affected_read:return 'post-reread model failure'
 if arm=='SOURCE_ONLY':return 'baseline model failure'
 return 'downstream model failure'
def run_session(ad,s,arm,ph,store,prior):
 sid=str(uuid.uuid4());tools=['search','read','finish'];hist=[];trace=[];reads=[];usage=[];lat=0;touch=None;answer=None;repair=False;blocked=0
 payload=None;itok=0;current=None
 if arm=='TMF_INJECT_ONLY' and ph!='first_visit' and prior:payload,itok,current=middleware(s,store,prior,ph)
 stale=bool(payload and payload['kind']=='STALE');fresh=bool(payload and payload['kind']=='FRESH');miss=bool(payload and payload['kind']=='MISS');affected_read=False;used_fresh=False
 for step in range(M['budget']['max_agent_calls']):
  z,dt=call(ad,prompt(s['tasks'][ph],tools,hist,json.dumps(payload,sort_keys=True) if payload else 'NONE'));lat+=dt;usage.append(z);a=parse(z['answer']);k=a.get('action');event={'step':step,'session_id':sid,'available_tools':tools,'model_action':a,'middleware':payload if step==0 else None,'call_kind':'agent'};trace.append(event)
  if k=='search':hist.append({'action':'search','results':search(s,ph,str(a.get('query','')))})
  elif k=='read' and a.get('path') in files(s,ph):
   d=read_source(s,ph,a['path']);reads.append(d);hist.append({'action':'read','data':d});affected_read|=a['path']==s['region_path']
   if touch is None:touch={'repo_id':s['id'],'path':a['path'],'symbol':s['identity'] if a['path']==s['region_path'] else None,'session_id':sid,'event_id':str(uuid.uuid4()),'source_sha256':d['sha256'],'origin':'source_tool_trace'}
  elif k=='finish':
   if stale and not affected_read:
    blocked+=1;hist.append({'error':'MIDDLEWARE_READ_GATE','required_path':s['region_path'],'old_fact_withheld':True});continue
   answer={'answer':a.get('answer'),'citations':a.get('citations')};used_fresh=fresh and not affected_read;break
  else:hist.append({'error':'invalid_or_unavailable_action'})
 errs=structural_errors(answer,'exists' if ph=='unknown_region' else 'value')
 if errs:
  z,dt=call(ad,'FORMAT REPAIR ONLY; no new facts/source. Return exactly answer,citations JSON. Raw:'+json.dumps(answer));lat+=dt;usage.append(z);answer=parse(z['answer']);repair=True;trace.append({'session_id':sid,'format_repair':True,'model_action':answer,'available_tools':tools,'call_kind':'repair','middleware':None})
 sc=score(answer,G[(s['id'],ph)]);pt=sum(int((x.get('usage')or{}).get('prompt_tokens',0)) for x in usage);ct=sum(int((x.get('usage')or{}).get('completion_tokens',0)) for x in usage)
 if ph=='first_visit' and touch and touch['path']==s['region_path']:store[s['identity']]=make_claim(s,touch)
 claim_wrong=fresh and any(c.get('value')!=s['base_value'] for c in payload['items']);stale_trusted=stale and not affected_read and answer is not None
 attr=attribution(arm,sc['valid'],sc['correct'],claim_wrong,used_fresh,stale_trusted,affected_read,ph)
 return {'phase':ph,'session_id':sid,'answer':answer,**sc,'machine_attribution':attr,'human_audit':{'reviewer':None,'agrees':None,'notes':''},'transcript':trace,'navigation_state_written':touch if ph=='first_visit' else None,'middleware_kind':payload and payload['kind'],'injection_before_first_read':bool(payload),'injection_items':len(payload['items']) if payload else 0,'injection_tokens':itok,'fresh_claim_hash_matches':fresh and all(c['provenance']['file_sha256']==current for c in payload['items']),'old_fact_withheld':not stale or all(x.get('claim') is None for x in payload['items']),'read_gate_blocks':blocked,'affected_path_read':affected_read,'localized_reread':ph=='semantic_mutation' and affected_read and all(x['path']==s['region_path'] for x in reads),'used_fresh_without_read':used_fresh,'claim_wrong':claim_wrong,'stale_trust_error':stale_trusted,'source_lines':sum(x['lines'] for x in reads),'source_bytes':sum(x['bytes'] for x in reads),'read_calls':len(reads),'source_paths':sorted({x['path'] for x in reads}),'prompt_tokens':pt,'completion_tokens':ct,'total_tokens':pt+ct+itok,'latency_seconds':lat,'format_repair_used':repair},touch

def run(mode,tag):
 ad=JsonBrokerAdapter(['/usr/bin/unshare','--net','--','/opt/tmf-model-broker/client'],expected_model=M['model']['id'],timeout_seconds=120);pre=ad.preflight();rows=[];rng=random.Random(M['seed'])
 for s in M['sequences'][:1 if mode=='smoke' else 5]:
  arms=M['arms'][:];rng.shuffle(arms)
  for arm in arms:
   store={};sessions=[];prior=None
   for ph in M['phases']:
    x,t=run_session(ad,s,arm,ph,store,prior);sessions.append(x)
    if ph=='first_visit':prior=t
   rows.append({'sequence':s['id'],'arm':arm,'arm_order':arms,'independent_session_ids':[x['session_id'] for x in sessions],'memory_store':store,'prior_navigation_state':prior,'sessions':sessions})
 out={'schema':'middleware-layered-v1-run','mode':mode,'frozen_hash':(H/'FROZEN.sha256').read_text().strip(),'preflight':pre.__dict__,'rows':rows};p=H/'results'/f'{tag}.json';p.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(p)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--mode',choices=['smoke','pilot'],required=True);a.add_argument('--tag',required=True);x=a.parse_args();run(x.mode,x.tag)
