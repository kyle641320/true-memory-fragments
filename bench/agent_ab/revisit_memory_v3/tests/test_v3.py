import json,sys,unittest
from pathlib import Path
H=Path(__file__).resolve().parents[1];sys.path.insert(0,str(H))
from scorer import score,structural_errors
from runner import repair_prompt,schema
G=[json.loads(x) for x in (H/'goldens/goldens.jsonl').read_text().splitlines()];g=G[0]
class V3Tests(unittest.TestCase):
 def good(self):return {'evidence_source':'SOURCE','memory_hit':'NOT_APPLICABLE','value':17,'citations':[{'path':'org/example/TaxBand.java','line':4}]}
 def test_positive(self):self.assertTrue(score(self.good(),g,'CONTROL')['correct'])
 def test_missing_citation_detected(self):a=self.good();a['citations']=[];self.assertIn('empty_citations',structural_errors(a,'value'))
 def test_repaired_missing_citation_scores(self):a=self.good();self.assertTrue(score(a,g,'CONTROL')['citation_ok'])
 def test_wrong_answer_not_hidden(self):a=self.good();a['value']=999;self.assertFalse(score(a,g,'CONTROL')['correct'])
 def test_bool_not_integer(self):a=self.good();a['value']=True;self.assertIn('bad_value_type',structural_errors(a,'value'))
 def test_integer_not_bool(self):self.assertIn('bad_exists_type',structural_errors({'evidence_source':'SOURCE','memory_hit':'MISS','exists':1,'citations':[{'path':'x','line':1}]},'exists'))
 def test_extra_rejected(self):a=self.good();a['explanation']='x';self.assertTrue(any(x.startswith('extra_fields') for x in structural_errors(a,'value')))
 def test_schema_requires_citation(self):self.assertEqual(1,schema('value')['properties']['citations']['minItems'])
 def test_repair_no_golden(self):p=repair_prompt('{}',schema('value'),['missing_value'],[]).lower();self.assertNotIn('golden',p);self.assertNotIn('17',p)
 def test_repair_semantic_guard(self):self.assertIn('Preserve every semantic answer',repair_prompt('{}',schema('value'),[],[]))
 def test_arm_symmetry(self):r=(H/'runner.py').read_text();self.assertEqual(1,r.count('if errs:'));self.assertNotIn("arm=='CONTROL' and errs",r)
 def test_distinct_heldout(self):m=json.loads((H/'manifest.json').read_text());self.assertEqual(3,len({s['identity'] for s in m['sequences']}));self.assertFalse(any(x in (H/'manifest.json').read_text() for x in ['ShippingRule','RetryRule','QuotaRule']))
 def test_memory_allowlist(self):r=(H/'runner.py').read_text();self.assertIn("'claim':{'value':s['base_value']}",r)
 def test_budget(self):
  for p in (H/'fixture').rglob('*.java'):self.assertLessEqual(len(p.read_text().splitlines()),24);self.assertLessEqual(len(p.read_bytes()),1600)
 def test_unknown_is_miss_contract(self):m=json.loads((H/'manifest.json').read_text());self.assertTrue(all(s['unknown_identity']!=s['identity'] for s in m['sequences']))
 def test_both_mutations(self):
  m=json.loads((H/'manifest.json').read_text());
  for s in m['sequences']:
   b=H/'fixture'/s['id']/'base';u=H/'fixture'/s['id']/'mutated';self.assertNotEqual((b/s['region_path']).read_text(),(u/s['region_path']).read_text());self.assertNotEqual((b/s['unrelated_mutation_path']).read_text(),(u/s['unrelated_mutation_path']).read_text())
if __name__=='__main__':unittest.main()
