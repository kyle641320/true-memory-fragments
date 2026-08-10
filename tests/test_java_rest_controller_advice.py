from __future__ import annotations
import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo

def run(c,w):subprocess.run(c,cwd=w,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
class RestControllerAdviceTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'A.java').write_text(s);run(['git','init','-b','master'],r);run(['git','config','user.email','x@y'],r);run(['git','config','user.name','x'],r);run(['git','add','.'],r);run(['git','commit','-m','x'],r);return derive_claims_for_path(GitRepo(r),'A.java')
 def declarations(self,s):return [x for x in self.claims(s) if x.id.startswith('claim_rest_controller_advice_decl_')]
 def test_presence_only(self):
  s='import org.springframework.web.bind.annotation.RestControllerAdvice;\n@RestControllerAdvice class A{}\n@RestControllerAdvice interface B{}';a=self.declarations(s);self.assertEqual(len(a),2);self.assertEqual({x.body['owner_kind'] for x in a},{'class','interface'});self.assertTrue(all(x.body['source_namespace']=='org.springframework.web.bind.annotation' and x.bindings[0].line_start in (2,3) for x in a))
 def test_fail_closed(self):
  cases=['@interface RestControllerAdvice{} @RestControllerAdvice class A{}','import org.springframework.web.bind.annotation.*; @RestControllerAdvice class A{}','import static org.springframework.web.bind.annotation.RestControllerAdvice; @RestControllerAdvice class A{}','import org.springframework.web.bind.annotation.RestControllerAdvice; import decoy.RestControllerAdvice; @RestControllerAdvice class A{}','import org.springframework.web.bind.annotation.RestControllerAdvice; class RestControllerAdvice{} @RestControllerAdvice class A{}','import org.springframework.web.bind.annotation.RestControllerAdvice; @RestControllerAdvice("x") class A{}','import org.springframework.web.bind.annotation.RestControllerAdvice; class A{void x(){@RestControllerAdvice class Local{}}}']
  for s in cases:self.assertFalse(self.declarations(s),s)
 def test_stability_freshness_deletion_and_no_composition_semantics(self):
  p='import org.springframework.web.bind.annotation.RestControllerAdvice;\n%s class A{}';a=self.declarations(p%'@RestControllerAdvice')[0];b=self.declarations(p%'@RestControllerAdvice( )')[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertFalse(self.declarations(p%'@RestControllerAdvice("x")'));self.assertFalse(self.declarations('class A{}'));text=str(a.body).lower();self.assertEqual(a.body['edge_kind'],'declares_rest_controller_advice_presence');self.assertIn('not expanded',a.body['notes'][0].lower())
if __name__=='__main__':unittest.main()
