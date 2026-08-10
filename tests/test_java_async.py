from __future__ import annotations
import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo
def run(cmd,cwd): subprocess.run(cmd,cwd=cwd,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
class JavaAsyncTests(unittest.TestCase):
 def claims(self,source):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'A.java').write_text(source);run(['git','init','-b','master'],root);run(['git','config','user.email','x@y'],root);run(['git','config','user.name','x'],root);run(['git','add','A.java'],root);run(['git','commit','-m','x'],root);return derive_claims_for_path(GitRepo(root),'A.java')
 def asyncs(self,s): return [c for c in self.claims(s) if c.id.startswith('claim_async_decl_')]
 def test_direct_class_methods_literals_overloads(self):
  s='''import org.springframework.scheduling.annotation.Async; @Async("classPool") class A { @Async void x(){} @Async(value="fast") void x(String s){} @Async(executor="fast") void y(){} }'''
  a=self.asyncs(s);self.assertEqual(len(a),4);self.assertEqual(len({x.body['owner_id'] for x in a}),4);self.assertEqual({x.body['executor_qualifier'] for x in a},{'classPool','fast',None});m=next(x for x in a if x.body['owner_qualname']=='A.x' and x.body['executor_qualifier']=='fast');self.assertEqual(m.body['declaration_precedence'],'method_over_class_source_metadata');self.assertEqual(m.bindings[0].role,'async_annotation');self.assertEqual(m.bindings[0].hash_kind,'java_token_sha256')
 def test_adversarial_fail_closed(self):
  cases=['''@interface Async{} class A{@Async void x(){}}''','''import org.springframework.scheduling.annotation.*; class A{@Async void x(){}}''','''import static org.springframework.scheduling.annotation.Async.*; class A{@Async void x(){}}''','''import org.springframework.scheduling.annotation.Async; import decoy.Async; class A{@Async void x(){}}''','''import org.springframework.scheduling.annotation.Async; class A{static final String E="x"; @Async(E) void x(){}}''','''import org.springframework.scheduling.annotation.Async; class A{@Async("${pool}") void x(){}}''','''import org.springframework.scheduling.annotation.Async; class A{@Async(value="a",executor="b") void x(){}}''','''import org.springframework.scheduling.annotation.Async; @Async @interface Mine{} class A{@Mine void x(){}}''']
  for s in cases:
   cs=self.claims(s);self.assertFalse([c for c in cs if c.id.startswith('claim_async_decl_')]);self.assertTrue(next(c for c in cs if c.scope=='file').body.get('java_async_unresolved') or '@Mine' in s)
  inherited='''import org.springframework.scheduling.annotation.Async; class P{@Async void x(){}} class A extends P{}''';self.assertEqual([x.body['owner_qualname'] for x in self.asyncs(inherited)],['P.x'])
 def test_stability_mutation_deletion_no_runtime(self):
  base='import org.springframework.scheduling.annotation.Async; class A{@Async("one") void x(){}}';a=self.asyncs(base)[0];b=self.asyncs(base.replace('one','two'))[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertFalse(self.asyncs('class A{void x(){}}'));self.assertEqual(a.body['values_handling'],'opaque-never-resolved');self.assertNotIn('calls',a.body)
if __name__=='__main__':unittest.main()
