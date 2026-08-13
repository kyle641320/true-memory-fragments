import importlib.util,json,os,tempfile,unittest
from pathlib import Path
P=Path(__file__).parents[1]/'bench/agent_ab/java_real_v1/broker_pilot_runner.py'
s=importlib.util.spec_from_file_location('pilot',P); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
class T(unittest.TestCase):
 def test_versioned_manifest_preserves_frozen_model_and_hash(self):
  self.assertEqual(m.M['model']['id'],'aisz/gpt-5.6-sol'); self.assertEqual(m.P['model']['id'],'gpt-5.6-sol')
  self.assertEqual(m.sha(m.HERE/'manifest.json'),m.P['base_manifest_sha256'])
  self.assertIn('does_not_modify_frozen',m.P['status'])
 def test_assignment_is_deterministic_and_balanced(self):
  for tid in m.P['task_order']:
   self.assertEqual(set(m.assignment(tid)),set(m.P['arms']))
 def test_arm_network_and_ambient_secrets_are_denied(self):
  os.environ['AISZ_API_KEY']='must-not-leak'
  try: out=m.probe_isolation()
  finally: os.environ.pop('AISZ_API_KEY',None)
  self.assertTrue(out['inet_blocked']); self.assertEqual(out['ambient_secrets'],[])
 def test_broker_telemetry_and_no_cross_arm_state(self):
  class A:
   n=0
   def answer(self,prompt,budget):
    self.n+=1; return {'protocol':'tmf-agent-broker-v1','model':'gpt-5.6-sol','calls':1,'request_id':str(self.n),'usage':{'total_tokens':3},'answer':json.dumps({'answer':'x','citations':[],'confidence':'low'})}
  old=(m.source_bundle,m.tmf_bundle,m.OUT)
  with tempfile.TemporaryDirectory() as d:
   m.source_bundle=lambda t:[{'path':'A.java','lines':1,'content':'1: class A {}'}]; m.tmf_bundle=lambda t:{'claims':[]}; m.OUT=Path(d); m.OUT.mkdir(exist_ok=True)
   try: pair=m.run_pair('P01',A())
   finally: m.source_bundle,m.tmf_bundle,m.OUT=old
  self.assertTrue(pair['valid_pair']); self.assertEqual(pair['cross_arm_state_files'],[])
  self.assertTrue(all(r['broker']['calls']==1 and r['broker']['request_id'] for r in pair['rows']))
if __name__=='__main__': unittest.main()
