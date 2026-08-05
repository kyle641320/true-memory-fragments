import json
import tempfile
import unittest
from pathlib import Path

from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo
from tmf.schema import (
    Claim,
    MODULE_TOP_LEVEL_CONTRACT_SCHEMA_VERSION,
    MODULE_TOP_LEVEL_STATUSES,
    module_top_level_invalidation_status,
)


class ModuleTopLevelContractTests(unittest.TestCase):
    def test_contract_is_explicit_typed_and_matches_legacy_body_values(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "sample.py").write_text("import os\nVALUE = 1\n\ndef f():\n    return VALUE\n", encoding="utf-8")
            import subprocess
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            subprocess.run(["git", "add", "sample.py"], cwd=root, check=True)
            subprocess.run(
                ["git", "-c", "user.name=TMF", "-c", "user.email=tmf@example.invalid", "commit", "-qm", "fixture"],
                cwd=root,
                check=True,
            )

            claims = derive_claims_for_path(GitRepo(root), "sample.py")
            claim = next(item for item in claims if item.scope == "module_top_level")
            contract = claim.module_top_level_contract

            self.assertIsNotNone(contract)
            self.assertEqual(contract.schema_version, MODULE_TOP_LEVEL_CONTRACT_SCHEMA_VERSION)
            self.assertEqual(contract.region_id, claim.body["region_id"])
            self.assertEqual(contract.region_id, claim.bindings[0].qualname)
            legacy_anchor = claim.body["anchors"][0]
            self.assertEqual(
                (contract.anchor.start, contract.anchor.end),
                (legacy_anchor["line_start"], legacy_anchor["line_end"]),
            )

            encoded = json.loads(json.dumps(claim.to_dict()))
            restored = Claim.from_dict(encoded)
            self.assertEqual(restored.to_dict(), claim.to_dict())

    def test_status_contract_is_closed_and_parallel_to_function_statuses(self):
        self.assertEqual(
            MODULE_TOP_LEVEL_STATUSES,
            ("module_top_level_changed", "module_top_level_added", "module_top_level_removed"),
        )
        self.assertEqual(module_top_level_invalidation_status(old_present=True, new_present=True), "module_top_level_changed")
        self.assertEqual(module_top_level_invalidation_status(old_present=False, new_present=True), "module_top_level_added")
        self.assertEqual(module_top_level_invalidation_status(old_present=True, new_present=False), "module_top_level_removed")
        self.assertIsNone(module_top_level_invalidation_status(old_present=True, new_present=True, hashes_equal=True))


if __name__ == "__main__":
    unittest.main()
