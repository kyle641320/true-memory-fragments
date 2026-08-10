from __future__ import annotations
import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo
def run(c,w):subprocess.run(c,cwd=w,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
class ComponentTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'A.java').write_text(s);run(['git','init','-b','master'],r);run(['git','config','user.email','x@y'],r);run(['git','config','user.name','x'],r);run(['git','add','.'],r);run(['git','commit','-m','x'],r);return derive_claims_for_path(GitRepo(r),'A.java')
 def declarations(self,s):return [x for x in self.claims(s) if x.id.startswith('claim_component_decl_')]
 def test_type_presence_precise_anchors(self):
  a=self.declarations('import org.springframework.stereotype.Component;\n@Component class A{}\n@Component interface B{}');self.assertEqual(len(a),2);self.assertEqual({x.body['owner_kind'] for x in a},{'class','interface'});self.assertEqual({x.bindings[0].line_start for x in a},{2,3});self.assertTrue(all(x.bindings[0].hash_kind=='java_token_sha256' for x in a))
 def test_fail_closed(self):
  cases=['@interface Component{} @Component class A{}','import org.springframework.web.bind.annotation.*; @Component class A{}','import static org.springframework.stereotype.Component; @Component class A{}','import org.springframework.stereotype.Component; import decoy.Component; @Component class A{}','import org.springframework.stereotype.Component; class Component{} @Component class A{}','import org.springframework.stereotype.Component; @Component("x") class A{}','import org.springframework.stereotype.Component; @Component record A(){}','import org.springframework.stereotype.Component; class A{@Component void x(){}}','import org.springframework.stereotype.Component; class A{void x(){@Component class L{}}}']
  for s in cases:self.assertFalse(self.declarations(s),s)
 def test_identity_freshness_deletion_determinism_and_no_runtime(self):
  p='import org.springframework.stereotype.Component; %s class A{}';a=self.declarations(p%'@Component')[0];b=self.declarations(p%'@Component( )')[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertEqual([a.id],[x.id for x in self.declarations(p%'@Component')]);self.assertFalse(self.declarations('class A{}'));n=' '.join(a.body['notes']).lower();self.assertIn('presence only',n);self.assertIn('bean discovery',n);self.assertIn('runtime',n)
if __name__=='__main__':unittest.main()
