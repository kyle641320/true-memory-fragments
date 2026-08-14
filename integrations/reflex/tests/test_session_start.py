#!/usr/bin/env python3
"""SessionStart cognitive calibration tests."""

import importlib.util
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
CALIBRATION_SCRIPT = PROJECT_ROOT / "hooks" / "session_start.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("tmf_sessionstart_calibration", CALIBRATION_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


calibration = _load_module()


def write_manifest(repo: Path, state_root: Path, entries: list[dict], name: str = "manifest.json", skipped: list[dict] | None = None) -> Path:
    manifest_dir = state_root / "invalidation-manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    path = manifest_dir / name
    payload = {
        "schema_version": "tmf.invalidation_manifest.v1",
        "kind": "code_cognition_invalidation_manifest",
        "generated_at": "2026-06-26T00:00:00+00:00",
        "repo_root": str(repo),
        "old_rev": "old",
        "new_rev": "new",
        "changed_files": ["a.py"],
        "scanned_files": ["a.py"],
        "entries": entries,
        "skipped": skipped or [],
        "cache_updated": True,
        "summary": {},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


class SessionStartCalibrationTests(unittest.TestCase):
    def test_marks_only_changed_and_deleted_as_suspect(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            state_root = Path(td) / "state"
            repo.mkdir()
            write_manifest(repo, state_root, [
                {"status": "changed", "file": "a.py", "qualname": "f", "reason": "fn_hash_mismatch"},
                {"status": "deleted", "file": "a.py", "qualname": "old_f", "reason": "missing"},
                {"status": "added", "file": "a.py", "qualname": "new_f", "reason": "new"},
            ])

            result = calibration.consume_latest_manifest(repo, state_root=state_root, mark_consumed=True)

            self.assertEqual(result["reason"], "ok")
            self.assertEqual([entry["qualname"] for entry in result["suspect_entries"]], ["f", "old_f"])
            self.assertIn("a.py::f [changed]", result["injection"])
            self.assertIn("a.py::old_f [deleted]", result["injection"])
            self.assertNotIn("new_f", result["injection"])
            self.assertIn("仅预警，不重读，不 warm，不清理，不强制", result["injection"])

    def test_consumed_manifest_is_not_repeated(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            state_root = Path(td) / "state"
            repo.mkdir()
            write_manifest(repo, state_root, [
                {"status": "changed", "file": "a.py", "qualname": "f"},
            ])

            first = calibration.consume_latest_manifest(repo, state_root=state_root, mark_consumed=True)
            second = calibration.consume_latest_manifest(repo, state_root=state_root, mark_consumed=True)

            self.assertEqual(first["reason"], "ok")
            self.assertEqual(second["reason"], "no_unconsumed_manifest")
            state = json.loads((state_root / "sessionstart_calibration_consumed.json").read_text(encoding="utf-8"))
            self.assertEqual(len(state["consumed"]), 1)
            self.assertFalse((repo / ".tmf").exists())

    def test_no_consume_can_read_manifest_after_sessionstart_consumed_it(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            state_root = Path(td) / "state"
            repo.mkdir()
            write_manifest(repo, state_root, [
                {"status": "changed", "file": "a.py", "qualname": "f"},
            ])

            consumed = calibration.consume_latest_manifest(repo, state_root=state_root, mark_consumed=True)
            delivery = calibration.consume_latest_manifest(repo, state_root=state_root, mark_consumed=False)

            self.assertEqual(delivery["reason"], "ok")
            self.assertEqual(delivery["fingerprint"], consumed["fingerprint"])
            self.assertFalse(delivery["consumed"])
            state = json.loads((state_root / "sessionstart_calibration_consumed.json").read_text(encoding="utf-8"))
            self.assertEqual(len(state["consumed"]), 1)

    def test_fingerprint_matches_git_calibrator_semantic_contract(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            state_root = Path(td) / "state"
            repo.mkdir()
            manifest = write_manifest(repo, state_root, [
                {"status": "changed", "file": "a.py", "qualname": "f"},
            ])
            data = json.loads(manifest.read_text(encoding="utf-8"))
            expected_base = "old|new|" + json.dumps(data["entries"], sort_keys=True, ensure_ascii=False)
            expected = hashlib.sha256(expected_base.encode()).hexdigest()

            result = calibration.consume_latest_manifest(repo, state_root=state_root, mark_consumed=False)

            self.assertEqual(result["fingerprint"], expected)
            self.assertNotEqual(result["fingerprint"], hashlib.sha256(manifest.read_bytes()).hexdigest())

    def test_no_source_file_read_or_tmf_warm_required(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            state_root = Path(td) / "state"
            repo.mkdir()
            manifest = write_manifest(repo, state_root, [
                {"status": "changed", "file": "missing_a.py", "qualname": "f"},
            ])

            result = calibration.consume_latest_manifest(repo, state_root=state_root, manifest_paths=[manifest], mark_consumed=False)

            self.assertEqual(result["reason"], "ok")
            self.assertIn("missing_a.py::f", result["injection"])
            self.assertFalse((repo / "missing_a.py").exists(), "test fixture proves calibration did not need the source file")
            self.assertFalse((state_root / "sessionstart_calibration_consumed.json").exists())
            self.assertFalse((repo / ".tmf").exists())

    def test_explicit_manifest_paths_take_priority_over_repo_glob(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            state_root = Path(td) / "state"
            repo.mkdir()
            write_manifest(repo, state_root, [
                {"status": "changed", "file": "repo.py", "qualname": "from_repo_glob"},
            ], name="latest.json")
            state_manifest = state_root / "explicit.json"
            payload = {
                "schema_version": "tmf.invalidation_manifest.v1",
                "kind": "code_cognition_invalidation_manifest",
                "generated_at": "2026-01-01T00:00:00+00:00",
                "repo_root": str(repo),
                "old_rev": "old",
                "new_rev": "new",
                "entries": [
                    {"status": "changed", "file": "state.py", "qualname": "from_state_explicit"},
                ],
            }
            state_manifest.write_text(json.dumps(payload), encoding="utf-8")

            result = calibration.consume_latest_manifest(repo, state_root=state_root, manifest_paths=[state_manifest], mark_consumed=False)

            self.assertEqual(result["reason"], "ok")
            self.assertEqual(result["manifest_path"], str(state_manifest))
            self.assertEqual(result["suspect_entries"][0]["qualname"], "from_state_explicit")

    def test_manifest_without_suspect_entries_is_consumed_without_injection(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            state_root = Path(td) / "state"
            repo.mkdir()
            write_manifest(repo, state_root, [
                {"status": "added", "file": "a.py", "qualname": "new_f"},
            ])

            result = calibration.consume_latest_manifest(repo, state_root=state_root, mark_consumed=True)

            self.assertEqual(result["reason"], "no_changed_or_deleted_entries")
            self.assertEqual(result["injection"], "")
            self.assertTrue((state_root / "sessionstart_calibration_consumed.json").exists())
            self.assertFalse((repo / ".tmf").exists())

    def test_module_top_level_changed_renders_line_anchor_and_added_is_silent(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td) / "repo"
            state_root = Path(td) / "state"
            repo.mkdir()
            write_manifest(repo, state_root, [
                {
                    "status": "module_top_level_changed",
                    "file": "a.py",
                    "old_top_level_hash": "old",
                    "new_top_level_hash": "new",
                    "new_anchor": {"line_start": 10, "line_end": 18},
                    "module_top_level_contract": {
                        "schema_version": "tmf.module_top_level_contract.v2",
                        "region_id": "top_level_0001",
                        "old_anchor": {"start": 10, "end": 17},
                        "new_anchor": {"start": 10, "end": 18},
                    },
                },
                {
                    "status": "module_top_level_added",
                    "file": "a.py",
                    "new_top_level_hash": "new2",
                    "new_anchor": {"line_start": 30, "line_end": 31},
                    "module_top_level_contract": {
                        "schema_version": "tmf.module_top_level_contract.v2",
                        "region_id": "top_level_0002",
                        "old_anchor": None,
                        "new_anchor": {"start": 30, "end": 31},
                    },
                },
                {
                    "status": "module_top_level_changed",
                    "file": "legacy-without-contract.py",
                    "new_anchor": {"line_start": 40, "line_end": 41},
                },
            ])

            result = calibration.consume_latest_manifest(repo, state_root=state_root, mark_consumed=True)

            self.assertEqual(result["reason"], "ok")
            self.assertEqual(result["suspect_entries"][0]["status"], "module_top_level_changed")
            self.assertIn("模块顶层逻辑已变更：a.py 第10-18行", result["injection"])
            self.assertNotIn("第30-31行", result["injection"])
            self.assertNotIn("legacy-without-contract.py", result["injection"])
            skipped_text = calibration.build_warning_text({
                "repo_root": str(repo), "old_rev": "old", "new_rev": "new"
            }, [{
                "status": "skipped", "file": "slow.py", "qualname": "",
                "reason": "derive_timeout", "elapsed_ms": "5",
            }])
            self.assertIn("slow.py [derive_timeout]", skipped_text)
            self.assertIn("该文件认知未更新", skipped_text)


if __name__ == "__main__":
    unittest.main()
