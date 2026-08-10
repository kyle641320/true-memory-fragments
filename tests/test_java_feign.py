from __future__ import annotations
import tempfile, unittest
from pathlib import Path
from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.store import Store
from tmf.warm import warm_repo
from tests.test_java_inherit import init_repo
IMPORTS='''import org.springframework.cloud.openfeign.FeignClient;\nimport org.springframework.web.bind.annotation.GetMapping;\nimport org.springframework.web.bind.annotation.RequestMapping;\nimport org.springframework.web.bind.annotation.RequestMethod;\n'''
GOOD='''package app;\n'''+IMPORTS+'''@FeignClient(name="catalog", url="https://catalog.invalid", path="/v1") interface CatalogClient { @GetMapping("/items") String item(); }\n'''
@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaFeignTests(unittest.TestCase):
 def repo(self, text=GOOD, extra=None):
  td=tempfile.TemporaryDirectory(); repo=init_repo(Path(td.name), {"src/app/CatalogClient.java":text, **(extra or {})}); warm_repo(repo); return td,repo
 def apis(self,r): return [c for c in Store(r).iter_claims() if c.scope=='api']
 def test_literal_client_dual_binding_metadata_and_stable_id(self):
  td,r=self.repo()
  with td:
   c=self.apis(r)[0]; self.assertTrue(c.id.startswith('claim_api_rel_')); self.assertEqual(c.body['service_name'],'catalog'); self.assertEqual(c.body['service_url'],'https://catalog.invalid'); self.assertEqual(c.body['route_path'],'/v1/items'); self.assertEqual([b.role for b in c.bindings],['route_declaration','handler']); self.assertTrue(check_freshness(GitRepo(r),c).fresh)
 def test_mutation_and_deletion_are_independent(self):
  td,r=self.repo()
  with td:
   c=self.apis(r)[0]; f=r/'src/app/CatalogClient.java'; f.write_text(GOOD.replace('catalog.invalid','changed.invalid')); stale=check_freshness(GitRepo(r),c).stale_bindings; self.assertTrue(any('route declaration missing' in x for x in stale),stale)
   f.write_text(GOOD.replace('String item();','String item(String id);')); stale=check_freshness(GitRepo(r),c).stale_bindings; self.assertTrue(any('handler_hash mismatch' in x for x in stale),stale)
   f.unlink(); warm_repo(r); self.assertIsNone(Store(r).get_claim(c.id))
 def test_fail_closed_adversarial_forms(self):
  bad=[GOOD.replace('name="catalog"','name="${service}"'), GOOD.replace('@GetMapping("/items")','@GetMapping(PATH)'), GOOD.replace('@GetMapping("/items")','@RequestMapping(path="/items", method={RequestMethod.GET,RequestMethod.POST})'), GOOD.replace('import org.springframework.cloud.openfeign.FeignClient;','import fake.FeignClient;'), GOOD.replace('@GetMapping("/items")','@MyGet("/items")')]
  for text in bad:
   td,r=self.repo(text)
   with td: self.assertEqual(self.apis(r),[])
 def test_overload_fails_closed(self):
  td,r=self.repo(GOOD.replace('String item();','String item(); String item(String id);'))
  with td: self.assertEqual(self.apis(r),[])
if __name__=='__main__': unittest.main()
