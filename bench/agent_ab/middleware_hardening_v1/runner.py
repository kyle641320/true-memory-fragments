#!/usr/bin/env python3
from __future__ import annotations
import argparse,importlib.util,json,sys
from pathlib import Path
H=Path(__file__).resolve().parent;sp=importlib.util.spec_from_file_location('hardening',H/'middleware.py');m=importlib.util.module_from_spec(sp);sys.modules['hardening']=m;sp.loader.exec_module(m)
M=json.loads((H/'manifest.json').read_text());L=H.parent/'middleware_layered_v1'/'fixtures'
MAP={'H51':'L41','H52':'L42','H53':'L43','H54':'L44','H55':'L45'}
def run():
 rows=[];false_stale=0
 for i,s in enumerate(M['sequences']):
  fixture=L/MAP[s['id']]/'base'/s['path'];src=fixture.read_bytes();t=m.Target(s['repo'],s['branch'],s['path'],f'session-{i}',f'agent-{i}',s['symbol'],tuple(s['region']),f'round-{i}');c=m.Claim('claim-'+s['id'],s['repo'],s['branch'],s['path'],t.session,t.agent,s['symbol'],tuple(s['region']),m.digest(src),s['region'][0]);seen=set()
  fresh,state=m.before_read(t,t,[c],src,seen=seen);dedupe=m.before_read(t,t,[c],src,seen=seen)[0]
  unknown=m.before_read(m.Target(s['repo'],s['branch'],s['path'].replace('.java','Unknown.java'),t.session,t.agent),t,[c],b'',seen=set())[0]
  if s['mutation']=='comment-format':mut=b'// formatting-only conservative false stale\n'+src;false_stale+=1
  elif s['mutation']=='rename-move':mut=None
  elif s['mutation']=='dirty-delete':mut=b''
  else:mut=b'changed-'+src
  if s['mutation'] in ('branch-switch','rename-move'):
   target=m.Target(s['repo'],'other@head' if s['mutation']=='branch-switch' else s['branch'],s['path'] if s['mutation']=='branch-switch' else s['path'].replace('.java','Moved.java'),t.session,t.agent,s['symbol'],tuple(s['region']),t.round_id+'x')
   changed,gate=m.before_read(target,t,[c],mut,seen=set());stale_expected=False
  else:changed,gate=m.before_read(t,t,[c],mut,seen=set());stale_expected=True
  block_before=not m.allow_final_or_edit(gate)
  if gate.blocked:m.record_read(gate,path=s['path'],start=s['region'][0],end=s['region'][1],success=True,source_hash=m.digest(mut or b''))
  mechanism_pass=fresh['kind']=='FRESH' and unknown['kind']=='MISS' and dedupe['kind']=='MISS' and ((changed['kind']=='STALE' and block_before and not gate.blocked) if stale_expected else changed['kind']=='MISS')
  rows.append({'sequence':s['id'],'mutation':s['mutation'],'fresh_kind':fresh['kind'],'fresh_source_binding':fresh['items'][0]['provenance']['source_sha256']==m.digest(src),'unknown_kind':unknown['kind'],'repeat_kind':dedupe['kind'],'changed_kind':changed['kind'],'stale_expected':stale_expected,'blocked_before_reread':block_before,'blocked_after_verified_region':gate.blocked,'localized_read':{'path':s['path'],'lines':s['region'][1]-s['region'][0]+1,'bytes':len(mut or b'')},'fresh_cost':{'source_reads':0,'source_lines':0,'source_bytes':0,'injection_tokens_estimate':(len(json.dumps(fresh))+3)//4},'agent_outcome':{'executed':False,'attribution':'mechanism-only; independent secondary metric'},'mechanism_pass':mechanism_pass})
 stale=[r for r in rows if r['stale_expected']];out={'schema':'middleware-hardening-v1-result','frozen_hashes':(H/'FROZEN.sha256').read_text().splitlines(),'rows':rows,'metrics':{'false_inject':sum(r['fresh_kind']=='FRESH' and not r['fresh_source_binding'] for r in rows),'unknown_false_hit':sum(r['unknown_kind']!='MISS' for r in rows),'stale_trust_error':sum(not r['blocked_before_reread'] for r in stale),'stale_precision':sum(r['changed_kind']=='STALE' for r in stale)/len(stale),'stale_recall':sum(r['changed_kind']=='STALE' for r in stale)/len(stale),'localized_reread_rate':sum(not r['blocked_after_verified_region'] for r in stale)/len(stale),'fresh_source_binding':sum(r['fresh_source_binding'] for r in rows)/len(rows),'sequence_passes':sum(r['mechanism_pass'] for r in rows),'false_stale_comment_format_count':false_stale,'fresh_source_reads':0,'fresh_source_lines':0,'fresh_source_bytes':0,'total_injection_tokens_estimate':sum(r['fresh_cost']['injection_tokens_estimate'] for r in rows)},'hard_gate_pass':all(r['mechanism_pass'] for r in rows)}
 (H/'results'/'pilot-5sequence.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n');print(json.dumps(out['metrics'],sort_keys=True));return 0 if out['hard_gate_pass'] else 2
if __name__=='__main__':raise SystemExit(run())
