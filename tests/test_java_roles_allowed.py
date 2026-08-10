from __future__ import annotations
import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo
def run(c,w):subprocess.run(c,cwd=w,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
class RolesAllowedTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'A.java').write_text(s);run(['git','init','-b','master'],r);run(['git','config','user.email','x@y'],r);run(['git','config','user.name','x'],r);run(['git','add','.'],r);run(['git','commit','-m','x'],r);return derive_claims_for_path(GitRepo(r),'A.java')
 def roles(self,s):return [x for x in self.claims(s) if x.id.startswith('claim_roles_allowed_decl_')]
 def test_namespaces_literals_overloads_and_anchor(self):
  for ns in ('jakarta','javax'):
   s=f'import {ns}.annotation.security.RolesAllowed; class A{{@RolesAllowed("ADMIN") void x(){{}} @RolesAllowed({{"USER","AUDITOR"}}) void x(String id){{}}}}'
   a=self.roles(s);self.assertEqual(len(a),2);self.assertEqual({x.body['source_namespace'] for x in a},{ns});self.assertEqual({tuple(x.body['roles']) for x in a},{('ADMIN',),('USER','AUDITOR')});self.assertEqual(len({x.body['owner_id'] for x in a}),2);self.assertTrue(all(x.bindings[0].line_start==1 and x.bindings[0].hash_kind=='java_token_sha256' for x in a))
 def test_fail_closed_imports_and_values(self):
  cases=['@interface RolesAllowed{} class A{@RolesAllowed("X") void x(){}}','import jakarta.annotation.security.*; class A{@RolesAllowed("X") void x(){}}','import static jakarta.annotation.security.RolesAllowed.*; class A{@RolesAllowed("X") void x(){}}','import jakarta.annotation.security.RolesAllowed; import javax.annotation.security.RolesAllowed; class A{@RolesAllowed("X") void x(){}}','import jakarta.annotation.security.RolesAllowed; import decoy.RolesAllowed; class A{@RolesAllowed("X") void x(){}}','import jakarta.annotation.security.RolesAllowed; class A{static final String X="X";@RolesAllowed(X) void x(){}}','import jakarta.annotation.security.RolesAllowed; class A{@RolesAllowed("${x}") void x(){}}','import jakarta.annotation.security.RolesAllowed; class A{@RolesAllowed({"X", X}) void x(){}}']
  for s in cases:
   c=self.claims(s);self.assertFalse([x for x in c if x.id.startswith('claim_roles_allowed_decl_')]);self.assertTrue(next(x for x in c if x.scope=='file').body.get('java_roles_allowed_unresolved'))
 def test_stable_mutation_delete_no_runtime_semantics(self):
  p='import jakarta.annotation.security.RolesAllowed; class A{@RolesAllowed("%s") void x(){}}';a=self.roles(p%'ONE')[0];b=self.roles(p%'TWO')[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertFalse(self.roles('class A{void x(){}}'));self.assertNotIn('calls',a.body);self.assertNotIn('authorized',a.body)
if __name__=='__main__':unittest.main()
