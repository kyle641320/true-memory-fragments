from __future__ import annotations
import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo
def run(c,w):subprocess.run(c,cwd=w,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
class SecuredTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'A.java').write_text(s);run(['git','init','-b','master'],r);run(['git','config','user.email','x@y'],r);run(['git','config','user.name','x'],r);run(['git','add','.'],r);run(['git','commit','-m','x'],r);return derive_claims_for_path(GitRepo(r),'A.java')
 def secured(self,s):return [x for x in self.claims(s) if x.id.startswith('claim_secured_decl_')]
 def test_literal_roles_overloads_and_anchor(self):
  s='import org.springframework.security.access.annotation.Secured; class A{@Secured("ROLE_ADMIN") void x(){} @Secured({"ROLE_USER","ROLE_AUDITOR"}) void x(String id){}}'
  a=self.secured(s);self.assertEqual(len(a),2);self.assertEqual(len({x.body['owner_id'] for x in a}),2);self.assertEqual({tuple(x.body['roles']) for x in a},{('ROLE_ADMIN',),('ROLE_USER','ROLE_AUDITOR')});self.assertTrue(all(x.bindings[0].line_start==1 and x.bindings[0].hash_kind=='java_token_sha256' for x in a))
 def test_fail_closed(self):
  cases=['@interface Secured{} class A{@Secured("X") void x(){}}','import org.springframework.security.access.annotation.*; class A{@Secured("X") void x(){}}','import org.springframework.security.access.annotation.Secured; import decoy.Secured; class A{@Secured("X") void x(){}}','import org.springframework.security.access.annotation.Secured; class A{static final String X="X";@Secured(X) void x(){}}','import org.springframework.security.access.annotation.Secured; class A{@Secured("${x}") void x(){}}','import org.springframework.security.access.annotation.Secured; class A{@Secured({"X", X}) void x(){}}']
  for s in cases:
   c=self.claims(s);self.assertFalse([x for x in c if x.id.startswith('claim_secured_decl_')]);self.assertTrue(next(x for x in c if x.scope=='file').body.get('java_secured_unresolved'))
 def test_stable_mutation_delete_no_calls(self):
  p='import org.springframework.security.access.annotation.Secured; class A{@Secured("%s") void x(){}}';a=self.secured(p%'ONE')[0];b=self.secured(p%'TWO')[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertFalse(self.secured('class A{void x(){}}'));self.assertNotIn('calls',a.body)
if __name__=='__main__':unittest.main()
