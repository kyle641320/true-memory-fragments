from __future__ import annotations
import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo
def run(c,w):subprocess.run(c,cwd=w,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
class JavaCircuitBreakerTests(unittest.TestCase):
 def claims(self,s):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'A.java').write_text(s);run(['git','init','-b','master'],r);run(['git','config','user.email','x@y'],r);run(['git','config','user.name','x'],r);run(['git','add','.'],r);run(['git','commit','-m','x'],r);return derive_claims_for_path(GitRepo(r),'A.java')
 def cb(self,s):return [x for x in self.claims(s) if x.id.startswith('claim_circuit_breaker_decl_')]
 def test_literal_overloads_and_anchor(self):
  s='''import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker; class A { @CircuitBreaker(name="billing", fallbackMethod="fallback") void x(){} @CircuitBreaker(name="other") void x(String s){} }'''
  a=self.cb(s);self.assertEqual(len(a),2);self.assertEqual(len({x.body['owner_id'] for x in a}),2);self.assertEqual(next(x for x in a if x.body['name']=='billing').body['fallback_method'],'fallback');self.assertTrue(all(x.bindings[0].hash_kind=='java_token_sha256' for x in a))
 def test_fail_closed(self):
  cases=['@interface CircuitBreaker{} class A{@CircuitBreaker(name="x") void x(){}}','import io.github.resilience4j.circuitbreaker.annotation.*; class A{@CircuitBreaker(name="x") void x(){}}','import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker; import decoy.CircuitBreaker; class A{@CircuitBreaker(name="x") void x(){}}','import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker; class A{static final String N="x";@CircuitBreaker(name=N) void x(){}}','import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker; class A{@CircuitBreaker(name="${x}") void x(){}}','import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker; class A{@CircuitBreaker(fallbackMethod="f") void x(){}}']
  for s in cases:
   c=self.claims(s);self.assertFalse([x for x in c if x.id.startswith('claim_circuit_breaker_decl_')]);self.assertTrue(next(x for x in c if x.scope=='file').body.get('java_circuit_breaker_unresolved'))
 def test_stable_mutation_delete_no_calls(self):
  p='import io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker; class A{@CircuitBreaker(name="%s") void x(){}}';a=self.cb(p%'one')[0];b=self.cb(p%'two')[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertFalse(self.cb('class A{void x(){}}'));self.assertNotIn('calls',a.body)
if __name__=='__main__':unittest.main()
