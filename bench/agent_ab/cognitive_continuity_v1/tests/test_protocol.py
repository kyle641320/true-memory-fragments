import hashlib,json,unittest
from pathlib import Path
H=Path(__file__).parents[1]
class ProtocolTest(unittest.TestCase):
 def test_manifest(self):
  m=json.loads((H/'manifest.json').read_text());self.assertGreaterEqual(len(m['full_order']),8);self.assertEqual(set(m['arms']),{'SOURCE_CONTINUITY','TMF_CONTINUITY'});self.assertEqual(len(m['smoke']),2)
  self.assertTrue(all(t['entry'] not in t['phase_b_prompt'] for t in m['tasks']))
 def test_frozen(self):
  for line in (H/'FROZEN.sha256').read_text().splitlines():
   h,p=line.split('  ');self.assertEqual(hashlib.sha256((H/p).read_bytes()).hexdigest(),h)
 def test_continuity_contract(self):
  s=(H/'runner.py').read_text();self.assertIn('logical_agent_id',s);self.assertIn('workflow_id',s);self.assertIn('repeat_bytes',s);self.assertIn('STALE memory notice',s)
