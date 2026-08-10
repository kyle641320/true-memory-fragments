from __future__ import annotations
import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo
def run(c,w):subprocess.run(c,cwd=w,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
class JavaRetryTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'A.java').write_text(s);run(['git','init'],r);run(['git','config','user.email','x@y'],r);run(['git','config','user.name','x'],r);run(['git','add','.'],r);run(['git','commit','-m','x'],r);return derive_claims_for_path(GitRepo(r),'A.java')
 def retry(self,s):return [x for x in self.claims(s) if x.id.startswith('claim_retry_decl_')]
 def test_literals_overloads_recover(self):
  s='''import org.springframework.retry.annotation.Retryable;
import org.springframework.retry.annotation.Recover;
class A { @Retryable(retryFor={java.io.IOException.class}, noRetryFor=IllegalArgumentException.class, maxAttempts=3, stateful=true, label="io", listeners={"a","b"}) void x(){} @Retryable void x(String s){} @Recover String recover(Exception e){return "";} }'''
  a=self.retry(s);self.assertEqual(len(a),3);self.assertEqual(len({x.body['owner_id'] for x in a}),3);r=next(x for x in a if x.body['annotation_kind']=='retryable' and x.body['metadata']['max_attempts']=='3');self.assertEqual(r.body['metadata']['retry_for'],['java.io.IOException.class']);self.assertEqual(r.bindings[0].hash_kind,'java_token_sha256')
 def test_fail_closed(self):
  cases=['@interface Retryable{} class A{@Retryable void x(){}}','import org.springframework.retry.annotation.*; class A{@Retryable void x(){}}','import org.springframework.retry.annotation.Retryable; import decoy.Retryable; class A{@Retryable void x(){}}','import org.springframework.retry.annotation.Retryable; class A{static final int N=3; @Retryable(maxAttempts=N) void x(){}}','import org.springframework.retry.annotation.Retryable; class A{@Retryable(value=Exception.class,retryFor=RuntimeException.class) void x(){}}','import org.springframework.retry.annotation.Retryable; class A{@Retryable(maxAttemptsExpression="${n}") void x(){}}','import org.springframework.retry.annotation.Retryable; @Retryable @interface Mine{} class A{@Mine void x(){}}']
  for s in cases:
   c=self.claims(s);self.assertFalse([x for x in c if x.id.startswith('claim_retry_decl_')]);self.assertTrue(next(x for x in c if x.scope=='file').body.get('java_retry_unresolved') or '@Mine' in s)
 def test_stable_mutation_delete_no_semantics(self):
  a=self.retry('import org.springframework.retry.annotation.Retryable; class A{@Retryable(maxAttempts=2) void x(){}}')[0];b=self.retry('import org.springframework.retry.annotation.Retryable; class A{@Retryable(maxAttempts=3) void x(){}}')[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertFalse(self.retry('class A{void x(){}}'));self.assertNotIn('calls',a.body)
if __name__=='__main__':unittest.main()
