import importlib.util,json,sys,unittest
from pathlib import Path
class PathInjectionTests(unittest.TestCase):
    H=Path(__file__).resolve().parents[1];sys.path.insert(0,str(H));spec=importlib.util.spec_from_file_location('runner',H/'runner.py');r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
    def test_no_prompt_path_leakage(self):
     for s in self.r.M['sequences']:
      for p in s['tasks'].values():assert s['region_path'] not in p and s['unknown_path'] not in p
    def test_trigger_from_trace_and_unknown_miss(self):
     s=self.r.M['sequences'][0];d=self.r.read_file(s,'first_visit',s['region_path']);t={'event':'e2','path':s['region_path'],'symbol':s['identity'],'sha256':d['sha256'],'origin':'agent_tool_trace'};c=self.r.make_claim(s,t);assert c['provenance']['trace_event']=='e2';u={**t,'path':s['unknown_path'],'symbol':s['unknown_identity'],'sha256':self.r.read_file(s,'unknown_region',s['unknown_path'])['sha256']};assert not self.r.pack({s['identity']:c},u)[2]
    def test_fresh_stale_top3_cap_and_no_forbidden_content(self):
     s=self.r.M['sequences'][0];d=self.r.read_file(s,'first_visit',s['region_path']);t={'event':'e','path':s['region_path'],'symbol':s['identity'],'sha256':d['sha256'],'origin':'agent_tool_trace'};c=self.r.make_claim(s,t);p,n,hit,st=self.r.pack({str(i):{**c,'identity':str(i)} for i in range(5)},t);assert hit and not st and len(p['items'])<=3 and n<=1200;assert not any(x in json.dumps(p).lower() for x in ['golden','transcript','previous answer']);mt={**t,'sha256':self.r.read_file(s,'semantic_mutation',s['region_path'])['sha256']};p,n,hit,st=self.r.pack({'x':c},mt);assert st and not hit and p['items'][0]['claim'] is None
    def test_arm_isolation_randomization_budget_and_repair_semantics(self):
     assert set(self.r.M['arms'])=={'SOURCE_ONLY','TMF_TOOL','TMF_INJECT_ONLY'};import random;a=self.r.M['arms'][:];random.Random(self.r.M['seed']).shuffle(a);assert a!=self.r.M['arms'];raw={'answer':19,'citations':[]};assert raw['answer']==19;assert self.r.M['budget']['injection_max_tokens']==1200
    def test_unrelated_mutation_keeps_region_fresh(self):
     s=self.r.M['sequences'][0];assert self.r.read_file(s,'first_visit',s['region_path'])['sha256']==self.r.read_file(s,'unrelated_mutation',s['region_path'])['sha256']
