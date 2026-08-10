from __future__ import annotations
import subprocess, tempfile, unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo


def run(cmd,cwd): subprocess.run(cmd,cwd=cwd,check=True,stdout=subprocess.PIPE,stderr=subprocess.PIPE)

class JavaCacheTests(unittest.TestCase):
 def claims(self, source):
  with tempfile.TemporaryDirectory() as td:
   root=Path(td); (root/'A.java').write_text(source); run(['git','init','-b','master'],root); run(['git','config','user.email','x@y'],root); run(['git','config','user.name','x'],root); run(['git','add','A.java'],root); run(['git','commit','-m','x'],root)
   return derive_claims_for_path(GitRepo(root),'A.java')
 def cache(self,source): return [c for c in self.claims(source) if c.id.startswith('claim_cache_decl_')]
 def test_exact_import_literals_and_opaque_spel(self):
  src='''import org.springframework.cache.annotation.Cacheable;\nimport org.springframework.cache.annotation.CachePut;\nimport org.springframework.cache.annotation.CacheEvict;\nclass A { @Cacheable(cacheNames={"users","profiles"}, key="#id", condition="#id > 0", unless="#result == null") String get(String id){return id;} @CachePut("users") String put(){return "x";} @CacheEvict(value={"users"}) void evict(){} }'''
  a=self.cache(src); b=self.cache(src); self.assertEqual(len(a),3); self.assertEqual([x.id for x in a],[x.id for x in b]); self.assertEqual(a[0].bindings[0].role,'cache_annotation')
  cacheable=next(x for x in a if x.body['operation']=='Cacheable'); self.assertEqual(cacheable.body['cache_names'],['users','profiles']); self.assertEqual(cacheable.body['key'],'#id'); self.assertEqual(cacheable.body['spel_handling'],'opaque-never-evaluated')
 def test_fail_closed_decoy_dynamic_composed_inherited_and_unsupported(self):
  cases=['''@interface Cacheable { String value(); } class A { @Cacheable("x") void x(){} }''',
   '''import org.springframework.cache.annotation.Cacheable; class A { static final String N="x"; @Cacheable(N) void x(){} }''',
   '''import org.springframework.cache.annotation.Cacheable; @Cacheable("x") @interface Mine {} class A { @Mine void x(){} }''',
   '''import org.springframework.cache.annotation.Cacheable; class P { @Cacheable("x") void x(){} } class A extends P {}''',
   '''import org.springframework.cache.annotation.CacheEvict; class A { @CacheEvict(value="x", allEntries=true) void x(){} }''']
  self.assertEqual([len(self.cache(x)) for x in cases],[0,0,0,1,0])
 def test_mutation_and_deletion_change_or_remove_claim(self):
  base='import org.springframework.cache.annotation.Cacheable; class A { @Cacheable("x") void x(){} }'
  self.assertNotEqual(self.cache(base)[0].id,self.cache(base.replace('"x"','"y"'))[0].id); self.assertFalse(self.cache('class A { void x(){} }'))
 def test_overloads_have_distinct_stable_declarations(self):
  src='import org.springframework.cache.annotation.Cacheable; class A { @Cacheable("x") void x(){} @Cacheable("y") void x(String s){} }'
  a=self.cache(src); self.assertEqual(len(a),2); self.assertEqual(len({x.body['method_id'] for x in a}),2)
if __name__=='__main__': unittest.main()
