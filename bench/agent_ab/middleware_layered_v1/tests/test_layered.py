import importlib.util,json,tempfile,unittest
from pathlib import Path
H=Path(__file__).resolve().parents[1]
def load(name):
 s=importlib.util.spec_from_file_location(name,H/f'{name}.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
runner=load('runner');audit=load('audit')
class LayeredTests(unittest.TestCase):
 def test_machine_attribution(self):
  self.assertEqual(runner.attribution('TMF_INJECT_ONLY',True,False,True,True,False,False,'fresh_revisit'),'memory-caused')
  self.assertEqual(runner.attribution('TMF_INJECT_ONLY',True,False,False,False,False,True,'semantic_mutation'),'post-reread model failure')
  self.assertEqual(runner.attribution('SOURCE_ONLY',True,False,False,False,False,False,'fresh_revisit'),'baseline model failure')
  self.assertEqual(runner.attribution('TMF_INJECT_ONLY',False,False,False,False,False,False,'fresh_revisit'),'output-contract failure')
 def test_middleware_stale_fresh_miss_budget_no_leak(self):
  s=runner.M['sequences'][0];base=runner.files(s,'first_visit')[s['region_path']];nav={'path':s['region_path'],'source_sha256':runner.sha(base),'session_id':'prior','event_id':'e'};store={s['identity']:runner.make_claim(s,nav)}
  p,t,_=runner.middleware(s,store,nav,'fresh_revisit');self.assertEqual(p['kind'],'FRESH');self.assertLessEqual(len(p['items']),3);self.assertLessEqual(t,500)
  p,_,_=runner.middleware(s,store,nav,'semantic_mutation');self.assertEqual(p['kind'],'STALE');self.assertIsNone(p['items'][0]['claim'])
  nav2={**nav,'path':s['unknown_path']};p,_,_=runner.middleware(s,store,nav2,'unknown_region');self.assertEqual(p['kind'],'MISS')
 def test_independent_sessions_and_order_are_audited(self):
  self.assertIn('independent_session_errors',Path(H/'audit.py').read_text());self.assertIn('pre_read_order_errors',Path(H/'audit.py').read_text())
 def test_no_forbidden_inputs_to_middleware(self):
  import inspect
  sig=str(inspect.signature(runner.middleware));self.assertEqual(sig,'(s, store, prior, ph)')
  body=inspect.getsource(runner.middleware);self.assertNotIn('golden',body);self.assertNotIn('transcript',body);self.assertNotIn('answer',body);self.assertNotIn('prompt',body)
if __name__=='__main__':unittest.main()
