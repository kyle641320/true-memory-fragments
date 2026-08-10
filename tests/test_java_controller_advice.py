from __future__ import annotations
import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo

def run(c,w):subprocess.run(c,cwd=w,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
class ControllerAdviceTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'A.java').write_text(s);run(['git','init'],r);run(['git','config','user.email','x@y'],r);run(['git','config','user.name','x'],r);run(['git','add','.'],r);run(['git','commit','-m','x'],r);return derive_claims_for_path(GitRepo(r),'A.java')
 def declarations(self,s):return [x for x in self.claims(s) if x.id.startswith('claim_controller_advice_decl_')]
 def test_class_interface_presence_namespace_and_precise_anchor(self):
  s='''import org.springframework.web.bind.annotation.ControllerAdvice;\n@ControllerAdvice\nclass A {}\n@ControllerAdvice interface B {}''';a=self.declarations(s);self.assertEqual(len(a),2);self.assertEqual({x.body['owner_kind'] for x in a},{'class','interface'});self.assertTrue(all(x.body['source_namespace']=='org.springframework.web.bind.annotation' and x.bindings[0].hash_kind=='java_token_sha256' and x.bindings[0].line_start in (2,4) for x in a))
 def test_fail_closed_negatives(self):
  cases=['@interface ControllerAdvice{} @ControllerAdvice class A{}','import org.springframework.web.bind.annotation.*; @ControllerAdvice class A{}','import static org.springframework.web.bind.annotation.ControllerAdvice; @ControllerAdvice class A{}','import org.springframework.web.bind.annotation.ControllerAdvice; import decoy.ControllerAdvice; @ControllerAdvice class A{}','import org.springframework.web.bind.annotation.ControllerAdvice; class ControllerAdvice{} @ControllerAdvice class A{}','import org.springframework.web.bind.annotation.ControllerAdvice; @ControllerAdvice("x") class A{}','import org.springframework.web.bind.annotation.ControllerAdvice; class A{void x(){@ControllerAdvice class Local{}}}','import org.springframework.web.bind.annotation.ControllerAdvice; String s="@ControllerAdvice"; class A{}']
  for s in cases:self.assertFalse(self.declarations(s),s)
 def test_stable_id_mutation_freshness_deletion_and_no_runtime_claims(self):
  p='import org.springframework.web.bind.annotation.ControllerAdvice;\n%s\nclass A{}';a=self.declarations(p%'@ControllerAdvice')[0];b=self.declarations(p%'@ControllerAdvice( )')[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertFalse(self.declarations(p%'@ControllerAdvice("dynamic")'));self.assertFalse(self.declarations('class A{}'));text=str(a.body).lower();self.assertNotIn('dispatches',text);self.assertNotIn('discovers',text)
if __name__=='__main__':unittest.main()
