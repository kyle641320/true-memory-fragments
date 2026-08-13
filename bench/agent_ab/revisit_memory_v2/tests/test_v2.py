import importlib.util,json,sys,unittest
from pathlib import Path
H=Path(__file__).resolve().parents[1];sys.path.insert(0,str(H));from scorer import score
G=[json.loads(x) for x in (H/'goldens/goldens.jsonl').read_text().splitlines()];g=G[0]
class ScorerTests(unittest.TestCase):
 def good(self):return {'evidence_source':'SOURCE','memory_hit':'NOT_APPLICABLE','value':9,'citations':[{'path':'com/acme/ShippingRule.java','line':4}]}
 def test_positive(self):self.assertTrue(score(self.good(),g,'CONTROL')['correct'])
 def test_semantic_wording_ignored(self):
  a=self.good();a['explanation']='anything semantically equivalent';self.assertTrue(score(a,g,'CONTROL')['correct'])
 def test_missing_field(self):
  a=self.good();del a['value'];self.assertFalse(score(a,g,'CONTROL')['correct'])
 def test_wrong_number(self):
  a=self.good();a['value']=10;self.assertFalse(score(a,g,'CONTROL')['correct'])
 def test_wrong_citation(self):
  a=self.good();a['citations'][0]['line']=3;self.assertFalse(score(a,g,'CONTROL')['correct'])
 def test_bool_not_int(self):
  a=self.good();a['value']=True;self.assertFalse(score(a,g,'CONTROL')['correct'])
class ProtocolTests(unittest.TestCase):
 def test_independent(self):
  m=json.loads((H/'manifest.json').read_text());self.assertEqual(3,len({x['identity'] for x in m['sequences']}));self.assertEqual(3,len({x['base_value'] for x in m['sequences']}))
 def test_budget_fixtures(self):
  for p in (H/'fixture').rglob('*.java'):
   s=p.read_text();self.assertLessEqual(len(s.splitlines()),24);self.assertLessEqual(len(s.encode()),1600)
 def test_no_v1_fixture_names(self):
  text=(H/'manifest.json').read_text();self.assertNotIn('PricePolicy',text);self.assertNotIn('Inventory',text)
 def test_memory_allowlist_and_no_answer(self):
  r=(H/'runner.py').read_text();self.assertIn("'claim':{'value':s['base_value']}",r);self.assertNotIn("'answer':",r.split('def claim')[1].split('def evidence')[0])
if __name__=='__main__':unittest.main()
