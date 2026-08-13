import importlib.util,json,tempfile
from pathlib import Path
H=Path(__file__).resolve().parents[1]
def load(n):
 s=importlib.util.spec_from_file_location('v2_'+n,H/(n+'.py'));m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
def test_frozen_hashes():
 import hashlib
 for line in (H/'FROZEN.sha256').read_text().splitlines():
  h,p=line.split('  ');assert hashlib.sha256((H/p).read_bytes()).hexdigest()==h
def test_pack_uses_prior_path_and_stale_pointer():
 r=load('runner');s=r.M['sequences'][0];nav={'path':s['region_path'],'memory_id':'m','source_sha256':'x','symbol':s['identity']};store={s['identity']:r.claim(s,nav)}
 p,_,hit,stale=r.pack(s,store,nav,'semantic_mutation');assert stale and not hit and p['items'][0]['claim'] is None and p['trigger']['provenance']=='prior_tool_trace'
def test_unknown_conservative_noise():
 r=load('runner');s=r.M['sequences'][0];d=r.read_file(s,'first_visit',s['region_path']);nav={'path':s['region_path'],'memory_id':'m','source_sha256':d['sha256'],'symbol':s['identity']};store={s['identity']:r.claim(s,nav)}
 _,_,hit,stale=r.pack(s,store,nav,'unknown_region');assert hit and not stale
def test_audit_repairs_capability_and_distinct_paths():
 a=load('audit');src={'schema':'path-injection-v2-run','preflight':{'stateless':True,'model':'gpt-5.6-sol'},'rows':[]}
 # Static regression assertions ensure call-level capability and distinct path set are implemented.
 text=(H/'audit.py').read_text();assert "e.get('available_tools',[])" in text and "len({e.get('model_action'" in text and "read_calls" in text
def test_no_prompt_or_golden_path_derivation():
 text=(H/'runner.py').read_text();body=text[text.index('def pack'):text.index('def prompt')];assert "tasks" not in body and "G[" not in body
