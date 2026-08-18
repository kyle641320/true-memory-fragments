from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path
from typing import Iterable

from .schema import Claim

INDEX_SCHEMA_VERSION = "tmf.inverted_index.v2"
_TOKEN_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")

EDGE_ENDPOINT_FIELDS: dict[str, tuple[str, str]] = {
    "calls": ("caller_id", "callee_id"),
    "reads": ("reader_id", "declaration_id"),
    "writes": ("writer_id", "declaration_id"),
    "inherits": ("child_id", "parent_id"),
    "overrides": ("method_id", "overridden_id"),
    "uses_type": ("user_id", "type_id"),
    "reads_env": ("reader_id", "env_id"),
    "reads_config_key": ("reader_id", "config_id"),
    "injects": ("injector_id", "bean_id"),
    "publishes_to": ("source_id", "topic_id"),
    "subscribes_to": ("source_id", "topic_id"),
    "publishes_type": ("source_id", "type_id"),
    "listens_type": ("source_id", "type_id"),
}

SEMANTIC_CANDIDATE_HARD_LIMIT = 256


def claim_search_text(claim: Claim) -> str:
    body = claim.body or {}
    path = claim.bindings[0].path if claim.bindings else ""
    return " ".join((claim.claim, str(body.get("keywords", [])), path,
                     str(body.get("qualname", "")), str(body.get("name", ""))))


class InvertedIndex:
    """Rebuildable SQLite index. Claim JSON files remain authoritative."""

    def __init__(self, root: Path) -> None:
        self.path = root / "index" / "claims.sqlite3"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db: sqlite3.Connection | None = None

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

    def _connect(self, *, rebuild: bool = False) -> sqlite3.Connection:
        if self._db is None:
            self._db = sqlite3.connect(self.path, timeout=30, isolation_level=None)
            if rebuild:
                self._db.execute("PRAGMA journal_mode=OFF")
                self._db.execute("PRAGMA synchronous=OFF")
                self._db.execute("PRAGMA temp_store=MEMORY")
                self._db.execute("PRAGMA cache_size=-131072")
            else:
                self._db.execute("PRAGMA journal_mode=WAL")
                self._db.execute("PRAGMA synchronous=NORMAL")
        return self._db

    def valid(self) -> bool:
        try:
            db = self._connect()
            row = db.execute("SELECT value FROM metadata WHERE key='schema_version'").fetchone()
            ready = db.execute("SELECT value FROM metadata WHERE key='state'").fetchone()
            return bool(row and row[0] == INDEX_SCHEMA_VERSION and ready and ready[0] == "complete")
        except (sqlite3.Error, OSError):
            self.close()
            return False

    def create(self) -> None:
        db = self._connect()
        db.executescript("""
        CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS claims(id TEXT PRIMARY KEY, scope TEXT NOT NULL, search_text TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS exact_names(value TEXT NOT NULL, claim_id TEXT NOT NULL,
          kind TEXT NOT NULL, PRIMARY KEY(value, claim_id, kind));
        CREATE INDEX IF NOT EXISTS exact_names_value ON exact_names(value);
        CREATE TABLE IF NOT EXISTS paths(value TEXT NOT NULL, claim_id TEXT NOT NULL,
          PRIMARY KEY(value, claim_id));
        CREATE INDEX IF NOT EXISTS paths_value ON paths(value);
        CREATE TABLE IF NOT EXISTS edge_endpoints(
          relation_kind TEXT NOT NULL, endpoint TEXT NOT NULL, edge_id TEXT NOT NULL,
          endpoint_role TEXT NOT NULL,
          PRIMARY KEY(relation_kind, endpoint, edge_id, endpoint_role));
        CREATE INDEX IF NOT EXISTS edge_endpoints_lookup
          ON edge_endpoints(endpoint, relation_kind, edge_id);
        CREATE VIRTUAL TABLE IF NOT EXISTS lexical USING fts5(claim_id UNINDEXED, search_text,
          tokenize='trigram');
        """)
        db.execute("INSERT OR REPLACE INTO metadata VALUES('schema_version', ?)", (INDEX_SCHEMA_VERSION,))
        db.execute("INSERT OR IGNORE INTO metadata VALUES('state', 'building')")

    def _delete_rows(self, db: sqlite3.Connection, claim_id: str) -> None:
        db.execute("DELETE FROM exact_names WHERE claim_id=?", (claim_id,))
        db.execute("DELETE FROM paths WHERE claim_id=?", (claim_id,))
        db.execute("DELETE FROM edge_endpoints WHERE edge_id=?", (claim_id,))
        old = db.execute("SELECT rowid FROM claims WHERE id=?", (claim_id,)).fetchone()
        if old:
            db.execute("DELETE FROM lexical WHERE rowid=?", (old[0],))
        db.execute("DELETE FROM claims WHERE id=?", (claim_id,))

    @staticmethod
    def _index_rows(claim: Claim, rowid: int) -> tuple[
        tuple[int, str, str, str], list[tuple[str, str, str]],
        list[tuple[str, str]], tuple[int, str, str]
        , list[tuple[str, str, str, str]]
    ]:
        """Extract index rows once without mutating or serializing the claim."""
        text = claim_search_text(claim)
        body = claim.body or {}
        qualname = body.get("qualname")
        name = body.get("name")
        values: set[tuple[str, str]] = set()
        if isinstance(qualname, str) and qualname:
            values.add((qualname, "qualname"))
            values.add((qualname.rsplit(".", 1)[-1], "simple"))
        if isinstance(name, str) and name:
            values.add((name, "name"))
        exact = [(value, claim.id, kind) for value, kind in sorted(values)]
        paths = [(binding.path, claim.id) for binding in claim.bindings]
        relation_kind = body.get("edge_kind")
        edge_rows: list[tuple[str, str, str, str]] = []
        fields = EDGE_ENDPOINT_FIELDS.get(str(relation_kind))
        if fields is not None:
            for field in fields:
                endpoint = body.get(field)
                if isinstance(endpoint, str) and endpoint:
                    edge_rows.append((str(relation_kind), endpoint, claim.id, field))
        return ((rowid, claim.id, claim.scope, text), exact, paths,
                (rowid, claim.id, text), edge_rows)

    def upsert(self, claim: Claim) -> None:
        db = self._connect()
        try:
            db.execute("SELECT 1 FROM claims LIMIT 1")
        except sqlite3.Error:
            self.create()
        self._delete_rows(db, claim.id)
        rowid = db.execute("SELECT COALESCE(MAX(rowid), 0) + 1 FROM claims").fetchone()[0]
        claim_row, exact_rows, path_rows, lexical_row, edge_rows = self._index_rows(claim, rowid)
        db.execute("INSERT INTO claims(rowid, id, scope, search_text) VALUES(?,?,?,?)", claim_row)
        db.executemany("INSERT OR IGNORE INTO exact_names(value, claim_id, kind) VALUES(?,?,?)", exact_rows)
        db.executemany("INSERT OR IGNORE INTO paths(value, claim_id) VALUES(?,?)", path_rows)
        db.execute("INSERT INTO lexical(rowid, claim_id, search_text) VALUES(?,?,?)", lexical_row)
        db.executemany(
            "INSERT OR IGNORE INTO edge_endpoints(relation_kind,endpoint,edge_id,endpoint_role) VALUES(?,?,?,?)",
            edge_rows,
        )
        db.execute("INSERT OR REPLACE INTO metadata VALUES('state', 'complete')")

    def delete(self, claim_id: str) -> None:
        if not self.valid():
            return
        self._delete_rows(self._connect(), claim_id)

    def rebuild(self, claims: Iterable[Claim], *, batch_size: int = 5000) -> int:
        """Build a complete replacement in bounded batches and one transaction."""
        self.close()
        tmp = self.path.with_suffix(".sqlite3.rebuild")
        for suffix in ("", "-journal", "-wal", "-shm"):
            Path(str(tmp) + suffix).unlink(missing_ok=True)
        target = InvertedIndex(self.path.parent.parent)
        target.path = tmp
        db = target._connect(rebuild=True)
        target.create()
        db.execute("BEGIN IMMEDIATE")
        count = 0
        claim_rows: list[tuple[int, str, str, str]] = []
        exact_rows: list[tuple[str, str, str]] = []
        path_rows: list[tuple[str, str]] = []
        lexical_rows: list[tuple[int, str, str]] = []
        edge_rows: list[tuple[str, str, str, str]] = []

        def flush() -> None:
            if not claim_rows:
                return
            db.executemany("INSERT INTO claims(rowid,id,scope,search_text) VALUES(?,?,?,?)", claim_rows)
            db.executemany("INSERT OR IGNORE INTO exact_names(value,claim_id,kind) VALUES(?,?,?)", exact_rows)
            db.executemany("INSERT OR IGNORE INTO paths(value,claim_id) VALUES(?,?)", path_rows)
            db.executemany("INSERT INTO lexical(rowid,claim_id,search_text) VALUES(?,?,?)", lexical_rows)
            db.executemany(
                "INSERT OR IGNORE INTO edge_endpoints(relation_kind,endpoint,edge_id,endpoint_role) VALUES(?,?,?,?)",
                edge_rows,
            )
            claim_rows.clear(); exact_rows.clear(); path_rows.clear(); lexical_rows.clear(); edge_rows.clear()

        try:
            for claim in claims:
                count += 1
                claim_row, exact, paths, lexical, endpoints = self._index_rows(claim, count)
                claim_rows.append(claim_row)
                exact_rows.extend(exact)
                path_rows.extend(paths)
                lexical_rows.append(lexical)
                edge_rows.extend(endpoints)
                if len(claim_rows) >= batch_size:
                    flush()
            flush()
            db.execute("INSERT OR REPLACE INTO metadata VALUES('claim_count', ?)", (str(count),))
            db.execute("INSERT OR REPLACE INTO metadata VALUES('state', 'complete')")
            db.execute("COMMIT")
        except Exception:
            db.execute("ROLLBACK")
            target.close()
            raise
        target.close()
        tmp.replace(self.path)
        self.close()
        return count

    def lexical_ids(self, terms: set[str], limit: int = 2000) -> list[str] | None:
        if not self.valid():
            return None
        usable = sorted({t.lower() for t in terms if len(t) >= 3})
        if not usable:
            return []
        # Trigram FTS provides the substring semantics used by lexical_score.
        query = " OR ".join('"' + t.replace('"', '""') + '"' for t in usable)
        try:
            return [r[0] for r in self._connect().execute(
                "SELECT claim_id FROM lexical WHERE lexical MATCH ? ORDER BY rank LIMIT ?", (query, limit))]
        except sqlite3.Error:
            return None

    def exact_ids(self, value: str, path: str | None = None) -> list[str] | None:
        if not self.valid():
            return None
        if path is None:
            rows = self._connect().execute(
                "SELECT DISTINCT claim_id FROM exact_names WHERE value=? ORDER BY claim_id", (value,))
        else:
            rows = self._connect().execute(
                "SELECT DISTINCT e.claim_id FROM exact_names e JOIN paths p ON p.claim_id=e.claim_id "
                "WHERE e.value=? AND p.value=? ORDER BY e.claim_id", (value, path))
        return [r[0] for r in rows]

    def path_ids(self, path: str) -> list[str] | None:
        if not self.valid():
            return None
        return [r[0] for r in self._connect().execute(
            "SELECT claim_id FROM paths WHERE value=? ORDER BY claim_id", (path,))]

    def edge_ids(self, endpoint: str, relation_kinds: set[str], limit: int) -> list[str] | None:
        """Return indexed edge ids for one endpoint without touching claim storage."""
        if not self.valid():
            return None
        kinds = sorted(relation_kinds)
        if not kinds or limit <= 0:
            return []
        placeholders = ",".join("?" for _ in kinds)
        rows = self._connect().execute(
            f"SELECT DISTINCT edge_id FROM edge_endpoints WHERE endpoint=? "
            f"AND relation_kind IN ({placeholders}) ORDER BY edge_id LIMIT ?",
            (endpoint, *kinds, limit),
        )
        return [row[0] for row in rows]

    def candidate_ids(self, limit: int) -> tuple[list[str], bool] | None:
        """Return a deterministic bounded candidate window from the index.

        The boolean reports whether additional indexed claims exist.  This is
        intentionally not a semantic corpus scan: configured routers and
        embedders must operate within an explicit candidate budget.
        """
        if not self.valid():
            return None
        bounded = max(0, min(int(limit), SEMANTIC_CANDIDATE_HARD_LIMIT))
        rows = list(self._connect().execute(
            "SELECT id FROM claims ORDER BY rowid LIMIT ?", (bounded + 1,)
        ))
        return [row[0] for row in rows[:bounded]], len(rows) > bounded

    def status_snapshot(self, freshness_sample_limit: int = 20) -> dict[str, object] | None:
        """Read bounded status metadata from the rebuildable index only."""
        if not self.valid():
            return None
        db = self._connect()
        claim_count = int(db.execute("SELECT COUNT(*) FROM claims").fetchone()[0])
        edge_counts = {
            str(kind): int(count)
            for kind, count in db.execute(
                "SELECT relation_kind, COUNT(DISTINCT edge_id) "
                "FROM edge_endpoints GROUP BY relation_kind ORDER BY relation_kind"
            )
        }
        sample_limit = max(0, min(int(freshness_sample_limit), 20))
        sample_ids = [
            row[0] for row in db.execute(
                "SELECT id FROM claims ORDER BY id LIMIT ?", (sample_limit,)
            )
        ]
        return {
            "claims": claim_count,
            "edge_counts": edge_counts,
            "freshness_sample_ids": sample_ids,
            "index_schema_version": INDEX_SCHEMA_VERSION,
        }
