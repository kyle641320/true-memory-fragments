import importlib.util,json,tempfile,unittest
from pathlib import Path
P=Path(__file__).parents[1]/'bench/agent_ab/retrieval_e2e_v1/runner.py'; s=importlib.util.spec_from_file_location('r',P);m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
class RetrievalE2E(unittest.TestCase):
 def test_frozen(self): self.assertEqual(m.M['status'],'FROZEN_BEFORE_EXECUTION');self.assertTrue(m.M['retrieval']['raw_natural_language_only'])
 def test_only_arm_difference(self):
  a=m.tool_desc('SOURCE_ONLY');b=m.tool_desc('TMF_AVAILABLE');self.assertEqual({*a},{'source_search','source_read'});self.assertEqual({k:b[k] for k in a},a);self.assertIn('tmf_retrieve',b)
 def test_paths_deduplicate_and_actionable_shape(self):
  x={'claims':[{'anchors':[{'path':'A.java','line_start':2}]},{'anchors':[{'path':'A.java','line_start':2},{'path':'B.java','line_start':3}]}]};self.assertEqual(m.paths(x),['A.java','B.java'])
 def test_source_read_traversal_fails_closed(self):
  with self.assertRaises(ValueError):m.execute(None,'source_read',{'path':'../x.java'},{'source_lines':0})
 def test_prompt_has_no_hints(self): self.assertNotIn('VisitScheduler',m.prompt(m.M['tasks'][0],'TMF_AVAILABLE',[],'neutral'))
if __name__=='__main__':unittest.main()
