"""Read authoritative locator JSON into a service-local, memory-only index.

No disk SQLite database (including WAL) is opened. Each protocol request checks
for an external JSON refresh. Corrupt records fail instead of disappearing.
"""
from __future__ import annotations
import copy
import json
import sqlite3
from pathlib import Path
from .index import InvertedIndex
from .schema import Claim, SUPPORTED_SCHEMA_VERSIONS

class LegacyLocatorClaim(Claim):
    """Only explicit locator mode admits legacy source-binding semantics."""
    def to_dict(self):
        return copy.deepcopy(self._legacy_record)

class MemoryIndex(InvertedIndex):
    def __init__(self, claims):
        self._db = sqlite3.connect(':memory:', isolation_level=None)
        try:
            self._db.execute('PRAGMA temp_store=MEMORY')
            self.create()
            self._db.execute('BEGIN')
            for claim in claims:
                self.upsert(claim)
            self._db.execute("INSERT OR REPLACE INTO metadata VALUES('state', 'complete')")
            self._db.execute('COMMIT')
            self._db.execute('PRAGMA query_only=ON')
        except BaseException:
            self.close()
            raise
    def _connect(self, *, rebuild=False):
        if self._db is None:
            raise RuntimeError('closed locator index')
        return self._db

class ReadOnlyStore:
    def __init__(self, repo_root, state_root=None):
        self.repo_root = Path(repo_root).resolve()
        self.root = Path(state_root).expanduser().resolve() if state_root is not None else self.repo_root / '.tmf'
        self.claims_dir = self.root / 'claims'
        self.require_initialized()
        before = self._signature()
        self._claims = {}
        for path in sorted(self.claims_dir.glob('*.json')):
            data = json.loads(path.read_text())
            legacy = 'derivation_versions' not in data.get('body', {})
            payload = dict(data)
            extension = payload.pop('module_top_level_contract', None)
            claim = Claim.from_dict(payload)
            if extension is not None and not legacy:
                raise ValueError('module_top_level_contract requires legacy locator semantics')
            if legacy:
                claim.__class__ = LegacyLocatorClaim
                claim._legacy_record = data
            if claim.id in self._claims:
                raise ValueError(f'duplicate claim id: {claim.id}')
            self._claims[claim.id] = claim
        if before != self._signature():
            raise ValueError("locator state changed while loading; retry after refresh completes")
        self.index = MemoryIndex(self._claims.values())
        self._snapshot_signature = before
    def require_initialized(self):
        marker = self.root / 'schema_version'
        if not self.claims_dir.is_dir() or not marker.is_file():
            raise ValueError(f'locator state is not initialized: {self.root}')
        if marker.read_text().strip() not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(f'unsupported locator state schema: {self.root}')
    def get_claim(self, claim_id):
        return self._claims.get(claim_id)
    def iter_claims(self):
        return iter(self._claims.values())
    def claims_for_path(self, path):
        return [self._claims[i] for i in (self.index.path_ids(path) or [])]

    def _signature(self):
        paths = [self.root / 'schema_version', *sorted(self.claims_dir.glob('*.json'))]
        return tuple((str(p), p.stat().st_ino, p.stat().st_size,
                      p.stat().st_mtime_ns, p.stat().st_ctime_ns) for p in paths)

    def refresh_if_changed(self):
        self.require_initialized()
        if self._signature() == self._snapshot_signature:
            return
        updated = ReadOnlyStore(self.repo_root, self.root)
        previous = self.index
        self._claims, self.index = updated._claims, updated.index
        self._snapshot_signature = updated._snapshot_signature
        previous.close()
