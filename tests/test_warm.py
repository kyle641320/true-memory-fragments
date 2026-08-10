from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from tmf.git import GitRepo
from tmf.ids import stable_function_claim_id
from tmf.retrieve import reverse_callers
from tmf.store import Store
from tmf.warm import warm_repo, warm_is_complete, load_complete_reverse_index, _refresh_claim_cache_for_replaced_path
from tmf.schema import Binding, Claim

ROOT = Path(__file__).resolve().parents[1]


def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def init_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "master"], repo)
    run(["git", "config", "user.email", "tmf@example.com"], repo)
    run(["git", "config", "user.name", "tmf"], repo)
    for path, content in files.items():
        full = repo / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
    run(["git", "add", *files.keys()], repo)
    run(["git", "commit", "-m", "init"], repo)
    return repo


class WarmReverseIndexTests(unittest.TestCase):
    def test_refresh_claim_cache_only_touches_old_owner_binding_buckets(self):
        def claim(claim_id: str, owner: str, bindings: list[str]) -> Claim:
            return Claim(
                id=claim_id,
                scope="repo",
                kind="structure",
                claim="fixture",
                confidence=1.0,
                evidence="observed",
                provenance="test",
                endorsed_by=None,
                last_verified="now",
                model="mechanical",
                bindings=[Binding(path=path, file_blob="blob", fn_hash=None, commit="head", qualname="fixture") for path in bindings],
                body={"caller_path": owner, "edge_kind": "calls"} if len(bindings) > 1 else {},
            )

        old = claim("old", "a.py", ["a.py", "b.py"])
        unrelated = claim("other", "z.py", ["z.py"])
        replacement = claim("new", "a.py", ["a.py", "c.py"])
        untouched_bucket = [unrelated]
        cache = {"a.py": [old], "b.py": [old], "z.py": untouched_bucket}

        _refresh_claim_cache_for_replaced_path(cache, "a.py", [replacement])

        self.assertEqual([item.id for item in cache["a.py"]], ["new"])
        self.assertNotIn("b.py", cache)
        self.assertEqual([item.id for item in cache["c.py"]], ["new"])
        self.assertIs(cache["z.py"], untouched_bucket)

    def test_warm_makes_reverse_callers_complete_and_matches_lazy(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "from b import helper\n\ndef main():\n    return helper()\n",
                "b.py": "def helper():\n    return 1\n",
            })
            helper_id = stable_function_claim_id("b.py", "helper")
            before = reverse_callers(repo, helper_id)
            self.assertEqual(before["coverage"], "partial")
            self.assertEqual(before["callers"], [])

            result = warm_repo(repo)
            self.assertEqual(result["coverage"], "complete")
            indexed = reverse_callers(repo, helper_id)
            self.assertEqual(indexed["coverage"], "complete")
            self.assertEqual(indexed["callers"], [{
                "caller_id": stable_function_claim_id("a.py", "main"),
                "caller_path": "a.py",
                "callee_qualname": "helper",
                "resolution": "from_import_direct_top_level",
                "evidence": "observed",
                "anchor": {"path": "a.py", "line_start": 3, "line_end": 4, "qualname": "main"},
            }])

            # Deleting the index forces lazy scan, which must return the same fresh callers.
            (repo / ".tmf" / "reverse_callers.json").unlink()
            lazy = reverse_callers(repo, helper_id)
            self.assertEqual(lazy["coverage"], "partial")
            self.assertEqual(lazy["callers"], indexed["callers"])

    def test_warm_second_run_is_noop_and_file_change_is_incremental(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "from b import helper\n\ndef main():\n    return helper()\n",
                "b.py": "def helper():\n    return 1\n",
                "c.py": "def spare():\n    return 3\n",
            })
            first = warm_repo(repo)
            self.assertEqual(first["derived"], 3)
            second = warm_repo(repo)
            self.assertEqual(second["derived"], 0)
            self.assertEqual(second["skipped"], 3)

            (repo / "a.py").write_text("from b import helper\n\ndef main():\n    x = 1\n    return helper() + x\n", encoding="utf-8")
            third = warm_repo(repo)
            self.assertEqual(third["derived"], 1)
            self.assertEqual(third["skipped"], 2)
            helper_id = stable_function_claim_id("b.py", "helper")
            self.assertEqual(reverse_callers(repo, helper_id)["coverage"], "complete")

    def test_pristine_clean_warm_streams_without_reconciliation_or_claim_cache(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "def main():\n    return 1\n",
                "b.py": "def spare():\n    return 2\n",
            })

            with (
                mock.patch(
                    "tmf.warm._claims_by_path_from_claims",
                    side_effect=AssertionError("pristine clean warm must not retain a full claim cache"),
                ),
                mock.patch(
                    "tmf.warm._replace_path_claims",
                    side_effect=AssertionError("pristine clean warm is append-only"),
                ),
                mock.patch(
                    "tmf.warm._replace_path_claims_cached",
                    side_effect=AssertionError("pristine clean warm is append-only"),
                ),
            ):
                result = warm_repo(repo)

            self.assertEqual(result["coverage"], "complete")
            self.assertEqual(result["derived"], 2)
            self.assertIsNotNone(Store(repo).get_claim(stable_function_claim_id("a.py", "main")))
            self.assertIsNotNone(Store(repo).get_claim(stable_function_claim_id("b.py", "spare")))

    def test_incremental_content_edit_does_not_build_full_claim_path_index(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "def main():\n    return 1\n",
                "b.py": "def spare():\n    return 2\n",
            })
            warm_repo(repo)
            (repo / "a.py").write_text("def main():\n    return 3\n", encoding="utf-8")

            with mock.patch(
                "tmf.warm._claims_by_path_from_claims",
                side_effect=AssertionError("full claim index should not be built for a content edit"),
            ):
                result = warm_repo(repo)

            self.assertEqual(result["derived"], 1)
            self.assertEqual(result["skipped"], 1)
            self.assertEqual(result["coverage"], "complete")

    def test_complete_noop_rejects_missing_claim_and_repairs_store(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"a.py": "def main():\n    return 1\n"})
            first = warm_repo(repo)
            self.assertEqual(first["coverage"], "complete")
            manifest = json.loads((repo / ".tmf" / "warm_manifest.json").read_text(encoding="utf-8"))
            self.assertIn("claim_inventory", manifest)
            claim_path = Store(repo).claim_path(stable_function_claim_id("a.py", "main"))
            claim_path.unlink()

            repaired = warm_repo(repo)
            self.assertEqual(repaired["coverage"], "complete")
            self.assertEqual(repaired["derived"], 1)
            self.assertIsNotNone(Store(repo).get_claim(stable_function_claim_id("a.py", "main")))

    def test_reverse_callers_falls_back_to_partial_when_warm_index_is_stale(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "from b import helper\n\ndef main():\n    return helper()\n",
                "b.py": "def helper():\n    return 1\n",
            })
            warm_repo(repo)
            helper_id = stable_function_claim_id("b.py", "helper")
            self.assertEqual(reverse_callers(repo, helper_id)["coverage"], "complete")

            (repo / "a.py").write_text("def main():\n    return 0\n", encoding="utf-8")
            result = reverse_callers(repo, helper_id)
            self.assertEqual(result["coverage"], "partial")
            self.assertEqual(result["callers"], [])

    def test_warm_respects_tmfignore_directory_prefixes(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "def main():\n    return 1\n",
                ".ts-venv/lib/site-packages/noise.py": "def noisy():\n    return 2\n",
            })
            (repo / ".tmfignore").write_text(".ts-venv/\n", encoding="utf-8")
            result = warm_repo(repo)
            self.assertEqual(result["files"], 1)
            self.assertIsNotNone(Store(repo).get_claim(stable_function_claim_id("a.py", "main")))
            self.assertIsNone(Store(repo).get_claim(stable_function_claim_id(".ts-venv/lib/site-packages/noise.py", "noisy")))


    def test_warm_records_failed_file_and_continues_after_per_file_timeout(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "def main():\n    return 1\n",
                "slow.py": "def slow():\n    return 2\n",
                "z.py": "def last():\n    return 3\n",
            })
            script = """
import json
import os
import pathlib
from tmf import warm as warm_mod

original = warm_mod.derive_claims_for_path

def fake_derive(repo, relpath):
    if relpath == 'slow.py':
        raise warm_mod.WarmFileTimeoutError('derive timed out after 1s')
    return original(repo, relpath)

warm_mod.derive_claims_for_path = fake_derive
result = warm_mod.warm_repo(os.environ['REPO'])
manifest = json.loads((pathlib.Path(os.environ['REPO']) / '.tmf' / 'warm_manifest.json').read_text())
print(json.dumps({'result': result, 'manifest': manifest}, sort_keys=True))
"""
            payload = json.loads(subprocess.run(
                [sys.executable, "-c", script],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(ROOT), "REPO": str(repo)},
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            ).stdout)
            result = payload["result"]
            manifest = payload["manifest"]
            self.assertEqual(result["coverage"], "partial")
            self.assertIn("slow.py", result["failed_files"])
            self.assertEqual(manifest["coverage"], "partial")
            self.assertIn("slow.py", manifest["failed_files"])
            self.assertEqual(len(manifest["warmed_files"]), 3)
            self.assertIsNotNone(Store(repo).get_claim(stable_function_claim_id("a.py", "main")))
            self.assertIsNotNone(Store(repo).get_claim(stable_function_claim_id("z.py", "last")))
            self.assertFalse((repo / ".tmf" / "reverse_callers.json").exists())
            self.assertFalse(warm_is_complete(repo))
            self.assertIsNone(load_complete_reverse_index(repo))

    def test_failed_file_with_existing_claims_is_retried_not_skipped(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "def main():\n    return 1\n",
                "b.py": "def helper():\n    return 2\n",
            })
            first = warm_repo(repo)
            self.assertEqual(first["coverage"], "complete")
            self.assertIsNotNone(Store(repo).get_claim(stable_function_claim_id("a.py", "main")))
            (repo / "a.py").write_text("def main():\n    value = 1\n    return value\n", encoding="utf-8")

            script_fail = """
import json
import os
import pathlib
from tmf import warm as warm_mod

original = warm_mod.derive_claims_for_path

def fake_derive(repo, relpath):
    if relpath == 'a.py':
        raise warm_mod.WarmFileTimeoutError('derive timed out after 1s')
    return original(repo, relpath)

warm_mod.derive_claims_for_path = fake_derive
result = warm_mod.warm_repo(os.environ['REPO'])
manifest = json.loads((pathlib.Path(os.environ['REPO']) / '.tmf' / 'warm_manifest.json').read_text())
print(json.dumps({'result': result, 'manifest': manifest}, sort_keys=True))
"""
            failed = json.loads(subprocess.run(
                [sys.executable, "-c", script_fail],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(ROOT), "REPO": str(repo)},
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            ).stdout)
            self.assertEqual(failed["result"]["coverage"], "partial")
            self.assertIn("a.py", failed["manifest"]["failed_files"])

            recovered = warm_repo(repo)
            self.assertEqual(recovered["coverage"], "complete")
            self.assertEqual(recovered["failed_files"], {})
            self.assertGreaterEqual(recovered["derived"], 1)
            self.assertTrue(warm_is_complete(repo))

    def test_partial_warm_removes_stale_complete_reverse_index(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "from b import helper\n\ndef main():\n    return helper()\n",
                "b.py": "def helper():\n    return 1\n",
            })
            first = warm_repo(repo)
            self.assertEqual(first["coverage"], "complete")
            self.assertTrue((repo / ".tmf" / "reverse_callers.json").exists())

            script = """
import json
import os
from tmf import warm as warm_mod

original = warm_mod.derive_claims_for_path

def fake_derive(repo, relpath):
    if relpath == 'b.py':
        raise warm_mod.WarmFileTimeoutError('derive timed out after 1s')
    return original(repo, relpath)

warm_mod.derive_claims_for_path = fake_derive
print(json.dumps(warm_mod.warm_repo(os.environ['REPO']), sort_keys=True))
"""
            (repo / "b.py").write_text("def helper():\n    return 2\n", encoding="utf-8")
            payload = json.loads(subprocess.run(
                [sys.executable, "-c", script],
                cwd=ROOT,
                env={**os.environ, "PYTHONPATH": str(ROOT), "REPO": str(repo)},
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            ).stdout)
            self.assertEqual(payload["coverage"], "partial")
            self.assertFalse((repo / ".tmf" / "reverse_callers.json").exists())
            self.assertFalse(warm_is_complete(repo))
            self.assertIsNone(load_complete_reverse_index(repo))

    def test_warm_requires_exact_blob_map_for_complete_manifest(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "a.py": "def main():\n    return 1\n",
            })
            warm_repo(repo)
            manifest_path = repo / ".tmf" / "warm_manifest.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["coverage"] = "complete"
            manifest["warmed_files"]["a.py"] = "not-current-blob"
            manifest["failed_files"] = {}
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
            self.assertFalse(warm_is_complete(repo))
            result = warm_repo(repo)
            self.assertEqual(result["coverage"], "complete")
            repaired = json.loads(manifest_path.read_text())
            self.assertEqual(repaired["warmed_files"], {"a.py": GitRepo(repo).blob_sha("a.py")})

    def test_warm_cli_outputs_json(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"a.py": "def main():\n    return 1\n"})
            payload = json.loads(run([sys.executable, "-m", "tmf.cli", "warm", "--repo", str(repo)], ROOT).stdout)
            self.assertEqual(payload["coverage"], "complete")
            self.assertEqual(payload["derived"], 1)
            self.assertTrue((repo / ".tmf" / "warm_manifest.json").exists())
            self.assertTrue((repo / ".tmf" / "reverse_callers.json").exists())


if __name__ == "__main__":
    unittest.main()
