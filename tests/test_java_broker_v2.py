import importlib.util,json,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).parents[1]; P=ROOT/'bench/agent_ab/java_broker_v2/runner.py'
s=importlib.util.spec_from_file_location('v2runner',P); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
class V2(unittest.TestCase):
 def test_frozen_independent_protocol(self):
  self.assertTrue(m.M['v1_immutable']); self.assertEqual(m.M['status'],'FROZEN_BEFORE_EXECUTION'); self.assertEqual(m.M['model']['temperature'],0)
 def test_randomization_and_equal_declared_budgets(self):
  for t in m.M['tasks']: self.assertEqual(set(m.assignment(t['id'])),set(m.M['arms']))
  self.assertEqual(m.M['model']['broker_calls_per_arm'],2); self.assertEqual(m.M['budgets']['source_lines'],600)
 def test_selection_rejects_pollution_and_fills_deterministically(self):
  cat=[{'path':f'src/{x}.java','lines':100} for x in 'ABCDEFG']
  paths,valid=m.parse_selection(json.dumps({'paths':['/tmp/golden.json','src/B.java','src/B.java']}),cat)
  self.assertTrue(valid); self.assertNotIn('/tmp/golden.json',paths); self.assertEqual(paths[:2],['src/B.java','src/A.java']); self.assertEqual(len(paths),6)
 def test_prompt_only_arm_difference_is_tmf_capability(self):
  task={'id':'X','prompt':'Find Foo'}; cat=[{'path':'src/Foo.java','lines':2}]; t={'claims':['src/Foo.java']}
  a=m.selection_prompt(task,cat,'SOURCE_ONLY',t); b=m.selection_prompt(task,cat,'TMF_MAP',t)
  self.assertEqual(a.split('\nTMF NAVIGATION HINTS')[0],b.split('\nTMF NAVIGATION HINTS')[0]); self.assertNotIn('claims',a); self.assertIn('claims',b)
 def test_exact_source_budget(self):
  old_repo,old_budget=m.REPO,m.M['budgets']['source_lines']
  with tempfile.TemporaryDirectory() as d:
   r=Path(d); (r/'src').mkdir();
   for x in 'ABC': (r/f'src/{x}.java').write_text('\n'.join('x' for _ in range(5)))
   m.REPO=r; m.M['budgets']['source_lines']=12
   try: ev=m.evidence(['src/B.java'],[{'path':f'src/{x}.java','lines':5} for x in 'ABC'])
   finally: m.REPO=old_repo; m.M['budgets']['source_lines']=old_budget
  self.assertEqual(sum(x['lines'] for x in ev),12)
 def test_isolation_probe(self):
  try: x=m.probe()
  except (PermissionError, OSError, __import__('subprocess').CalledProcessError) as exc:
   self.skipTest(f'network namespace unavailable in this runner: {exc}')
  self.assertTrue(x['inet_blocked']); self.assertEqual(x['ambient_secrets'],[])
if __name__=='__main__': unittest.main()
