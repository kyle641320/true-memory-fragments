from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from tmf.contracts import sanitize_contract_candidate


class ContractSanitizerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.interface = {
            "params": [{"name": "x"}, {"name": "y"}],
            "raises": ["ValueError"],
            "return": {"shape": "none", "has_value": False},
            "side_effects": {"writes": ["GLOBAL"]},
        }

    def test_prunes_fabricated_raises(self) -> None:
        out = sanitize_contract_candidate({"raises": [{"exception": "RuntimeError", "condition": "bad"}, {"exception": "ValueError", "condition": "x bad"}], "confidence": 0.99}, self.interface)
        self.assertEqual([r["exception"] for r in out["slots"]["raises"]], ["ValueError"])
        self.assertTrue(any(c["reason"] == "exception_not_mechanically_observed" for c in out["_contract_checks"]["checks"]))

    def test_rejects_false_no_side_effect_claim_when_writes_exist(self) -> None:
        out = sanitize_contract_candidate({"side_effects": [{"meaning": "pure function with no side effects", "confidence": 0.9}]}, self.interface, graph={"writes": [{"target_id": "GLOBAL"}]})
        self.assertEqual(out["slots"]["side_effects"], [])
        self.assertTrue(any(c["reason"] == "claims_no_side_effects_but_mechanical_writes_exist" for c in out["_contract_checks"]["checks"]))

    def test_prunes_param_mismatch_and_caps_confidence(self) -> None:
        out = sanitize_contract_candidate({"params": [{"name": "x", "meaning": "input", "confidence": 0.99}, {"name": "z", "meaning": "fake", "confidence": 0.99}], "confidence": 0.99}, self.interface)
        self.assertEqual([p["name"] for p in out["slots"]["params"]], ["x"])
        self.assertLessEqual(out["slots"]["params"][0]["confidence"], 0.6)
        self.assertTrue(any(c["reason"] == "param_not_in_signature" for c in out["_contract_checks"]["checks"]))

    def test_rejects_return_value_when_no_value_return(self) -> None:
        out = sanitize_contract_candidate({"returns": {"meaning": "returns a result dict", "confidence": 0.5}}, self.interface)
        self.assertNotIn("returns", out["slots"])
        self.assertTrue(any(c["reason"] == "claims_return_value_but_mechanical_return_has_no_value" for c in out["_contract_checks"]["checks"]))


class ContractModelPathTests(unittest.TestCase):
    def test_model_contract_path_is_sanitized_before_claim_storage(self) -> None:
        from tmf.derive import derive_claims_for_path
        from tmf.git import GitRepo
        from tmf.ids import stable_contract_claim_id

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            cmd = root / "fake_contract_model.py"
            cmd.write_text(
                "import json\n"
                "print(json.dumps({'contract': {"
                "'purpose': 'adds safe business meaning', "
                "'params': [{'name':'x','meaning':'real input','confidence':0.99},{'name':'fake','meaning':'fake','confidence':0.99}], "
                "'returns': {'meaning':'returns a result dict','confidence':0.99}, "
                "'raises': [{'exception':'RuntimeError','condition':'fake','confidence':0.99},{'exception':'ValueError','condition':'negative','confidence':0.99}], "
                "'side_effects': [{'meaning':'pure function with no side effects','confidence':0.99}], "
                "'gotchas': [{'meaning':'watch input','confidence':0.99}], "
                "'confidence': 0.99"
                "}}))\n",
                encoding="utf-8",
            )
            (root / "m.py").write_text('''
GLOBAL = 0

def f(x):
    global GLOBAL
    GLOBAL = x
    if x < 0:
        raise ValueError("bad")
''', encoding="utf-8")
            old = os.environ.get("TMF_MODEL_COMMAND")
            os.environ["TMF_MODEL_COMMAND"] = f"python3 {cmd}"
            try:
                claims = derive_claims_for_path(GitRepo(root), "m.py")
            finally:
                if old is None:
                    os.environ.pop("TMF_MODEL_COMMAND", None)
                else:
                    os.environ["TMF_MODEL_COMMAND"] = old
            contract = [c for c in claims if c.id == stable_contract_claim_id("m.py", "f")][0]
            self.assertEqual(contract.evidence, "inferred")
            self.assertEqual(contract.body["contract_version"], "contract.v2.semantic_sanitized")
            self.assertEqual([p["name"] for p in contract.body["slots"]["params"]], ["x"])
            self.assertEqual([r["exception"] for r in contract.body["slots"]["raises"]], ["ValueError"])
            self.assertEqual(contract.body["slots"].get("side_effects"), [])
            self.assertLessEqual(contract.confidence, 0.6)
            reasons = [c.get("reason") for c in contract.body["_contract_checks"]["checks"]]
            self.assertIn("param_not_in_signature", reasons)
            self.assertIn("exception_not_mechanically_observed", reasons)
            self.assertIn("claims_no_side_effects_but_mechanical_writes_exist", reasons)


if __name__ == "__main__":
    unittest.main()
