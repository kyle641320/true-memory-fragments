from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from tmf.derive import derive_claims_for_path
from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_contract_claim_id
from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.store import Store
from tests.test_java_inherit import init_repo


@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaContractWindow2Tests(unittest.TestCase):
    def test_java_semantic_contract_sanitizer_blocks_adversarial_slots(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cmd = root / "fake_java_contract_model.py"
            cmd.write_text(
                "import json\n"
                "print(json.dumps({'contract': {"
                "'purpose':'unsafe semantic purpose', "
                "'params':[{'name':'x','meaning':'real','confidence':0.99},{'name':'fake','meaning':'fake','confidence':0.99}], "
                "'returns': {'meaning':'returns a result object','confidence':0.99}, "
                "'raises':[{'exception':'RuntimeException','condition':'fake','confidence':0.99},{'exception':'IllegalArgumentException','condition':'bad','confidence':0.99}], "
                "'side_effects':[{'meaning':'pure function with no side effects','confidence':0.99}], "
                "'gotchas':[{'meaning':'watch x','confidence':0.99}], "
                "'confidence':0.99"
                "}}))\n",
                encoding="utf-8",
            )
            source = """class C {
  int state;
  void run(int x) throws IllegalArgumentException {
    int y = x;
    this.state = y;
    if (y < 0) { throw new IllegalArgumentException(); }
    return;
  }
}
"""
            repo = init_repo(root, {"C.java": source})
            old = os.environ.get("TMF_MODEL_COMMAND")
            os.environ["TMF_MODEL_COMMAND"] = f"python3 {cmd}"
            try:
                claims = derive_claims_for_path(GitRepo(repo), "C.java")
            finally:
                if old is None:
                    os.environ.pop("TMF_MODEL_COMMAND", None)
                else:
                    os.environ["TMF_MODEL_COMMAND"] = old
            contract = [c for c in claims if c.id == stable_contract_claim_id("C.java", "C.run")][0]
            self.assertEqual(contract.evidence, "inferred")
            self.assertEqual(contract.body["contract_version"], "contract.v2.semantic_sanitized")
            self.assertEqual([p["name"] for p in contract.body["slots"]["params"]], ["x"])
            self.assertEqual([r["exception"] for r in contract.body["slots"]["raises"]], ["IllegalArgumentException"])
            self.assertEqual(contract.body["slots"].get("side_effects"), [])
            self.assertNotIn("returns", contract.body["slots"])
            self.assertLessEqual(contract.confidence, 0.6)
            reasons = [c.get("reason") for c in contract.body["_contract_checks"]["checks"]]
            self.assertIn("param_not_in_signature", reasons)
            self.assertIn("exception_not_mechanically_observed", reasons)
            self.assertIn("claims_no_side_effects_but_mechanical_writes_exist", reasons)
            self.assertIn("claims_return_value_but_mechanical_return_has_no_value", reasons)

    def test_java_contract_stales_on_method_body_change_and_skips_trivial_methods(self):
        source = """class C {
  int tiny() { return 1; }
  int run(int x) {
    int y = x + 1;
    if (y > 0) { return y; }
    return 0;
  }
}
"""
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"C.java": source})
            store = Store(repo)
            for claim in derive_claims_for_path(GitRepo(repo), "C.java"):
                store.put_claim(claim)
            self.assertIsNone(store.get_claim(stable_contract_claim_id("C.java", "C.tiny")))
            contract = store.get_claim(stable_contract_claim_id("C.java", "C.run"))
            self.assertIsNotNone(contract)
            assert contract is not None
            self.assertEqual(contract.body["node_kind"], "method")
            self.assertTrue(check_freshness(GitRepo(repo), contract).fresh)
            (repo / "C.java").write_text(source.replace("int y = x + 1;", "int y = x + 2;"), encoding="utf-8")
            freshness = check_freshness(GitRepo(repo), contract)
            self.assertFalse(freshness.fresh)
            self.assertTrue(any("java_hash mismatch" in reason for reason in freshness.stale_bindings))
            self.assertFalse(any("java node missing" in reason for reason in freshness.stale_bindings))


if __name__ == "__main__":
    unittest.main()
