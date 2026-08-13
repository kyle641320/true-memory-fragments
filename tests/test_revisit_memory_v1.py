import importlib.util,subprocess,unittest
from pathlib import Path
H=Path('bench/agent_ab/revisit_memory_v1')
spec=importlib.util.spec_from_file_location('rm',H/'runner.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
class RevisitMemoryV1Test(unittest.TestCase):
 def test_mutation_and_fingerprint(self):
  self.assertNotEqual(m.tree('base')[m.M['region']['path']],m.tree('mutated')[m.M['region']['path']]);self.assertNotEqual(m.fingerprint('base'),m.fingerprint('mutated'))
 def test_identity_gated_memory_and_stale_block(self):
  s={m.M['region']['identity']:m.claim()};e,h,a,b,_=m.evidence('TMF_MEMORY','fresh_revisit',s);self.assertTrue(h and a and not b and e[0]['kind']=='memory')
  e,h,a,b,_=m.evidence('TMF_MEMORY','mutation_revisit',s);self.assertTrue(h and not a and b);self.assertEqual([x['kind'] for x in e],['stale_block','source'])
  e,h,a,b,_=m.evidence('TMF_MEMORY','unknown',s);self.assertTrue(not h and not a and e[0]['kind']=='source')
 def test_store_allowlist_and_no_answer_leak(self):
  c=m.claim();self.assertEqual(set(c),{'identity','claim','anchors','provenance','freshness'});self.assertFalse({'answer','transcript','prompt','golden'} & set(c))
 def test_frozen_hashes(self):self.assertEqual(subprocess.run(['sha256sum','-c',str(H/'FROZEN.sha256')],stdout=subprocess.DEVNULL).returncode,0)
if __name__=='__main__':unittest.main()
