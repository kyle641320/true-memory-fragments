import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo

class AutowiredTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'A.java').write_text(s);subprocess.run(['git','init','-b','master'],cwd=p,check=True,stdout=subprocess.PIPE);subprocess.run(['git','config','user.email','x@y'],cwd=p,check=True);subprocess.run(['git','config','user.name','x'],cwd=p,check=True);subprocess.run(['git','add','.'],cwd=p,check=True);subprocess.run(['git','commit','-m','x'],cwd=p,check=True,stdout=subprocess.PIPE);return [x for x in derive_claims_for_path(GitRepo(p),'A.java') if x.body.get('edge_kind')=='declares_autowired_presence']
 def test_constructor_method_field_contract_and_identity(self):
  s='import org.springframework.beans.factory.annotation.Autowired; class A{ @Autowired A(Object x){} @Autowired Object client; @Autowired void setClient(Object v){} }';a=self.claims(s);self.assertEqual({x.body['owner_kind'] for x in a},{'constructor','field','method'});self.assertEqual(len(a),3);self.assertEqual(len({x.id for x in a}),3);self.assertTrue(all(x.body['source_namespace']=='org.springframework.beans.factory.annotation' for x in a));self.assertTrue(all(x.bindings[0].hash_kind=='java_token_sha256' for x in a))
 def test_overloads_and_separate_fields_have_stable_unique_identity(self):
  s='import org.springframework.beans.factory.annotation.Autowired; class A{@Autowired A(Object x){} @Autowired A(String x){} @Autowired Object a; @Autowired Object b; @Autowired void set(Object x){} @Autowired void set(String x){}}';a=self.claims(s);self.assertEqual(len(a),6);self.assertEqual(len({x.id for x in a}),6)
 def test_import_metadata_target_and_identity_fail_closed(self):
  cases=['@interface Autowired{} class A{@Autowired Object x;}','import org.springframework.beans.factory.annotation.*; class A{@Autowired Object x;}','import static org.springframework.beans.factory.annotation.Autowired; class A{@Autowired Object x;}','import decoy.Autowired; class A{@Autowired Object x;}','import org.springframework.beans.factory.annotation.Autowired; import decoy.Autowired; class A{@Autowired Object x;}','import org.springframework.beans.factory.annotation.Autowired; class Autowired{} class A{@Autowired Object x;}','import org.springframework.beans.factory.annotation.Autowired; class A{@Autowired(required=false) Object x;}','import org.springframework.beans.factory.annotation.Autowired; class A{@Autowired Object a,b;}','import org.springframework.beans.factory.annotation.Autowired; class A{@Autowired static Object x;}','import org.springframework.beans.factory.annotation.Autowired; class A{@Autowired static void set(Object x){}}','import org.springframework.beans.factory.annotation.Autowired; class A{void f(){class L{@Autowired Object x;}}}','import org.springframework.beans.factory.annotation.Autowired; class A{Object x=new Object(){@Autowired Object client;};}','import org.springframework.beans.factory.annotation.Autowired; class A{Object x=new Object(){@Autowired void set(Object v){}};}','import org.springframework.beans.factory.annotation.Autowired; class A{void f(@Autowired Object x){}}','import org.springframework.beans.factory.annotation.Autowired; @Autowired class A{}']
  for s in cases:self.assertFalse(self.claims(s),s)
 def test_stability_freshness_deletion_and_boundary(self):
  p='import org.springframework.beans.factory.annotation.Autowired; class A{%s Object client;}';a=self.claims(p%'@Autowired')[0];b=self.claims(p%'@Autowired( )')[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertFalse(self.claims('class A{Object client;}'));n=' '.join(a.body['notes']).lower();self.assertIn('presence only',n);self.assertIn('metadata-free',n);self.assertIn('runtime',n);self.assertIn('multi-declarator',n)

if __name__=='__main__':unittest.main()
