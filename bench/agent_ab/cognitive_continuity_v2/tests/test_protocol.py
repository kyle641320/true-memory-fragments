import importlib.util,json,unittest
from pathlib import Path
H=Path(__file__).resolve().parents[1]
s=importlib.util.spec_from_file_location('v',H/'validate.py');v=importlib.util.module_from_spec(s);s.loader.exec_module(v)
class Protocol(unittest.TestCase):
 def test_preflight(self): self.assertTrue(v.validate()['pass'])
 def test_freeze(self): self.assertEqual((H/'FROZEN.sha256').read_text(),v.frozen())
 def test_no_v1_fact_reuse(self):
  text=(H/'tasks.json').read_text()+''.join(p.read_text() for p in (H/'fixtures').rglob('*') if p.is_file())
  for forbidden in ('billing.py','RetryPolicy','moon_phase','Codec.encode','tax rate'):self.assertNotIn(forbidden,text)
 def test_minimal_envelope_contract(self):
  protocol=(H/'PROTOCOL.md').read_text() if (H/'PROTOCOL.md').exists() else ''
  for x in ('logical_agent_id','workflow_id','no transcript','Store'):self.assertIn(x,protocol)
if __name__=='__main__':unittest.main()
