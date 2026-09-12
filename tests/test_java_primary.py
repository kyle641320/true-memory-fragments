import json,os,subprocess,tempfile,unittest
from unittest.mock import patch
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo

class PrimaryTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as d:
   # A fixture commit must not outlive this directory via detached maintenance.
   p=Path(d);(p/'A.java').write_text(s);subprocess.run(['git','init','-b','master'],cwd=p,check=True,stdout=subprocess.PIPE);subprocess.run(['git','config','user.email','x@y'],cwd=p,check=True);subprocess.run(['git','config','user.name','x'],cwd=p,check=True);subprocess.run(['git','add','.'],cwd=p,check=True);subprocess.run(['git','-c','maintenance.auto=false','-c','gc.auto=0','commit','-m','x'],cwd=p,check=True,stdout=subprocess.PIPE);return [x for x in derive_claims_for_path(GitRepo(p),'A.java') if x.body.get('edge_kind')=='declares_primary_presence']
 def test_fixture_commit_does_not_start_background_maintenance(self):
  # Cleanup must remain strict: disposable fixtures have no maintenance work.
  with tempfile.TemporaryDirectory() as d:
   trace=Path(d)/'git-trace.json'
   with patch.dict(os.environ, {'GIT_TRACE2_EVENT':str(trace)}):
    claims=self.claims('import org.springframework.context.annotation.Primary; @Primary class A{}')
   self.assertEqual(len(claims),1)
   events=[json.loads(line) for line in trace.read_text().splitlines()]
   self.assertTrue(any(e.get('event')=='cmd_name' and e.get('name')=='commit' for e in events))
   maintenance=[e for e in events if e.get('event')=='child_start' and any(a in {'maintenance','gc'} for a in e.get('argv',[]))]
   self.assertEqual(maintenance,[])
 def test_type_method_overloads_and_contract(self):
  s='import org.springframework.context.annotation.Primary; @Primary class A{ @Primary Object x(){return null;} @Primary Object x(String v){return v;} }';a=self.claims(s);self.assertEqual(len(a),3);self.assertEqual({x.body['owner_kind'] for x in a},{'class','method'});self.assertEqual(len({x.id for x in a}),3);self.assertTrue(all(x.bindings[0].hash_kind=='java_token_sha256' for x in a));self.assertTrue(all(x.body['metadata_handling']=='unsupported-fail-closed' for x in a))
 def test_fail_closed_negatives(self):
  cases=['@interface Primary{} @Primary class A{}','import org.springframework.context.annotation.*; @Primary class A{}','import static org.springframework.context.annotation.Primary; @Primary class A{}','import org.springframework.context.annotation.Primary; import decoy.Primary; @Primary class A{}','import org.springframework.context.annotation.Primary; class Primary{} @Primary class A{}','import org.springframework.context.annotation.Primary; @Primary(true) class A{}','import org.springframework.context.annotation.Primary; class A{@Primary String x;}','import org.springframework.context.annotation.Primary; class A{void f(){@Primary class L{}}}']
  for s in cases:self.assertFalse(self.claims(s),s)
 def test_stability_freshness_deletion_and_qualification(self):
  p='import org.springframework.context.annotation.Primary; class A{%s Object x(){return null;}}';a=self.claims(p%'@Primary')[0];b=self.claims(p%'@Primary( )')[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertEqual([a.id],[x.id for x in self.claims(p%'@Primary')]);self.assertFalse(self.claims('class A{Object x(){return null;}}'));n=' '.join(a.body['notes']).lower();self.assertIn('presence only',n);self.assertIn('bean selection',n);self.assertIn('lifecycle',n);self.assertIn('runtime',n)

if __name__=='__main__':unittest.main()
