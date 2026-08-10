from __future__ import annotations
import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo

def run(c,w):subprocess.run(c,cwd=w,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
class CrossOriginTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'A.java').write_text(s);run(['git','init','-b','master'],r);run(['git','config','user.email','x@y'],r);run(['git','config','user.name','x'],r);run(['git','add','.'],r);run(['git','commit','-m','x'],r);return derive_claims_for_path(GitRepo(r),'A.java')
 def declarations(self,s):return [x for x in self.claims(s) if x.id.startswith('claim_cross_origin_decl_')]
 def test_type_and_method_presence_precise_anchors(self):
  s='import org.springframework.web.bind.annotation.CrossOrigin;\n@CrossOrigin class A{\n @CrossOrigin void x(){}\n}\n@CrossOrigin interface B{}'
  a=self.declarations(s);self.assertEqual(len(a),3);self.assertEqual({x.body['owner_kind'] for x in a},{'class','interface','method'});self.assertEqual({x.bindings[0].line_start for x in a},{2,3,5});self.assertTrue(all(x.bindings[0].line_start==x.bindings[0].line_end and x.bindings[0].hash_kind=='java_token_sha256' for x in a))
 def test_qualification_wrong_targets_metadata_dynamic_and_decoys_fail_closed(self):
  cases=['@interface CrossOrigin{} @CrossOrigin class A{}','import org.springframework.web.bind.annotation.*; @CrossOrigin class A{}','import static org.springframework.web.bind.annotation.CrossOrigin; @CrossOrigin class A{}','import org.springframework.web.bind.annotation.CrossOrigin; import decoy.CrossOrigin; @CrossOrigin class A{}','import org.springframework.web.bind.annotation.CrossOrigin; class CrossOrigin{} @CrossOrigin class A{}','import org.springframework.web.bind.annotation.CrossOrigin; @CrossOrigin("https://x") class A{}','import org.springframework.web.bind.annotation.CrossOrigin; @CrossOrigin(origins="${cors}") class A{}','import org.springframework.web.bind.annotation.CrossOrigin; @CrossOrigin record A(){}','import org.springframework.web.bind.annotation.CrossOrigin; class A{@CrossOrigin int x;}','import org.springframework.web.bind.annotation.CrossOrigin; class A{void x(){@CrossOrigin class L{}}}','import org.springframework.web.bind.annotation.CrossOrigin; class A{String s="@CrossOrigin";}']
  for s in cases:self.assertFalse(self.declarations(s),s)
 def test_overload_safe_identity_and_determinism(self):
  s='import org.springframework.web.bind.annotation.CrossOrigin; class A{@CrossOrigin void x(String a){} @CrossOrigin void x(int a){}}'
  a=self.declarations(s);self.assertEqual(len(a),2);self.assertEqual(len({x.id for x in a}),2);self.assertEqual([x.id for x in a],[x.id for x in self.declarations(s)])
 def test_freshness_deletion_and_no_runtime_inference(self):
  a=self.declarations('import org.springframework.web.bind.annotation.CrossOrigin; @CrossOrigin class A{}')[0];b=self.declarations('import org.springframework.web.bind.annotation.CrossOrigin; @CrossOrigin( ) class A{}')[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertFalse(self.declarations('class A{}'));self.assertEqual(a.body['edge_kind'],'declares_cross_origin_presence');notes=' '.join(a.body['notes']).lower();self.assertIn('presence only',notes);self.assertIn('runtime',notes);self.assertIn('cors',notes);self.assertNotIn('origins',a.body)
if __name__=='__main__':unittest.main()
