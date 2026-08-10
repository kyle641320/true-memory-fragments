from __future__ import annotations
import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo
def run(c,w):subprocess.run(c,cwd=w,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
class PreFilterTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'A.java').write_text(s);run(['git','init'],r);run(['git','config','user.email','x@y'],r);run(['git','config','user.name','x'],r);run(['git','add','.'],r);run(['git','commit','-m','x'],r);return derive_claims_for_path(GitRepo(r),'A.java')
 def pf(self,s):return [x for x in self.claims(s) if x.id.startswith('claim_pre_filter_decl_')]
 def test_opaque_literals_overloads_and_target(self):
  s='import org.springframework.security.access.prepost.PreFilter; class A{@PreFilter("filterObject.owner == authentication.name") void x(){} @PreFilter(value="opaque #id", filterTarget="items") void x(String id){}}'
  a=self.pf(s);self.assertEqual(len(a),2);self.assertEqual(len({x.body['owner_id'] for x in a}),2);self.assertEqual({x.body['filter_target'] for x in a},{None,'items'});self.assertTrue(all(x.bindings[0].hash_kind=='java_token_sha256' for x in a));self.assertTrue(all('calls' not in x.body for x in a))
 def test_fail_closed(self):
  cases=['@interface PreFilter{} class A{@PreFilter("x") void x(){}}','import org.springframework.security.access.prepost.*; class A{@PreFilter("x") void x(){}}','import org.springframework.security.access.prepost.PreFilter; import decoy.PreFilter; class A{@PreFilter("x") void x(){}}','import org.springframework.security.access.prepost.PreFilter; class A{static final String X="x";@PreFilter(X) void x(){}}','import org.springframework.security.access.prepost.PreFilter; class A{@PreFilter("${x}") void x(){}}','import static org.springframework.security.access.prepost.PreFilter; class A{@PreFilter("x") void x(){}}','import org.springframework.security.access.prepost.PreFilter; class A{@PreFilter(value="x", value="y") void x(){}}','import org.springframework.security.access.prepost.PreFilter; class A{@PreFilter(foo="x") void x(){}}','import org.springframework.security.access.prepost.PreFilter; @PreFilter("x") class A{}','import org.springframework.security.access.prepost.PreFilter; class A{@PreFilter(value="x",filterTarget=X) void x(){}}']
  for s in cases:
   c=self.claims(s);self.assertFalse([x for x in c if x.id.startswith('claim_pre_filter_decl_')]);self.assertTrue(next(x for x in c if x.scope=='file').body.get('java_pre_filter_unresolved'))
 def test_stable_mutation_delete(self):
  p='import org.springframework.security.access.prepost.PreFilter; class A{@PreFilter("%s") void x(){}}';a=self.pf(p%'one')[0];b=self.pf(p%'two')[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertFalse(self.pf('class A{void x(){}}'))
