from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Iterable

from .schema import Claim

logger = logging.getLogger(__name__)

_state_root_override: Path | None = None


def configure_state_root(state_root: str | Path | None) -> None:
    global _state_root_override
    _state_root_override = Path(state_root).expanduser().resolve() if state_root is not None else None


def resolve_state_root(repo_root: str | Path, state_root: str | Path | None = None) -> Path:
    repo = Path(repo_root).resolve()
    if state_root is not None:
        return Path(state_root).expanduser().resolve()
    if _state_root_override is not None:
        return _state_root_override
    env_root = os.environ.get("TMF_STATE_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()
    return repo / ".tmf"


class Store:
    def __init__(self, repo_root: str | Path = ".", state_root: str | Path | None = None) -> None:
        self.repo_root = Path(repo_root).resolve()
        self.root = resolve_state_root(self.repo_root, state_root)
        self.claims_dir = self.root / "claims"
        # path -> set[claim_id]: in-memory index, lazily populated on first use
        self._path_index: dict[str, set[str]] | None = None

    def init(self) -> None:
        self.claims_dir.mkdir(parents=True, exist_ok=True)
        version_file = self.root / "schema_version"
        if not version_file.exists():
            version_file.write_text("tmf.schema.v1\n", encoding="utf-8")

    def claim_path(self, claim_id: str) -> Path:
        return self.claims_dir / f"{claim_id}.json"

    # ------------------------------------------------------------------
    # Path index helpers
    # ------------------------------------------------------------------

    def _ensure_index(self) -> dict[str, set[str]]:
        if self._path_index is None:
            self._path_index = {}
            for claim in self._iter_claims_raw():
                for binding in claim.bindings:
                    self._path_index.setdefault(binding.path, set()).add(claim.id)
        return self._path_index

    def _index_add(self, claim: Claim) -> None:
        if self._path_index is None:
            return
        for binding in claim.bindings:
            self._path_index.setdefault(binding.path, set()).add(claim.id)

    def _index_remove(self, claim_id: str) -> None:
        if self._path_index is None:
            return
        for ids in self._path_index.values():
            ids.discard(claim_id)

    # ------------------------------------------------------------------
    # Core CRUD
    # ------------------------------------------------------------------

    def put_claim(self, claim: Claim) -> None:
        self.init()
        path = self.claim_path(claim.id)
        path.write_text(json.dumps(claim.to_dict(), ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        self._index_add(claim)

    def delete_claim(self, claim_id: str) -> bool:
        path = self.claim_path(claim_id)
        if not path.exists():
            return False
        path.unlink()
        self._index_remove(claim_id)
        return True

    def get_claim(self, claim_id: str) -> Claim | None:
        path = self.claim_path(claim_id)
        if not path.exists():
            return None
        return Claim.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def _iter_claims_raw(self) -> Iterable[Claim]:
        self.init()
        for path in sorted(self.claims_dir.glob("*.json")):
            try:
                yield Claim.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except Exception:
                logger.warning("TMF: corrupt claim file skipped: %s", path)
                continue

    def iter_claims(self) -> Iterable[Claim]:
        yield from self._iter_claims_raw()

    def claims_for_path(self, relpath: str) -> list[Claim]:
        index = self._ensure_index()
        ids = index.get(relpath, set())
        claims = []
        for cid in list(ids):
            claim = self.get_claim(cid)
            if claim is None:
                ids.discard(cid)
                continue
            claims.append(claim)
        return claims

    # ------------------------------------------------------------------
    # Reconciliation
    # ------------------------------------------------------------------

    def reconcile_path_claims(self, relpath: str, current_claims: list[Claim]) -> list[str]:
        current_ids = {claim.id for claim in current_claims}
        deleted: list[str] = []
        for claim in list(self.claims_for_path(relpath)):
            if len(claim.bindings) != 1 or claim.bindings[0].path != relpath:
                continue
            if claim.id not in current_ids:
                if self.delete_claim(claim.id):
                    deleted.append(claim.id)
        return deleted

    def reconcile_edge_claims_for_caller_path(self, relpath: str, current_edge_claims: list[Claim]) -> list[str]:
        current_ids = {claim.id for claim in current_edge_claims}
        deleted: list[str] = []
        for claim in list(self.iter_claims()):
            if claim.scope != "cross-repo" and claim.body.get("edge_kind") not in {"calls", "reads", "writes"}:
                continue
            edge_kind = claim.body.get("edge_kind")
            owner_path = (
                claim.body.get("caller_path") if edge_kind == "calls"
                else claim.body.get("reader_path") if edge_kind == "reads"
                else claim.body.get("writer_path")
            )
            if owner_path != relpath:
                continue
            if claim.id not in current_ids:
                if self.delete_claim(claim.id):
                    deleted.append(claim.id)
        return deleted
