import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo

class NamedTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'A.java').write_text(s);subprocess.run(['git','init','-b','master'],cwd=p,check=True,stdout=subprocess.PIPE);subprocess.run(['git','config','user.email','x@y'],cwd=p,check=True);subprocess.run(['git','config','user.name','x'],cwd=p,check=True);subprocess.run(['git','add','.'],cwd=p,check=True);subprocess.run(['git','commit','-m','x'],cwd=p,check=True,stdout=subprocess.PIPE);return [x for x in derive_claims_for_path(GitRepo(p),'A.java') if x.body.get('edge_kind')=='declares_named_presence']
 def test_direct_default_named_contract_and_identity(self):
  a=self.claims('import jakarta.inject.Named; @Named class A{@Named Object f; @Named Object make(){return f;} static class N{@Named static Object x;}}');self.assertEqual({x.body['owner_qualname'] for x in a},{'A','A.f','A.make','A.N.x'});self.assertEqual({x.body['owner_kind'] for x in a},{'class','field','method'});self.assertEqual(len({x.id for x in a}),4);self.assertTrue(all(x.body['source_namespace']=='jakarta.inject' for x in a));self.assertTrue(all(x.body['metadata_handling']=='metadata-free-default-name-only-fail-closed' for x in a))
 def test_namespace_explicit_name_target_and_decoys_fail_closed(self):
  cases=['@interface Named{} @Named class A{}','import jakarta.inject.*; @Named class A{}','import static jakarta.inject.Named; @Named class A{}','import jakarta.inject.Named; import decoy.Named; @Named class A{}','import jakarta.inject.Named; class Named{} @Named class A{}','import jakarta.inject.Named; @Named("x") class A{}','import jakarta.inject.Named; @Named(value="x") class A{}','import jakarta.inject.Named; @Named @Named class A{}','import jakarta.inject.Named; @Named interface A{}','import jakarta.inject.Named; @Named enum A{}','import jakarta.inject.Named; @Named record A(int x){}','import jakarta.inject.Named; class A{void f(@Named Object x){}}','import jakarta.inject.Named; class A{@Named Object a,b;}','import jakarta.inject.Named; class A{void f(){@Named class L{}}}','import jakarta.inject.Named; class A{Object x=new Object(){@Named Object hidden;};}']
  for s in cases:self.assertFalse(self.claims(s),s)
 def test_stability_freshness_deletion_and_boundary(self):
  a=self.claims('import jakarta.inject.Named; @Named class A{}')[0];b=self.claims('import jakarta.inject.Named;\n@Named\nclass A {}')[0];self.assertEqual(a.id,b.id);self.assertEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);c=self.claims('import jakarta.inject.Named; @Named /*fresh*/ class A{}')[0];self.assertEqual(a.id,c.id);self.assertEqual(a.bindings[0].fn_hash,c.bindings[0].fn_hash);self.assertFalse(self.claims('class A{}'));n=' '.join(a.body['notes']).lower();self.assertIn('presence only',n);self.assertIn('explicit names',n);self.assertIn('runtime',n)

if __name__=='__main__':unittest.main()
