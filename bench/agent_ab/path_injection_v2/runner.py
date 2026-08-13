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
def symbol_for(s,p):return s['identity'] if p==s['region_path'] else s['unknown_identity'] if p==s['unknown_path'] else None
def search(s,ph,q):
 words={w.lower() for w in ''.join(c if c.isalnum() else ' ' for c in q).split() if len(w)>2};out=[]
 for rel,p in files(s,ph).items():
  text=p.read_text();n=sum(w in (rel+' '+text).lower() for w in words)
  if n:out.append({'path':rel,'score':n})
 return sorted(out,key=lambda x:(-x['score'],x['path']))[:5]
def read_file(s,ph,path):
 p=files(s,ph).get(path)
 if not p:return None
 x=p.read_text();return {'path':path,'content':x,'lines':len(x.splitlines()),'bytes':len(x.encode()),'sha256':sha(p)}
def claim(s,nav):return {'identity':nav['symbol'],'path':nav['path'],'line':4,'claim':f"{s['symbol']} returns integer {s['base_value']} for input {s['input']}",'freshness':'fresh','anchor':{'path':nav['path'],'line':4},'provenance':{'kind':'first_visit_source_read','file_sha256':nav['source_sha256'],'memory_id':nav['memory_id']},'source_authoritative':True,'non_instruction':True}
def pack(s,store,nav,ph):
 # Only prior navigation chooses path. Freshness oracle checks that selected path's indexed fingerprint; no prompt/golden lookup.
 cs=[c for c in store.values() if c['path']==nav['path']][:M['budget']['injection_top_k']];p=files(s,ph).get(nav['path']);current=sha(p) if p else None
 fresh=[c for c in cs if c['provenance']['file_sha256']==current];stale=[c for c in cs if c not in fresh]
 if fresh:payload={'kind':'TMF_MEMORY_PREAMBLE','trigger':{'provenance':'prior_tool_trace','path':nav['path'],'memory_id':nav['memory_id']},'items':fresh}
 elif stale:payload={'kind':'TMF_MEMORY_POINTER','trigger':{'provenance':'prior_tool_trace','path':nav['path'],'memory_id':nav['memory_id']},'items':[{'path':c['path'],'freshness':'stale','claim':None,'pointer':'Source changed; reread localized path.','source_authoritative':True} for c in stale]}
 else:payload={'kind':'TMF_MEMORY_MISS','trigger':{'provenance':'prior_tool_trace','path':nav['path'],'memory_id':nav['memory_id']},'items':[]}
 text=json.dumps(payload,sort_keys=True);tokens=(len(text)+3)//4
 while tokens>M['budget']['injection_max_tokens'] and payload['items']:payload['items'].pop();text=json.dumps(payload,sort_keys=True);tokens=(len(text)+3)//4
 return payload,tokens,bool(fresh),bool(stale)
def prompt(task,tools,h,pre=''):return f'You are a controlled code agent. Task: {task}\nAvailable actions: {tools}. Return ONLY one JSON action. search={{"action":"search","query":"..."}}; read={{"action":"read","path":"search result path"}}; tmf_lookup={{"action":"tmf_lookup","identity_or_path":"identity learned from source touch"}}; finish={{"action":"finish","answer":integer_or_boolean,"citations":[{{"path":"...","line":1}}]}}. Search before read unless fresh pre-read memory answers it. Source authoritative.\nPRE-READ EVENT:{pre}\nTrace:{json.dumps(h)}'
def call(ad,p):t=time.perf_counter();z=ad.answer(p,budget=1);return z,time.perf_counter()-t
def parse(x):
 try:return json.loads(x)
 except:return {}
def run_session(ad,s,arm,ph,store,prior_nav):
 tools=['search','read','finish']+(['tmf_lookup'] if arm=='TMF_TOOL' else []);hist=[];tr=[];src=[];usage=[];lat=0;touch=None;tmfc=0;tmfa=False;answer=None;repair=False
 payload=None;itok=0;hit=False;stale=False
 if arm=='TMF_INJECT_ONLY' and ph!='first_visit' and prior_nav:payload,itok,hit,stale=pack(s,store,prior_nav,ph)
 for step in range(M['budget']['max_agent_calls']):
  z,dt=call(ad,prompt(s['tasks'][ph],tools,hist,json.dumps(payload,sort_keys=True) if payload else ''));lat+=dt;usage.append(z);a=parse(z['answer']);tr.append({'step':step,'available_tools':tools,'model_action':a,'injection':payload if step==0 else None,'call_kind':'agent'});k=a.get('action')
  if k=='search':hist.append({'action':'search','results':search(s,ph,str(a.get('query','')))})
  elif k=='read' and a.get('path') in files(s,ph):
   d=read_file(s,ph,a['path']);src.append(d);hist.append({'action':'read','data':d})
   if touch is None:touch={'repo_id':s['id'],'path':a['path'],'last_read_path':a['path'],'last_edited_path':None,'symbol':symbol_for(s,a['path']),'region':'line:4','timestamp':int(time.time()),'event_id':f'e{len(tr)}','memory_id':str(uuid.uuid4()),'source_sha256':d['sha256'],'origin':'prior_tool_trace'}
  elif k=='tmf_lookup' and arm=='TMF_TOOL':
   tmfc+=1;q=str(a.get('identity_or_path',''));cs=[c for c in store.values() if q in (c['identity'],c['path'])];current=touch and touch['source_sha256'];fresh=[c for c in cs if c['provenance']['file_sha256']==current];hist.append({'action':'tmf_lookup','result':fresh[:3] if fresh else ([{'freshness':'stale','pointer':'reread localized source'}] if cs else [])});tmfa=bool(fresh)
  elif k=='finish':answer={'answer':a.get('answer'),'citations':a.get('citations')};break
  else:hist.append({'error':'invalid_or_unavailable_action'})
 errs=structural_errors(answer,'exists' if ph=='unknown_region' else 'value')
 if errs:
  z,dt=call(ad,'FORMAT REPAIR ONLY. Same capabilities: '+json.dumps(tools)+'. Preserve semantics; no new source. Return valid answer JSON. Raw:'+json.dumps(answer)+' Trace:'+json.dumps(hist));lat+=dt;usage.append(z);answer=parse(z['answer']);repair=True;tr.append({'format_repair':True,'model_action':answer,'available_tools':tools,'call_kind':'repair','injection':None})
 sc=score(answer,G[(s['id'],ph)]);pt=sum(int((x.get('usage')or{}).get('prompt_tokens',0)) for x in usage)+itok;ct=sum(int((x.get('usage')or{}).get('completion_tokens',0)) for x in usage)
 if ph=='first_visit' and touch and touch['symbol']==s['identity']:store[s['identity']]=claim(s,touch)
 paths={x['path'] for x in src};before=bool(payload) and (not src or tr[0].get('injection') is not None)
 return {'phase':ph,'answer':answer,**sc,'transcript':tr,'navigation_state_written':touch if ph=='first_visit' else None,'trigger_provenance':payload and payload['trigger'],'injection_before_first_read':before,'injection_fired':bool(payload),'injection_hit':hit,'injection_stale_pointer':stale,'injection_adoption':hit and not src,'injection_noise':hit and ph=='unknown_region','injection_tokens':itok,'tmf_calls':tmfc,'tmf_adoption':tmfa,'source_lines':sum(x['lines'] for x in src),'source_bytes':sum(x['bytes'] for x in src),'source_files':len(paths),'read_calls':len(src),'prompt_tokens':pt,'completion_tokens':ct,'total_tokens':pt+ct,'latency_seconds':lat,'format_repair_used':repair,'stale_trust_error':ph=='semantic_mutation' and ((stale and not src) or tmfa)},touch
def run(mode,tag):
 ad=JsonBrokerAdapter(['/usr/bin/unshare','--net','--','/opt/tmf-model-broker/client'],expected_model=M['model']['id'],timeout_seconds=120);pre=ad.preflight();rows=[];rng=random.Random(M['seed'])
 for s in M['sequences'][:1 if mode=='smoke' else 3]:
  arms=M['arms'][:];rng.shuffle(arms)
  for arm in arms:
   store={};sessions=[];prior=None
   for ph in M['phases']:
    x,t=run_session(ad,s,arm,ph,store,prior);sessions.append(x)
    if ph=='first_visit':prior=t
   rows.append({'sequence':s['id'],'arm':arm,'arm_order':arms,'memory_store':store,'prior_navigation_state':prior,'sessions':sessions})
 out={'schema':'path-injection-v2-run','mode':mode,'preflight':pre.__dict__,'rows':rows};p=H/'results'/f'{tag}.json';p.write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(p)
if __name__=='__main__':
 a=argparse.ArgumentParser();a.add_argument('--mode',choices=['smoke','pilot'],required=True);a.add_argument('--tag',required=True);x=a.parse_args();run(x.mode,x.tag)
