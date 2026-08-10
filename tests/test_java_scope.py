import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo

class ScopeTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'A.java').write_text(s);subprocess.run(['git','init','-b','master'],cwd=p,check=True,stdout=subprocess.PIPE);subprocess.run(['git','config','user.email','x@y'],cwd=p,check=True);subprocess.run(['git','config','user.name','x'],cwd=p,check=True);subprocess.run(['git','add','.'],cwd=p,check=True);subprocess.run(['git','commit','-m','x'],cwd=p,check=True,stdout=subprocess.PIPE);return [x for x in derive_claims_for_path(GitRepo(p),'A.java') if x.body.get('edge_kind')=='declares_scope_presence']
 def test_type_method_overloads_and_contract(self):
  s='import org.springframework.context.annotation.Scope; @Scope class A{ @Scope Object x(){return null;} @Scope Object x(String v){return v;} }';a=self.claims(s);self.assertEqual(len(a),3);self.assertEqual({x.body['owner_kind'] for x in a},{'class','method'});self.assertEqual(len({x.id for x in a}),3);self.assertTrue(all(x.bindings[0].hash_kind=='java_token_sha256' for x in a));self.assertTrue(all(x.body['metadata_handling']=='unsupported-fail-closed' for x in a))
 def test_fail_closed_negatives(self):
  cases=['@interface Scope{} @Scope class A{}','import org.springframework.context.annotation.*; @Scope class A{}','import static org.springframework.context.annotation.Scope; @Scope class A{}','import org.springframework.context.annotation.Scope; import decoy.Scope; @Scope class A{}','import org.springframework.context.annotation.Scope; class Scope{} @Scope class A{}','import org.springframework.context.annotation.Scope; @Scope("singleton") class A{}','import org.springframework.context.annotation.Scope; class A{@Scope String x;}','import org.springframework.context.annotation.Scope; class A{void f(){@Scope class L{}}}']
  for s in cases:self.assertFalse(self.claims(s),s)
 def test_stability_freshness_deletion_and_qualification(self):
  p='import org.springframework.context.annotation.Scope; class A{%s Object x(){return null;}}';a=self.claims(p%'@Scope')[0];b=self.claims(p%'@Scope( )')[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertFalse(self.claims('class A{Object x(){return null;}}'));n=' '.join(a.body['notes']).lower();self.assertIn('presence only',n);self.assertIn('scope name',n);self.assertIn('lifecycle',n);self.assertIn('runtime',n)

if __name__=='__main__':unittest.main()
