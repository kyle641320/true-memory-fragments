from __future__ import annotations
import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo

def run(c,w):subprocess.run(c,cwd=w,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
class InitBinderTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'A.java').write_text(s);run(['git','init','-b','master'],r);run(['git','config','user.email','x@y'],r);run(['git','config','user.name','x'],r);run(['git','add','.'],r);run(['git','commit','-m','x'],r);return derive_claims_for_path(GitRepo(r),'A.java')
 def declarations(self,s):return [x for x in self.claims(s) if x.id.startswith('claim_init_binder_decl_')]
 def test_method_presence_overloads_and_anchors(self):
  s='import org.springframework.web.bind.annotation.InitBinder; class A{\n @InitBinder void bind(){}\n @InitBinder void bind(String x){}\n}'
  a=self.declarations(s);self.assertEqual(len(a),2);self.assertEqual(len({x.id for x in a}),2);self.assertTrue(all(x.body['owner_kind']=='method' and x.bindings[0].line_start in (2,3) for x in a))
 def test_fail_closed(self):
  cases=['@interface InitBinder{} class A{@InitBinder void x(){}}','import org.springframework.web.bind.annotation.*; class A{@InitBinder void x(){}}','import static org.springframework.web.bind.annotation.InitBinder; class A{@InitBinder void x(){}}','import org.springframework.web.bind.annotation.InitBinder; import decoy.InitBinder; class A{@InitBinder void x(){}}','import org.springframework.web.bind.annotation.InitBinder; class InitBinder{} class A{@InitBinder void x(){}}','import org.springframework.web.bind.annotation.InitBinder; class A{@InitBinder("x") void x(){}}','import org.springframework.web.bind.annotation.InitBinder; @InitBinder class A{}']
  for s in cases:self.assertFalse(self.declarations(s),s)
 def test_stability_freshness_deletion_and_no_runtime_semantics(self):
  p='import org.springframework.web.bind.annotation.InitBinder; class A{%s void x(){}}';a=self.declarations(p%'@InitBinder')[0];b=self.declarations(p%'@InitBinder( )')[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertFalse(self.declarations(p%'@InitBinder("x")'));self.assertFalse(self.declarations('class A{void x(){}}'));self.assertEqual(a.body['edge_kind'],'declares_init_binder_presence');self.assertIn('presence only',a.body['notes'][0].lower())
if __name__=='__main__':unittest.main()
