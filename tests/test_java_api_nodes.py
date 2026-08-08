from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_api_claim_id
from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.store import Store
from tmf.warm import warm_repo
from tests.test_java_inherit import init_repo


@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaSpringApiNodeTests(unittest.TestCase):
    def test_literal_class_and_method_mapping_builds_api_node(self):
        source = '''@RestController
@RequestMapping("/api")
class UserController {
  @GetMapping("/users")
  String list() { return "ok"; }
}
'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"UserController.java": source})
            warm_repo(repo)
            claim = Store(repo).get_claim(stable_api_claim_id("UserController.java", "GET", "/api/users", "UserController.list"))
            self.assertIsNotNone(claim)
            self.assertEqual(claim.scope, "api")
            self.assertEqual(claim.body["language"], "java")
            self.assertEqual(claim.body["method"], "GET")
            self.assertEqual(claim.body["route_path"], "/api/users")
            self.assertEqual(claim.body["http_methods"], ["GET"])
            self.assertEqual(claim.body["handler_qualname"], "UserController.list")
            self.assertEqual(claim.body["verification"]["method"], "java-ast-literal-route-check")
            self.assertTrue(claim.body["verification"]["supported"])
            self.assertEqual(claim.evidence, "observed")
            self.assertEqual(claim.confidence, 0.45)
            self.assertTrue(check_freshness(GitRepo(repo), claim).fresh)

    def test_class_and_method_literal_paths_are_not_downgraded(self):
        source = '''@RestController
@RequestMapping("/api")
class BankAccountResource {
  @PutMapping("/bank-accounts/{id}")
  String updateBankAccount() { return "ok"; }
}
'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"BankAccountResource.java": source})
            warm_repo(repo)
            claim = Store(repo).get_claim(stable_api_claim_id(
                "BankAccountResource.java", "PUT", "/api/bank-accounts/{id}", "BankAccountResource.updateBankAccount"
            ))
            self.assertIsNotNone(claim)
            assert claim is not None
            self.assertEqual(claim.evidence, "observed")
            self.assertEqual(claim.confidence, 0.45)
            self.assertTrue(claim.body["verification"]["supported"])

    def test_request_mapping_unspecified_method_and_body_change_stales(self):
        source = '''class C {
  @RequestMapping("/x")
  String h() { return "ok"; }
}
'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"C.java": source})
            warm_repo(repo)
            cid = stable_api_claim_id("C.java", "UNSPECIFIED", "/x", "C.h")
            claim = Store(repo).get_claim(cid)
            self.assertIsNotNone(claim)
            self.assertEqual(claim.body["http_methods"], ["unspecified"])
            (repo / "C.java").write_text(source.replace('"ok"', '"changed"'), encoding="utf-8")
            freshness = check_freshness(GitRepo(repo), claim)
            self.assertFalse(freshness.fresh)
            self.assertTrue(any("api_hash mismatch" in reason or "api missing" in reason for reason in freshness.stale_bindings))
            self.assertFalse(any("java node missing" in reason for reason in freshness.stale_bindings))

    def test_java_route_change_stales_as_api_hash_mismatch(self):
        source = '''class C {
  @GetMapping("/x")
  String h() { return "ok"; }
}
'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"C.java": source})
            warm_repo(repo)
            claim = Store(repo).get_claim(stable_api_claim_id("C.java", "GET", "/x", "C.h"))
            self.assertIsNotNone(claim)
            assert claim is not None
            (repo / "C.java").write_text(source.replace('"/x"', '"/y"'), encoding="utf-8")
            freshness = check_freshness(GitRepo(repo), claim)
            self.assertFalse(freshness.fresh)
            self.assertTrue(any("api missing" in reason for reason in freshness.stale_bindings))
            self.assertFalse(any("java node missing" in reason for reason in freshness.stale_bindings))

    def test_dynamic_path_records_unresolved_without_api_node(self):
        source = '''class C {
  static final String P = "/x";
  @GetMapping(P)
  String h() { return "ok"; }
}
'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"C.java": source})
            warm_repo(repo)
            api_claims = [c for c in Store(repo).iter_claims() if c.scope == "api"]
            self.assertEqual(api_claims, [])

    def test_non_route_annotation_does_not_create_api_node(self):
        source = '''class C {
  @Transactional
  String h() { return "ok"; }
}
'''
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"C.java": source})
            warm_repo(repo)
            self.assertEqual([c for c in Store(repo).iter_claims() if c.scope == "api"], [])


if __name__ == "__main__":
    unittest.main()
