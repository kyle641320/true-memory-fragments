from __future__ import annotations
import subprocess, tempfile, unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo


def run(cmd,cwd): subprocess.run(cmd,cwd=cwd,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)

class JavaSchedulingTests(unittest.TestCase):
 def claims(self, source):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td); (root/'A.java').write_text(source); run(['git','init'],root); run(['git','config','user.email','x@y'],root); run(['git','config','user.name','x'],root); run(['git','add','A.java'],root); run(['git','commit','-m','x'],root)
   return derive_claims_for_path(GitRepo(root),'A.java')
 def scheduling(self, source): return [c for c in self.claims(source) if c.id.startswith('claim_scheduling_decl_')]
 def test_literals_are_opaque_exact_and_overload_safe(self):
  src='''import org.springframework.scheduling.annotation.Scheduled; import java.util.concurrent.TimeUnit; class A { @Scheduled(fixedRate=1_000L, initialDelay=5, timeUnit=TimeUnit.MILLISECONDS) void run(){} @Scheduled(cron="0 0 * * * *", zone="UTC") void run(String x){} }'''
  a=self.scheduling(src); b=self.scheduling(src); self.assertEqual(len(a),2); self.assertEqual([x.id for x in a],[x.id for x in b]); self.assertEqual(len({x.body['method_id'] for x in a}),2)
  rate=next(x for x in a if x.body['fixed_rate']); self.assertEqual(rate.body['fixed_rate'],'1_000L'); self.assertEqual(rate.body['time_unit'],'TimeUnit.MILLISECONDS'); self.assertEqual(rate.bindings[0].role,'scheduled_annotation'); self.assertEqual(rate.bindings[0].hash_kind,'java_token_sha256')
 def test_dynamic_conflicting_unsupported_and_decoy_fail_closed_with_reasons(self):
  cases=[
   '''@interface Scheduled { long fixedRate(); } class A { @Scheduled(fixedRate=1) void x(){} }''',
   '''import org.springframework.scheduling.annotation.Scheduled; class A { static final long N=1; @Scheduled(fixedRate=N) void x(){} }''',
   '''import org.springframework.scheduling.annotation.Scheduled; class A { @Scheduled(fixedRate=1, fixedDelay=2) void x(){} }''',
   '''import org.springframework.scheduling.annotation.Scheduled; class A { @Scheduled(fixedRateString="${rate}") void x(){} }''',
   '''import org.springframework.scheduling.annotation.Scheduled; class A { @Scheduled(cron="${cron}") void x(){} }''']
  for src in cases:
   claims=self.claims(src); self.assertFalse([c for c in claims if c.id.startswith('claim_scheduling_decl_')]); file_claim=next(c for c in claims if c.scope=='file'); self.assertTrue(file_claim.body.get('java_scheduling_unresolved'))
 def test_methods_only_not_composed_or_inherited(self):
  src='''import org.springframework.scheduling.annotation.Scheduled; @Scheduled(fixedRate=1) @interface Often {} class P { @Scheduled(fixedDelay=2) void inherited(){} } class A extends P { @Often void composed(){} }'''
  a=self.scheduling(src); self.assertEqual(len(a),1); self.assertEqual(a[0].body['method_qualname'],'P.inherited')
 def test_mutation_deletion_and_anchor_hash(self):
  base='import org.springframework.scheduling.annotation.Scheduled; class A { @Scheduled(fixedRate=1) void x(){} }'
  a=self.scheduling(base)[0]; b=self.scheduling(base.replace('fixedRate=1','fixedRate=2'))[0]; self.assertEqual(a.id,b.id); self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash); self.assertFalse(self.scheduling('class A { void x(){} }'))

if __name__=='__main__': unittest.main()
