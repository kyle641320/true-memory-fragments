from __future__ import annotations
import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo
def run(c,w):subprocess.run(c,cwd=w,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
class JavaTimeLimiterTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'A.java').write_text(s);run(['git','init'],r);run(['git','config','user.email','x@y'],r);run(['git','config','user.name','x'],r);run(['git','add','.'],r);run(['git','commit','-m','x'],r);return derive_claims_for_path(GitRepo(r),'A.java')
 def bh(self,s):return [x for x in self.claims(s) if x.id.startswith('claim_time_limiter_decl_')]
 def test_literal_overloads_and_anchor(self):
  s='''import io.github.resilience4j.timelimiter.annotation.TimeLimiter; class A { @TimeLimiter(name="billing", fallbackMethod="fallback") void x(){} @TimeLimiter(name="other") void x(String s){} }'''
  a=self.bh(s);self.assertEqual(len(a),2);self.assertEqual(len({x.body['owner_id'] for x in a}),2);self.assertEqual(next(x for x in a if x.body['name']=='billing').body['fallback_method'],'fallback');self.assertTrue(all(x.bindings[0].hash_kind=='java_token_sha256' for x in a))
 def test_fail_closed(self):
  cases=['@interface TimeLimiter{} class A{@TimeLimiter(name="x") void x(){}}','import io.github.resilience4j.timelimiter.annotation.*; class A{@TimeLimiter(name="x") void x(){}}','import io.github.resilience4j.timelimiter.annotation.TimeLimiter; import decoy.TimeLimiter; class A{@TimeLimiter(name="x") void x(){}}','import io.github.resilience4j.timelimiter.annotation.TimeLimiter; class A{static final String N="x";@TimeLimiter(name=N) void x(){}}','import io.github.resilience4j.timelimiter.annotation.TimeLimiter; class A{@TimeLimiter(name="${x}") void x(){}}','import io.github.resilience4j.timelimiter.annotation.TimeLimiter; class A{@TimeLimiter(fallbackMethod="f") void x(){}}','import static io.github.resilience4j.timelimiter.annotation.TimeLimiter; class A{@TimeLimiter(name="x") void x(){}}','import io.github.resilience4j.timelimiter.annotation.TimeLimiter; class A{@TimeLimiter(name="x", name="y") void x(){}}','import io.github.resilience4j.timelimiter.annotation.TimeLimiter; class A{@TimeLimiter("x") void x(){}}','import io.github.resilience4j.timelimiter.annotation.TimeLimiter; class A{@TimeLimiter(name="x", timeout="1") void x(){}}']
  for s in cases:
   c=self.claims(s);self.assertFalse([x for x in c if x.id.startswith('claim_time_limiter_decl_')]);self.assertTrue(next(x for x in c if x.scope=='file').body.get('java_time_limiter_unresolved'))
 def test_stable_mutation_delete_no_calls(self):
  p='import io.github.resilience4j.timelimiter.annotation.TimeLimiter; class A{@TimeLimiter(name="%s") void x(){}}';a=self.bh(p%'one')[0];b=self.bh(p%'two')[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertFalse(self.bh('class A{void x(){}}'));self.assertNotIn('calls',a.body)
if __name__=='__main__':unittest.main()
