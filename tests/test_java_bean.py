from __future__ import annotations
import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo
def run(c,w):subprocess.run(c,cwd=w,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
class BeanTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'A.java').write_text(s);run(['git','init','-b','master'],r);run(['git','config','user.email','x@y'],r);run(['git','config','user.name','x'],r);run(['git','add','.'],r);run(['git','commit','-m','x'],r);return derive_claims_for_path(GitRepo(r),'A.java')
 def declarations(self,s):return [x for x in self.claims(s) if x.id.startswith('claim_bean_decl_')]
 def test_method_presence_precise_anchor_and_overloads(self):
  s='import org.springframework.context.annotation.Bean; class A{ @Bean Object x(){return null;} @Bean Object x(String v){return v;} }';a=self.declarations(s);self.assertEqual(len(a),2);self.assertEqual({x.body['owner_kind'] for x in a},{'method'});self.assertEqual({x.bindings[0].line_start for x in a},{1});self.assertEqual(len({x.id for x in a}),2);self.assertTrue(all(x.bindings[0].hash_kind=='java_token_sha256' for x in a))
 def test_exact_direct_method_and_metadata_fail_closed(self):
  cases=['@interface Bean{} class A{@Bean Object x(){return null;}}','import org.springframework.context.annotation.*; class A{@Bean Object x(){return null;}}','import static org.springframework.context.annotation.Bean; class A{@Bean Object x(){return null;}}','import org.springframework.context.annotation.Bean; import decoy.Bean; class A{@Bean Object x(){return null;}}','import org.springframework.context.annotation.Bean; class Bean{} class A{@Bean Object x(){return null;}}','import org.springframework.context.annotation.Bean; @Bean class A{}','import org.springframework.context.annotation.Bean; class A{@Bean(name="x") Object x(){return null;}}','import org.springframework.context.annotation.Bean; class A{@Bean(value="x") Object x(){return null;}}','import org.springframework.context.annotation.Bean; class A{@Bean(initMethod="i") Object x(){return null;}}','import org.springframework.context.annotation.Bean; class A{@Bean(destroyMethod="d") Object x(){return null;}}']
  self.assertEqual(len(self.declarations('import org.springframework.context.annotation.Bean; class A{@Bean Object f(){ class L{@Bean Object x(){return null;}} return null;}}')),1)
  for s in cases:self.assertFalse(self.declarations(s),s)
 def test_identity_freshness_deletion_determinism_and_no_runtime(self):
  p='import org.springframework.context.annotation.Bean; class A{%s Object x(){return null;}}';a=self.declarations(p%'@Bean')[0];b=self.declarations(p%'@Bean( )')[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertEqual([a.id],[x.id for x in self.declarations(p%'@Bean')]);self.assertFalse(self.declarations('class A{Object x(){return null;}}'));n=' '.join(a.body['notes']).lower();self.assertIn('presence only',n);self.assertIn('bean lifecycle',n);self.assertIn('dependency graph',n);self.assertIn('factory',n);self.assertIn('runtime',n)
if __name__=='__main__':unittest.main()
