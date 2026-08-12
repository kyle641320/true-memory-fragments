from __future__ import annotations

import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from bench.agent_ab.java_real_v2.store_lock import (
    LOCK_SCHEMA,
    create_store_archive,
    disposable_repository,
    reconstruct_store_archive,
    store_inventory,
    verify_lock,
    verify_store_archive,
)


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

    def test_inventory_rejects_symlinked_store_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = _store(root / "repo")
            linked_store = root / "linked-store"
            linked_store.symlink_to(store, target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "unsupported root symlink"):
                store_inventory(linked_store)

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

    def test_archive_is_deterministic_idempotent_and_reconstructs_exact_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = _store(root / "repo")
            archive_root = root / "archives"
            first = create_store_archive(store, archive_root)
            second = create_store_archive(store, archive_root)
            self.assertEqual(first, second)
            archive = archive_root / first["archive_id"]
            self.assertEqual(verify_store_archive(archive, first["archive_id"]), first)
            restored = root / "restored"
            reconstruct_store_archive(archive, restored, first["archive_id"])
            self.assertEqual(store_inventory(restored), store_inventory(store))
            for source in store.rglob("*"):
                if source.is_file() and source.name != ".lock":
                    self.assertEqual((restored / source.relative_to(store)).read_bytes(), source.read_bytes())
            self.assertFalse(os.stat(archive / "manifest.json").st_mode & stat.S_IWUSR)
            self.assertFalse(os.stat(archive).st_mode & stat.S_IWUSR)

    def test_archive_rejects_tampering_and_id_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = create_store_archive(_store(root / "repo"), root / "archives")
            archive = root / "archives" / result["archive_id"]
            with self.assertRaisesRegex(ValueError, "archive id mismatch"):
                verify_store_archive(archive, "0" * 64)
            manifest = json.loads((archive / "manifest.json").read_text())
            blob = archive / "blobs" / manifest["files"][0]["blob"]
            blob.chmod(0o644)
            blob.write_bytes(b"tampered")
            with self.assertRaisesRegex(ValueError, "archive blob mismatch"):
                reconstruct_store_archive(archive, root / "restored", result["archive_id"])

    def test_archive_rejects_unsafe_paths_symlinks_and_special_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = create_store_archive(_store(root / "repo"), root / "archives")
            archive = root / "archives" / result["archive_id"]
            manifest_path = archive / "manifest.json"
            original_manifest = json.loads(manifest_path.read_text())
            manifest_path.chmod(0o644)
            for unsafe_path in ("../escape", "claims/./claim.json", "claims//claim.json", "claims/claim.json/", "claims\\claim.json", "claims/\0claim.json"):
                manifest = json.loads(json.dumps(original_manifest))
                manifest["files"][0]["path"] = unsafe_path
                manifest_path.write_text(json.dumps(manifest, sort_keys=True, separators=(",", ":")))
                with self.subTest(path=unsafe_path), self.assertRaisesRegex(ValueError, "unsafe archive path"):
                    verify_store_archive(archive)

            symlink_store = _store(root / "symlink-repo")
            (symlink_store / "claims" / "link").symlink_to(root / "outside")
            with self.assertRaisesRegex(ValueError, "unsupported symlink"):
                create_store_archive(symlink_store, root / "other-archives")

            linked_store = root / "linked-store"
            linked_store.symlink_to(_store(root / "linked-repo"), target_is_directory=True)
            with self.assertRaisesRegex(ValueError, "unsupported root symlink"):
                create_store_archive(linked_store, root / "linked-archives")

            if hasattr(os, "mkfifo"):
                special_store = _store(root / "special-repo")
                os.mkfifo(special_store / "claims" / "pipe")
                with self.assertRaisesRegex(ValueError, "unsupported file type"):
                    create_store_archive(special_store, root / "special-archives")


if __name__ == "__main__":
    unittest.main()
