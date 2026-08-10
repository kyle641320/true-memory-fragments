from __future__ import annotations
import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo
def run(c,w):subprocess.run(c,cwd=w,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
class ServiceTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'A.java').write_text(s);run(['git','init','-b','master'],r);run(['git','config','user.email','x@y'],r);run(['git','config','user.name','x'],r);run(['git','add','.'],r);run(['git','commit','-m','x'],r);return derive_claims_for_path(GitRepo(r),'A.java')
 def declarations(self,s):return [x for x in self.claims(s) if x.id.startswith('claim_service_decl_')]
 def test_type_presence_precise_anchors(self):
  a=self.declarations('import org.springframework.stereotype.Service;\n@Service class A{}\n@Service interface B{}');self.assertEqual(len(a),2);self.assertEqual({x.body['owner_kind'] for x in a},{'class','interface'});self.assertEqual({x.bindings[0].line_start for x in a},{2,3});self.assertTrue(all(x.bindings[0].hash_kind=='java_token_sha256' for x in a))
 def test_fail_closed(self):
  cases=['@interface Service{} @Service class A{}','import org.springframework.web.bind.annotation.*; @Service class A{}','import static org.springframework.stereotype.Service; @Service class A{}','import org.springframework.stereotype.Service; import decoy.Service; @Service class A{}','import org.springframework.stereotype.Service; class Service{} @Service class A{}','import org.springframework.stereotype.Service; @Service("x") class A{}','import org.springframework.stereotype.Service; @Service record A(){}','import org.springframework.stereotype.Service; class A{@Service void x(){}}','import org.springframework.stereotype.Service; class A{void x(){@Service class L{}}}']
  for s in cases:self.assertFalse(self.declarations(s),s)
 def test_identity_freshness_deletion_determinism_and_no_runtime(self):
  p='import org.springframework.stereotype.Service; %s class A{}';a=self.declarations(p%'@Service')[0];b=self.declarations(p%'@Service( )')[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertEqual([a.id],[x.id for x in self.declarations(p%'@Service')]);self.assertFalse(self.declarations('class A{}'));n=' '.join(a.body['notes']).lower();self.assertIn('presence only',n);self.assertIn('bean discovery',n);self.assertIn('runtime',n)
if __name__=='__main__':unittest.main()
