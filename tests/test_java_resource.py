import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo

class ResourceTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'A.java').write_text(s);subprocess.run(['git','init','-b','master'],cwd=p,check=True,stdout=subprocess.PIPE);subprocess.run(['git','config','user.email','x@y'],cwd=p,check=True);subprocess.run(['git','config','user.name','x'],cwd=p,check=True);subprocess.run(['git','add','.'],cwd=p,check=True);subprocess.run(['git','commit','-m','x'],cwd=p,check=True,stdout=subprocess.PIPE);return [x for x in derive_claims_for_path(GitRepo(p),'A.java') if x.body.get('edge_kind')=='declares_resource_presence']
 def test_type_method_field_contract_and_identity(self):
  s='import jakarta.annotation.Resource; @Resource class A{ @Resource Object client; @Resource void setClient(Object v){} }';a=self.claims(s);self.assertEqual({x.body['owner_kind'] for x in a},{'class','field','method'});self.assertEqual(len(a),3);self.assertEqual(len({x.id for x in a}),3);self.assertTrue(all(x.body['source_namespace']=='jakarta.annotation' for x in a));self.assertTrue(all(x.bindings[0].hash_kind=='java_token_sha256' for x in a))
 def test_overloads_and_separate_fields_have_stable_unique_identity(self):
  s='import jakarta.annotation.Resource; class A{@Resource Object a; @Resource Object b; @Resource void set(Object x){} @Resource void set(String x){}}';a=self.claims(s);self.assertEqual(len(a),4);self.assertEqual(len({x.id for x in a}),4)
 def test_namespace_metadata_target_and_identity_fail_closed(self):
  cases=['@interface Resource{} class A{@Resource Object x;}','import jakarta.annotation.*; class A{@Resource Object x;}','import static jakarta.annotation.Resource; class A{@Resource Object x;}','import jakarta.annotation.Resource; import decoy.Resource; class A{@Resource Object x;}','import jakarta.annotation.Resource; class Resource{} class A{@Resource Object x;}','import jakarta.annotation.Resource; class A{@Resource(name="x") Object x;}','import jakarta.annotation.Resource; class A{@Resource Object a,b;}','import jakarta.annotation.Resource; class A{@Resource static Object x;}','import jakarta.annotation.Resource; class A{@Resource static void set(Object x){}}','import jakarta.annotation.Resource; class A{void f(){class L{@Resource Object x;}}}','import jakarta.annotation.Resource; class A{Object x=new Object(){@Resource Object client;};}','import jakarta.annotation.Resource; class A{Object x=new Object(){@Resource void set(Object v){}};}','import jakarta.annotation.Resource; class A{void f(@Resource Object x){}}','import jakarta.annotation.Resource; @Resource interface A{}']
  for s in cases:self.assertFalse(self.claims(s),s)
 def test_stability_freshness_deletion_and_boundary(self):
  p='import jakarta.annotation.Resource; class A{%s Object client;}';a=self.claims(p%'@Resource')[0];b=self.claims(p%'@Resource( )')[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertFalse(self.claims('class A{Object client;}'));n=' '.join(a.body['notes']).lower();self.assertIn('presence only',n);self.assertIn('metadata-free',n);self.assertIn('runtime',n);self.assertIn('multi-declarator',n)

if __name__=='__main__':unittest.main()
