from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from bench.agent_ab.java_real_v2.store_lock import LOCK_SCHEMA, disposable_repository, store_inventory, verify_lock


def _store(root: Path, claim: dict | None = None) -> Path:
    store = root / ".tmf"
    (store / "claims").mkdir(parents=True)
    (store / "claims" / "b.json").write_text(json.dumps(claim or {"id": "b", "body": {"x": 1}}))
    (store / "claims" / "a.json").write_text('{"z":2,"id":"a"}\n')
    (store / "schema_version").write_text("tmf.schema.v1\n")
    (store / ".lock").write_text("runtime")
    (store / "local_identity.json").write_text(json.dumps({"machine_hash": "secret", "repo_salt": "secret"}))
    return store


class EvaluationStoreLockTests(unittest.TestCase):
    def test_inventory_is_stable_for_json_format_and_object_key_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = _store(root / "one", {"id": "b", "body": {"x": 1}, "trust": "local"})
            second = _store(root / "two", {"trust": "local", "body": {"x": 1}, "id": "b"})
            self.assertEqual(store_inventory(first), store_inventory(second))

    def test_inventory_detects_identity_and_trust_metadata_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(Path(tmp) / "repo")
            before = store_inventory(store)
            (store / "local_identity.json").write_text(json.dumps({"machine_hash": "changed", "repo_salt": "secret"}))
            after = store_inventory(store)
            self.assertNotEqual(before["digest"], after["digest"])

    def test_inventory_detects_semantic_drift_without_exposing_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(Path(tmp) / "repo")
            before = store_inventory(store)
            (store / "claims" / "a.json").write_text('{"id":"a","z":3}')
            after = store_inventory(store)
            self.assertNotEqual(before["digest"], after["digest"])
            self.assertNotIn(tmp, json.dumps(after))
            self.assertNotIn("secret", json.dumps(after))

    def test_inventory_rejects_symlinked_store_entries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = _store(root / "repo")
            outside = root / "outside.json"
            outside.write_text('{"id":"outside"}')
            (store / "claims" / "linked.json").symlink_to(outside)
            with self.assertRaisesRegex(ValueError, "unsupported symlink: claims/linked.json"):
                store_inventory(store)

    def test_verify_lock_fails_explicitly_on_store_or_commit_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = _store(Path(tmp) / "repo")
            inventory = store_inventory(store)
            lock = {"schema": LOCK_SCHEMA, "repositories": [{"id": "sample", "commit": "abc", **inventory}]}
            self.assertEqual(verify_lock("sample", "abc", store, lock), inventory)
            with self.assertRaisesRegex(ValueError, "commit drift"):
                verify_lock("sample", "def", store, lock)
            (store / "claims" / "a.json").write_text('{"id":"a","z":4}')
            with self.assertRaisesRegex(ValueError, "store drift"):
                verify_lock("sample", "abc", store, lock)

    def test_disposable_repository_isolates_read_through_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "source"
            store = _store(repo)
            source_before = store_inventory(store)
            with disposable_repository(repo) as copy:
                (copy / ".tmf" / "claims" / "new.json").write_text('{"id":"new"}')
                (copy / "source.txt").write_text("copy only")
            self.assertEqual(store_inventory(store), source_before)
            self.assertFalse((repo / "source.txt").exists())


if __name__ == "__main__":
    unittest.main()
