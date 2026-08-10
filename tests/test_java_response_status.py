from __future__ import annotations
import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo

def run(c,w):subprocess.run(c,cwd=w,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
class ResponseStatusTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'A.java').write_text(s);run(['git','init','-b','master'],r);run(['git','config','user.email','x@y'],r);run(['git','config','user.name','x'],r);run(['git','add','.'],r);run(['git','commit','-m','x'],r);return derive_claims_for_path(GitRepo(r),'A.java')
 def declarations(self,s):return [x for x in self.claims(s) if x.id.startswith('claim_response_status_decl_')]
 def test_class_method_presence_overloads_and_precise_anchors(self):
  s='import org.springframework.web.bind.annotation.ResponseStatus;\n@ResponseStatus class A{\n @ResponseStatus Object item(){return null;}\n @ResponseStatus Object item(String x){return null;}\n}'
  a=self.declarations(s);self.assertEqual(len(a),3);self.assertEqual(len({x.id for x in a}),3);self.assertEqual({x.body['owner_kind'] for x in a},{'class','method'});self.assertEqual({x.bindings[0].line_start for x in a},{2,3,4});self.assertTrue(all(x.bindings[0].line_start==x.bindings[0].line_end and x.bindings[0].hash_kind=='java_token_sha256' for x in a))
 def test_qualification_and_metadata_fail_closed(self):
  cases=['@interface ResponseStatus{} @ResponseStatus class A{}','import org.springframework.web.bind.annotation.*; @ResponseStatus class A{}','import static org.springframework.web.bind.annotation.ResponseStatus; @ResponseStatus class A{}','import org.springframework.web.bind.annotation.ResponseStatus; import decoy.ResponseStatus; @ResponseStatus class A{}','import org.springframework.web.bind.annotation.ResponseStatus; class ResponseStatus{} @ResponseStatus class A{}','import org.springframework.web.bind.annotation.ResponseStatus; @ResponseStatus(code=HttpStatus.NOT_FOUND) class A{}','import org.springframework.web.bind.annotation.ResponseStatus; @ResponseStatus(value=HttpStatus.OK, reason="ok") class A{}','import org.springframework.web.bind.annotation.ResponseStatus; class A{void x(@ResponseStatus String p){}}','import org.springframework.web.bind.annotation.ResponseStatus; class A{void x(){ @ResponseStatus class Local{} }}','import org.springframework.web.bind.annotation.ResponseStatus; class A{String s="@ResponseStatus";}']
  for s in cases:self.assertFalse(self.declarations(s),s)
 def test_stability_freshness_deletion_and_no_runtime_inference(self):
  p='import org.springframework.web.bind.annotation.ResponseStatus; class A{%s Object x(){return null;}}';a=self.declarations(p%'@ResponseStatus')[0];b=self.declarations(p%'@ResponseStatus( )')[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertFalse(self.declarations('class A{Object x(){return null;}}'));self.assertEqual(a.body['edge_kind'],'declares_response_status_presence');notes=' '.join(a.body['notes']).lower();self.assertIn('presence only',notes);self.assertIn('runtime',notes);self.assertIn('inheritance',notes);self.assertNotIn('http_status',a.body)
if __name__=='__main__':unittest.main()
