from __future__ import annotations

import json
import sqlite3
import subprocess
import tempfile
import unittest
from pathlib import Path

from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo
from tmf.mcp_server import McpService
from tmf.retrieve import retrieve_text
from tmf.store import Store


class InvertedIndexTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.repo = Path(self.tmp.name)
        subprocess.run(["git", "init", "-q", "-b", "master"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.email", "x@example.test"], cwd=self.repo, check=True)
        subprocess.run(["git", "config", "user.name", "x"], cwd=self.repo, check=True)
        (self.repo / "a.py").write_text("def alpha_value():\n    return 1\n", encoding="utf-8")
        (self.repo / "b.py").write_text("def alpha_value():\n    return 2\n\ndef beta_value():\n    return 3\n", encoding="utf-8")
        subprocess.run(["git", "add", "."], cwd=self.repo, check=True)
        subprocess.run(["git", "commit", "-qm", "base"], cwd=self.repo, check=True)
        store = Store(self.repo)
        git = GitRepo(self.repo)
        for path in ("a.py", "b.py"):
            for claim in derive_claims_for_path(git, path):
                store.put_claim(claim)
        store.rebuild_index()

    def tearDown(self):
        self.tmp.cleanup()

    def test_lexical_and_exact_preserve_ambiguity(self):
        result = retrieve_text(self.repo, "beta_value", 5)
        self.assertTrue(any(c.claim.body.get("qualname") == "beta_value" for c in result.claims))
        resolved, meta = McpService(self.repo)._resolve_claim_id(qualname="alpha_value", scopes={"function"})
        self.assertIsNone(resolved)
        self.assertEqual("ambiguous", meta["status"])
        resolved, meta = McpService(self.repo)._resolve_claim_id(qualname="alpha_value", path="a.py", scopes={"function"})
        self.assertIsNotNone(resolved)
        self.assertEqual("resolved", meta["status"])

    def test_upsert_delete_and_path_migration(self):
        store = Store(self.repo)
        ids = store.index.path_ids("a.py")
        self.assertTrue(ids)
        claim = store.get_claim(ids[0])
        self.assertIsNotNone(claim)
        store.delete_claim(claim.id)
        self.assertNotIn(claim.id, store.index.path_ids("a.py"))
        self.assertNotIn(claim.id, store.index.exact_ids("alpha_value", "a.py"))

    def test_corrupt_index_returns_gap_without_ordinary_query_rebuild(self):
        store = Store(self.repo)
        store.index.close()
        store.index.path.write_bytes(b"not sqlite")
        result = retrieve_text(self.repo, "beta_value", 5)
        self.assertEqual([], result.claims)
        self.assertEqual(["inverted_index_missing_no_full_store_fallback"], result.gaps)
        self.assertFalse(Store(self.repo).index.valid())

    def test_stale_index_id_is_ignored(self):
        store = Store(self.repo)
        db = store.index._connect()
        db.execute("INSERT OR IGNORE INTO claims(id, scope, search_text) VALUES('missing','function','beta_value')")
        rowid = db.execute("SELECT rowid FROM claims WHERE id='missing'").fetchone()[0]
        db.execute("INSERT INTO lexical(rowid, claim_id, search_text) VALUES(?,?,?)", (rowid, "missing", "beta_value"))
        result = retrieve_text(self.repo, "beta_value", 5)
        self.assertTrue(result.claims)
        self.assertNotIn("missing", [c.claim.id for c in result.claims])

    @staticmethod
    def _index_snapshot(store):
        db = store.index._connect()
        return {
            "claims": db.execute("SELECT id,scope,search_text FROM claims ORDER BY id").fetchall(),
            "exact": db.execute("SELECT value,claim_id,kind FROM exact_names ORDER BY 1,2,3").fetchall(),
            "paths": db.execute("SELECT value,claim_id FROM paths ORDER BY 1,2").fetchall(),
            "lexical": db.execute("SELECT claim_id,search_text FROM lexical ORDER BY claim_id").fetchall(),
            "edges": db.execute("SELECT relation_kind,endpoint,edge_id,endpoint_role FROM edge_endpoints ORDER BY 1,2,3,4").fetchall(),
        }

    def test_bulk_rebuild_equals_incremental_maintenance(self):
        source = Store(self.repo)
        claims = list(source.iter_claims())
        expected = self._index_snapshot(source)
        source.index.close()
        source.index.path.unlink()
        incremental = Store(self.repo)
        for claim in claims:
            incremental.index.upsert(claim)
        incremental.index._connect().execute(
            "INSERT OR REPLACE INTO metadata VALUES('state','complete')"
        )
        self.assertEqual(expected, self._index_snapshot(incremental))
        incremental.rebuild_index()
        self.assertEqual(expected, self._index_snapshot(incremental))

    def test_reconcile_delete_and_rebuild_remove_stale_ids(self):
        store = Store(self.repo)
        old_ids = set(store.index.path_ids("a.py"))
        self.assertTrue(old_ids)
        deleted = set(store.reconcile_path_claims("a.py", []))
        self.assertEqual(old_ids, deleted)
        self.assertEqual([], store.index.path_ids("a.py"))
        self.assertTrue(all(store.get_claim(claim_id) is None for claim_id in old_ids))
        store.rebuild_index()
        self.assertEqual([], store.index.path_ids("a.py"))
        indexed = {row[0] for row in store.index._connect().execute("SELECT id FROM claims")}
        authoritative = {claim.id for claim in store.iter_claims()}
        self.assertEqual(authoritative, indexed)

    def test_interrupted_rebuild_preserves_complete_live_index(self):
        store = Store(self.repo)
        before = self._index_snapshot(store)

        def interrupted():
            claims = iter(store.iter_claims())
            yield next(claims)
            raise RuntimeError("simulated interruption")

        with self.assertRaises(RuntimeError):
            store.index.rebuild(interrupted(), batch_size=1)
        self.assertTrue(store.index.valid())
        self.assertEqual(before, self._index_snapshot(store))
        rebuild = store.index.path.with_suffix(".sqlite3.rebuild")
        if rebuild.exists():
            db = sqlite3.connect(rebuild)
            self.assertNotEqual(
                ("complete",),
                db.execute("SELECT value FROM metadata WHERE key='state'").fetchone(),
            )
            db.close()


if __name__ == "__main__":
    unittest.main()
