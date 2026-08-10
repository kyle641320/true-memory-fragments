from __future__ import annotations
import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo
def run(c,w):subprocess.run(c,cwd=w,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
class PreAuthorizeTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'A.java').write_text(s);run(['git','init','-b','master'],r);run(['git','config','user.email','x@y'],r);run(['git','config','user.name','x'],r);run(['git','add','.'],r);run(['git','commit','-m','x'],r);return derive_claims_for_path(GitRepo(r),'A.java')
 def pa(self,s):return [x for x in self.claims(s) if x.id.startswith('claim_pre_authorize_decl_')]
 def test_opaque_literal_overloads(self):
  s='import org.springframework.security.access.prepost.PreAuthorize; class A{@PreAuthorize("hasRole(\\"ADMIN\\")") void x(){} @PreAuthorize(value="opaque #id") void x(String id){}}'
  a=self.pa(s);self.assertEqual(len(a),2);self.assertEqual(len({x.body['owner_id'] for x in a}),2);self.assertEqual(a[0].body['values_handling'],'opaque-never-interpreted');self.assertTrue(all(x.bindings[0].hash_kind=='java_token_sha256' for x in a))
 def test_fail_closed(self):
  cases=['@interface PreAuthorize{} class A{@PreAuthorize("x") void x(){}}','import org.springframework.security.access.prepost.*; class A{@PreAuthorize("x") void x(){}}','import org.springframework.security.access.prepost.PreAuthorize; import decoy.PreAuthorize; class A{@PreAuthorize("x") void x(){}}','import org.springframework.security.access.prepost.PreAuthorize; class A{static final String X="x";@PreAuthorize(X) void x(){}}','import org.springframework.security.access.prepost.PreAuthorize; class A{@PreAuthorize("${x}") void x(){}}','import static org.springframework.security.access.prepost.PreAuthorize; class A{@PreAuthorize("x") void x(){}}','import org.springframework.security.access.prepost.PreAuthorize; class A{@PreAuthorize(value="x", value="y") void x(){}}','import org.springframework.security.access.prepost.PreAuthorize; class A{@PreAuthorize(foo="x") void x(){}}']
  for s in cases:
   c=self.claims(s);self.assertFalse([x for x in c if x.id.startswith('claim_pre_authorize_decl_')]);self.assertTrue(next(x for x in c if x.scope=='file').body.get('java_pre_authorize_unresolved'))
 def test_stable_mutation_delete_no_calls(self):
  p='import org.springframework.security.access.prepost.PreAuthorize; class A{@PreAuthorize("%s") void x(){}}';a=self.pa(p%'one')[0];b=self.pa(p%'two')[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertFalse(self.pa('class A{void x(){}}'));self.assertNotIn('calls',a.body)
