from __future__ import annotations
import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo

def run(c,w):subprocess.run(c,cwd=w,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
class SessionAttributesTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'A.java').write_text(s);run(['git','init','-b','master'],r);run(['git','config','user.email','x@y'],r);run(['git','config','user.name','x'],r);run(['git','add','.'],r);run(['git','commit','-m','x'],r);return derive_claims_for_path(GitRepo(r),'A.java')
 def declarations(self,s):return [x for x in self.claims(s) if x.id.startswith('claim_session_attributes_decl_')]
 def test_class_interface_presence_and_precise_anchors(self):
  s='import org.springframework.web.bind.annotation.SessionAttributes;\n@SessionAttributes class A{}\n@SessionAttributes interface B{}'
  a=self.declarations(s);self.assertEqual(len(a),2);self.assertEqual({x.body['owner_kind'] for x in a},{'class','interface'});self.assertEqual({x.bindings[0].line_start for x in a},{2,3});self.assertTrue(all(x.bindings[0].line_start==x.bindings[0].line_end and x.bindings[0].hash_kind=='java_token_sha256' for x in a))
 def test_qualification_wrong_targets_and_metadata_fail_closed(self):
  cases=['@interface SessionAttributes{} @SessionAttributes class A{}','import org.springframework.web.bind.annotation.*; @SessionAttributes class A{}','import static org.springframework.web.bind.annotation.SessionAttributes; @SessionAttributes class A{}','import org.springframework.web.bind.annotation.SessionAttributes; import decoy.SessionAttributes; @SessionAttributes class A{}','import org.springframework.web.bind.annotation.SessionAttributes; class SessionAttributes{} @SessionAttributes class A{}','import org.springframework.web.bind.annotation.SessionAttributes; @SessionAttributes("x") class A{}','import org.springframework.web.bind.annotation.SessionAttributes; @SessionAttributes(names="x") class A{}','import org.springframework.web.bind.annotation.SessionAttributes; @SessionAttributes record A(){}','import org.springframework.web.bind.annotation.SessionAttributes; class A{@SessionAttributes void x(){}}','import org.springframework.web.bind.annotation.SessionAttributes; class A{void x(){@SessionAttributes class L{}}}','import org.springframework.web.bind.annotation.SessionAttributes; class A{String s="@SessionAttributes";}']
  for s in cases:self.assertFalse(self.declarations(s),s)
 def test_stability_freshness_deletion_and_no_runtime_inference(self):
  a=self.declarations('import org.springframework.web.bind.annotation.SessionAttributes; @SessionAttributes class A{}')[0];b=self.declarations('import org.springframework.web.bind.annotation.SessionAttributes; @SessionAttributes( ) class A{}')[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertFalse(self.declarations('class A{}'));self.assertEqual(a.body['edge_kind'],'declares_session_attributes_presence');notes=' '.join(a.body['notes']).lower();self.assertIn('presence only',notes);self.assertIn('runtime',notes);self.assertNotIn('names',a.body)
if __name__=='__main__':unittest.main()
