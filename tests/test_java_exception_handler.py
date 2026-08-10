from __future__ import annotations
import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo

def run(c,w):subprocess.run(c,cwd=w,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
class ExceptionHandlerTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'A.java').write_text(s);run(['git','init'],r);run(['git','config','user.email','x@y'],r);run(['git','config','user.name','x'],r);run(['git','add','.'],r);run(['git','commit','-m','x'],r);return derive_claims_for_path(GitRepo(r),'A.java')
 def declarations(self,s):return [x for x in self.claims(s) if x.id.startswith('claim_exception_handler_decl_')]
 def test_literals_overloads_anchor_and_metadata(self):
  s='''import org.springframework.web.bind.annotation.ExceptionHandler;\nclass A {\n @ExceptionHandler(IllegalArgumentException.class) void x() {}\n @ExceptionHandler({IllegalStateException.class, java.io.IOException.class}) void x(String id) {}\n}'''
  a=self.declarations(s);self.assertEqual(len(a),2);self.assertEqual({tuple(x.body['exception_types']) for x in a},{('IllegalArgumentException',),('IllegalStateException','java.io.IOException')});self.assertEqual(len({x.body['owner_id'] for x in a}),2);self.assertTrue(all(x.bindings[0].line_start in (3,4) and x.bindings[0].hash_kind=='java_token_sha256' for x in a))
 def test_value_attribute_and_empty_metadata(self):
  s='import org.springframework.web.bind.annotation.ExceptionHandler; class A{@ExceptionHandler(value={RuntimeException.class}) void x(){} @ExceptionHandler void y(){}}'
  a=self.declarations(s);self.assertEqual(len(a),2);self.assertEqual({tuple(x.body['exception_types']) for x in a},{('RuntimeException',),()})
 def test_fail_closed_imports_dynamic_conflict_local_decoy(self):
  cases=['@interface ExceptionHandler{} class A{@ExceptionHandler void x(){}}','import org.springframework.web.bind.annotation.*; class A{@ExceptionHandler void x(){}}','import static org.springframework.web.bind.annotation.ExceptionHandler.*; class A{@ExceptionHandler void x(){}}','import org.springframework.web.bind.annotation.ExceptionHandler; import decoy.ExceptionHandler; class A{@ExceptionHandler void x(){}}','import org.springframework.web.bind.annotation.ExceptionHandler; class A{static final Class<?> X=RuntimeException.class;@ExceptionHandler(X) void x(){}}','import org.springframework.web.bind.annotation.ExceptionHandler; class A{void y(){class ExceptionHandler{};} @ExceptionHandler void x(){}}']
  for s in cases:
   c=self.claims(s);self.assertFalse([x for x in c if x.id.startswith('claim_exception_handler_decl_')]);self.assertTrue(next(x for x in c if x.scope=='file').body.get('java_exception_handler_unresolved'))
 def test_stable_mutation_delete_and_no_runtime_semantics(self):
  p='import org.springframework.web.bind.annotation.ExceptionHandler; class A{@ExceptionHandler(%s.class) void x(){}}';a=self.declarations(p%'RuntimeException')[0];b=self.declarations(p%'Error')[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertFalse(self.declarations('class A{void x(){}}'));self.assertNotIn('catches',a.body);self.assertNotIn('response',a.body)
if __name__=='__main__':unittest.main()
