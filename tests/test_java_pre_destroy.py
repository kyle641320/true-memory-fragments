import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo

class PreDestroyTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d);(p/'A.java').write_text(s);subprocess.run(['git','init','-b','master'],cwd=p,check=True,stdout=subprocess.PIPE);subprocess.run(['git','config','user.email','x@y'],cwd=p,check=True);subprocess.run(['git','config','user.name','x'],cwd=p,check=True);subprocess.run(['git','add','.'],cwd=p,check=True);subprocess.run(['git','commit','-m','x'],cwd=p,check=True,stdout=subprocess.PIPE);return [x for x in derive_claims_for_path(GitRepo(p),'A.java') if x.body.get('edge_kind')=='declares_pre_destroy_presence']
 def test_methods_overloads_and_contract(self):
  s='import jakarta.annotation.PreDestroy; class A{ @PreDestroy void x(){} @PreDestroy void x(String v){} }';a=self.claims(s);self.assertEqual(len(a),2);self.assertEqual(len({x.id for x in a}),2);self.assertTrue(all(x.body['source_namespace']=='jakarta.annotation' for x in a));self.assertTrue(all(x.bindings[0].hash_kind=='java_token_sha256' for x in a))
 def test_namespace_and_fail_closed_negatives(self):
  cases=['@interface PreDestroy{} class A{@PreDestroy void x(){}}','import jakarta.annotation.*; class A{@PreDestroy void x(){}}','import static jakarta.annotation.PreDestroy; class A{@PreDestroy void x(){}}','import javax.annotation.PreDestroy; class A{@PreDestroy void x(){}}','import jakarta.annotation.PreDestroy; import javax.annotation.PreDestroy; class A{@PreDestroy void x(){}}','import jakarta.annotation.PreDestroy; import decoy.PreDestroy; class A{@PreDestroy void x(){}}','import jakarta.annotation.PreDestroy; class PreDestroy{} class A{@PreDestroy void x(){}}','import jakarta.annotation.PreDestroy; @PreDestroy class A{}','import jakarta.annotation.PreDestroy; class A{@PreDestroy int x;}','import jakarta.annotation.PreDestroy; class A{void f(){class L{@PreDestroy void x(){}}}}']
  for s in cases:self.assertFalse(self.claims(s),s)
 def test_stability_freshness_deletion_and_boundary(self):
  p='import jakarta.annotation.PreDestroy; class A{%s void x(){}}';a=self.claims(p%'@PreDestroy')[0];b=self.claims(p%'@PreDestroy()')[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertFalse(self.claims('class A{void x(){}}'));n=' '.join(a.body['notes']).lower();self.assertIn('presence only',n);self.assertIn('jakarta namespace only',n);self.assertIn('javax.annotation.predestroy',n);self.assertIn('runtime',n)

if __name__=='__main__':unittest.main()
