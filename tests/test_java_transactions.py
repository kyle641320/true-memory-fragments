from __future__ import annotations
import subprocess,tempfile,unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo

def run(cmd,cwd): subprocess.run(cmd,cwd=cwd,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
class JavaTransactionTests(unittest.TestCase):
 def claims(self,source):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td);(root/'A.java').write_text(source);run(['git','init'],root);run(['git','config','user.email','x@y'],root);run(['git','config','user.name','x'],root);run(['git','add','A.java'],root);run(['git','commit','-m','x'],root)
   return derive_claims_for_path(GitRepo(root),'A.java')
 def tx(self,source): return [c for c in self.claims(source) if c.id.startswith('claim_transaction_decl_')]
 def test_exact_literals_class_method_and_overloads(self):
  src='''import org.springframework.transaction.annotation.Transactional; import org.springframework.transaction.annotation.Propagation; import org.springframework.transaction.annotation.Isolation; @Transactional(readOnly=false, transactionManager="main") class A { @Transactional(propagation=Propagation.REQUIRES_NEW,isolation=Isolation.SERIALIZABLE,readOnly=true,timeout=1_000,rollbackFor={Exception.class,java.io.IOException.class},noRollbackFor=RuntimeException.class,rollbackForClassName={"a.B","c.D"},noRollbackForClassName="e.F") void x(){} @Transactional("other") void x(String s){} }'''
  a=self.tx(src);self.assertEqual(len(a),3);self.assertEqual(len({x.body['owner_id'] for x in a}),3)
  method=next(x for x in a if x.body['propagation']);self.assertEqual(method.body['timeout'],'1_000');self.assertEqual(method.body['rollback_for'],['Exception.class','java.io.IOException.class']);self.assertEqual(method.body['declaration_precedence'],'method_over_class_source_metadata');self.assertEqual(method.bindings[0].role,'transactional_annotation');self.assertEqual(method.bindings[0].hash_kind,'java_token_sha256')
 def test_decoys_dynamic_alias_conflict_composed_inherited_wildcard_static_and_malformed_fail_closed(self):
  cases=['''@interface Transactional{} class A{@Transactional void x(){}}''','''import org.springframework.transaction.annotation.*; class A{@Transactional void x(){}}''','''import static org.springframework.transaction.annotation.Transactional.*; class A{@Transactional void x(){}}''','''import org.springframework.transaction.annotation.Transactional; class A{static final int N=3; @Transactional(timeout=N) void x(){}}''','''import org.springframework.transaction.annotation.Transactional; class A{@Transactional(value="a",transactionManager="b") void x(){}}''','''import org.springframework.transaction.annotation.Transactional; @Transactional @interface Mine{} class A{@Mine void x(){}}''']
  for src in cases:
   claims=self.claims(src);self.assertFalse([c for c in claims if c.id.startswith('claim_transaction_decl_')]);self.assertTrue(next(c for c in claims if c.scope=='file').body.get('java_transaction_unresolved') or '@Mine' in src)
  inherited='''import org.springframework.transaction.annotation.Transactional; class P{@Transactional void x(){}} class A extends P{}''';self.assertEqual([x.body['owner_qualname'] for x in self.tx(inherited)],['P.x'])
 def test_stable_id_mutation_hash_deletion_and_no_runtime_edges(self):
  base='import org.springframework.transaction.annotation.Transactional; class A{@Transactional(timeout=1) void x(){}}';a=self.tx(base)[0];b=self.tx(base.replace('timeout=1','timeout=2'))[0];self.assertEqual(a.id,b.id);self.assertNotEqual(a.bindings[0].fn_hash,b.bindings[0].fn_hash);self.assertFalse(self.tx('class A{void x(){}}'));self.assertNotIn('transactions',a.body);self.assertEqual(a.body['values_handling'],'opaque-never-interpreted')
if __name__=='__main__':unittest.main()
