import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo

class SingletonTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'A.java').write_text(s);subprocess.run(['git','init','-b','master'],cwd=p,check=True,stdout=subprocess.PIPE);subprocess.run(['git','config','user.email','x@y'],cwd=p,check=True);subprocess.run(['git','config','user.name','x'],cwd=p,check=True);subprocess.run(['git','add','.'],cwd=p,check=True);subprocess.run(['git','commit','-m','x'],cwd=p,check=True,stdout=subprocess.PIPE);return [x for x in derive_claims_for_path(GitRepo(p),'A.java') if x.body.get('edge_kind')=='declares_singleton_presence']
 def test_direct_class_contract_and_identity(self):
  a=self.claims('import jakarta.inject.Singleton; @Singleton class A{} class Outer{@Singleton class Inner{}}');self.assertEqual({x.body['owner_qualname'] for x in a},{'A','Outer.Inner'});self.assertEqual(len({x.id for x in a}),2);self.assertTrue(all(x.body['owner_kind']=='class' for x in a));self.assertTrue(all(x.body['source_namespace']=='jakarta.inject' for x in a));self.assertTrue(all(x.bindings[0].hash_kind=='java_token_sha256' for x in a))
 def test_namespace_metadata_target_and_decoys_fail_closed(self):
  cases=['@interface Singleton{} @Singleton class A{}','import jakarta.inject.*; @Singleton class A{}','import static jakarta.inject.Singleton; @Singleton class A{}','import jakarta.inject.Singleton; import decoy.Singleton; @Singleton class A{}','import jakarta.inject.Singleton; class Singleton{} @Singleton class A{}','import jakarta.inject.Singleton; @Singleton(value="x") class A{}','import jakarta.inject.Singleton; @Singleton @Singleton class A{}','import jakarta.inject.Singleton; @Singleton interface A{}','import jakarta.inject.Singleton; @Singleton enum A{}','import jakarta.inject.Singleton; @Singleton record A(int x){}','import jakarta.inject.Singleton; class A{@Singleton void f(){}}','import jakarta.inject.Singleton; class A{void f(){@Singleton class L{}}}']
  for s in cases:self.assertFalse(self.claims(s),s)
 def test_stability_freshness_deletion_and_boundary(self):
  a=self.claims('import jakarta.inject.Singleton; @Singleton class A{}')[0];b=self.claims('import jakarta.inject.Singleton;\n@Singleton\nclass A {}')[0];self.assertEqual(a.id,b.id);self.assertEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);c=self.claims('import jakarta.inject.Singleton; @Singleton /*fresh*/ class A{}')[0];self.assertEqual(a.id,c.id);self.assertEqual(a.bindings[0].fn_hash,c.bindings[0].fn_hash);self.assertFalse(self.claims('class A{}'));n=' '.join(a.body['notes']).lower();self.assertIn('presence only',n);self.assertIn('runtime',n);self.assertIn('scope',n)

if __name__=='__main__':unittest.main()
