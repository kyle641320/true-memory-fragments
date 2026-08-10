from __future__ import annotations
import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo
def run(c,w):subprocess.run(c,cwd=w,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
class ConfigurationTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'A.java').write_text(s);run(['git','init','-b','master'],r);run(['git','config','user.email','x@y'],r);run(['git','config','user.name','x'],r);run(['git','add','.'],r);run(['git','commit','-m','x'],r);return derive_claims_for_path(GitRepo(r),'A.java')
 def declarations(self,s):return [x for x in self.claims(s) if x.id.startswith('claim_configuration_decl_')]
 def test_type_presence_precise_anchors(self):
  a=self.declarations('import org.springframework.context.annotation.Configuration;\n@Configuration class A{}\n@Configuration interface B{}');self.assertEqual(len(a),2);self.assertEqual({x.body['owner_kind'] for x in a},{'class','interface'});self.assertEqual({x.bindings[0].line_start for x in a},{2,3});self.assertTrue(all(x.bindings[0].hash_kind=='java_token_sha256' for x in a))
 def test_fail_closed_and_distinct_from_configuration_properties(self):
  cases=['@interface Configuration{} @Configuration class A{}','import org.springframework.context.annotation.*; @Configuration class A{}','import static org.springframework.context.annotation.Configuration; @Configuration class A{}','import org.springframework.context.annotation.Configuration; import decoy.Configuration; @Configuration class A{}','import org.springframework.context.annotation.Configuration; class Configuration{} @Configuration class A{}','import org.springframework.context.annotation.Configuration; @Configuration(proxyBeanMethods=false) class A{}','import org.springframework.context.annotation.Configuration; @Configuration record A(){}','import org.springframework.context.annotation.Configuration; class A{@Configuration void x(){}}','import org.springframework.boot.context.properties.ConfigurationProperties; @ConfigurationProperties("x") class A{}']
  for s in cases:self.assertFalse(self.declarations(s),s)
 def test_identity_freshness_deletion_determinism_and_no_runtime(self):
  p='import org.springframework.context.annotation.Configuration; %s class A{}';a=self.declarations(p%'@Configuration')[0];b=self.declarations(p%'@Configuration( )')[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertEqual([a.id],[x.id for x in self.declarations(p%'@Configuration')]);self.assertFalse(self.declarations('class A{}'));n=' '.join(a.body['notes']).lower();self.assertIn('presence only',n);self.assertIn('bean lifecycle',n);self.assertIn('component scan',n);self.assertIn('runtime',n)
if __name__=='__main__':unittest.main()
