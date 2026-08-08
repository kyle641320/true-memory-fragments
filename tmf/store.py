from __future__ import annotations

import contextlib
import fcntl
import hashlib
import json
import os
import socket
import uuid
from pathlib import Path
from typing import Any, Iterable

from .schema import Claim

IDENTITY_FILE = "local_identity.json"
FOREIGN_MARKER = "foreign_store.json"


def _machine_hash() -> str:
    raw = "|".join([socket.gethostname(), str(os.getuid())])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _read_json(path: Path) -> Any | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json_atomic(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)


class Store:
    def __init__(self, repo_root: str | Path = ".") -> None:
        self.repo_root = Path(repo_root).resolve()
        self.root = self.repo_root / ".tmf"
        self.claims_dir = self.root / "claims"
        self._initialized = False
        self._foreign_checked = False

    def _identity_path(self) -> Path:
        return self.root / IDENTITY_FILE

    def _foreign_marker_path(self) -> Path:
        return self.root / FOREIGN_MARKER

    def _has_existing_claim_files(self) -> bool:
        return self.claims_dir.exists() and any(self.claims_dir.glob("*.json"))

    def _identity_matches_this_machine(self) -> bool:
        data = _read_json(self._identity_path())
        return isinstance(data, dict) and data.get("machine_hash") == _machine_hash() and isinstance(data.get("repo_salt"), str)

    def _ensure_identity(self) -> None:
        identity = self._identity_path()
        if identity.exists():
            return
        _write_json_atomic(identity, {
            "format": "tmf.local_identity.v1",
            "machine_hash": _machine_hash(),
            "repo_salt": uuid.uuid4().hex,
        })

    def _mark_foreign_if_needed(self) -> None:
        # If a repository arrives with pre-existing claim files whose local
        # identity is missing or from another machine, treat the cache as data
        # from outside this agent.  Source re-derivation remains authoritative.
        if self._foreign_checked:
            return
        self._foreign_checked = True
        if self._has_existing_claim_files() and not self._identity_matches_this_machine():
            _write_json_atomic(self._foreign_marker_path(), {
                "status": "foreign",
                "reason": "existing .tmf claims do not carry this machine local identity",
            })

    def is_foreign_store(self) -> bool:
        self._mark_foreign_if_needed()
        return self._foreign_marker_path().exists()

    def clear_foreign_marker(self) -> None:
        marker = self._foreign_marker_path()
        if marker.exists():
            marker.unlink()

    def init(self) -> None:
        if self._initialized:
            return
        self.root.mkdir(parents=True, exist_ok=True)
        self._mark_foreign_if_needed()
        self.claims_dir.mkdir(parents=True, exist_ok=True)
        self._ensure_identity()
        version_file = self.root / "schema_version"
        if not version_file.exists():
            version_file.write_text("tmf.schema.v1\n", encoding="utf-8")
        self._initialized = True

    def claim_path(self, claim_id: str) -> Path:
        return self.claims_dir / f"{claim_id}.json"


    @contextlib.contextmanager
    def write_lock(self):
        """Repository-local interprocess write lock for .tmf mutations.

        Serializes warm/read-through writers. Readers see either old complete
        files or new complete files because writes use temp-file + atomic
        replace. This is a corruption guard, not full snapshot isolation.
        """
        self.root.mkdir(parents=True, exist_ok=True)
        path = self.root / ".lock"
        with path.open("a+", encoding="utf-8") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)

    def _stamp_locally_derived(self, claim: Claim) -> Claim:
        body = dict(claim.body or {})
        source = dict(body.get("source_provenance") or {})
        source.update({
            "origin": "locally_derived",
            "machine_hash": _machine_hash(),
            "trust": "source_rederived",
        })
        body["source_provenance"] = source
        claim.body = body
        return claim

    def _mark_claim_foreign(self, claim: Claim) -> Claim:
        body = dict(claim.body or {})
        source = dict(body.get("source_provenance") or {})
        if source.get("origin") != "locally_derived" or source.get("machine_hash") != _machine_hash():
            source.update({
                "origin": "foreign",
                "trust": "unverified_foreign",
                "reason": "claim came from a .tmf cache not generated under this local identity",
            })
            body["source_provenance"] = source
            claim.body = body
        return claim

    def put_claim(self, claim: Claim) -> None:
        self.init()
        claim = self._stamp_locally_derived(claim)
        path = self.claim_path(claim.id)
        tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(claim.to_dict(), ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")
        tmp.replace(path)

    def delete_claim(self, claim_id: str) -> bool:
        path = self.claim_path(claim_id)
        if not path.exists():
            return False
        path.unlink()
        return True

    def reconcile_path_claims(self, relpath: str, current_claims: list[Claim]) -> list[str]:
        """Delete tombstone claims for a path after re-derivation.

        Rename/delete is represented in v1 as old node removal + new node birth.
        Without this, dead function claims stay stale forever and force every
        read of the path to re-derive.
        """
        current_ids = {claim.id for claim in current_claims}
        deleted: list[str] = []
        for claim in list(self.claims_for_path(relpath)):
            # v2 guardrail: path-level reconciliation may only delete claims
            # whose entire freshness dependency set is this one path. Cross-file
            # architecture/module claims are multi-binding and must be managed by
            # their own derivation/reconciliation flow, not by a local file pass.
            if claim.body.get("edge_kind") in {"calls", "reads", "writes", "inherits", "overrides", "uses_type", "reads_env", "reads_config_key", "injects", "publishes_to", "subscribes_to"}:
                continue
            if len(claim.bindings) != 1 or claim.bindings[0].path != relpath:
                continue
            if claim.id not in current_ids:
                if self.delete_claim(claim.id):
                    deleted.append(claim.id)
        return deleted

    def get_claim(self, claim_id: str) -> Claim | None:
        path = self.claim_path(claim_id)
        if not path.exists():
            return None
        return self._mark_claim_foreign(Claim.from_dict(json.loads(path.read_text(encoding="utf-8"))))

    def iter_claims(self) -> Iterable[Claim]:
        self.init()
        for path in sorted(self.claims_dir.glob("*.json")):
            try:
                yield self._mark_claim_foreign(Claim.from_dict(json.loads(path.read_text(encoding="utf-8"))))
            except Exception:
                # v0 is conservative: corrupt cache is ignored; source fallback remains available.
                continue

    def claims_for_path(self, relpath: str) -> list[Claim]:
        return [
            claim for claim in self.iter_claims()
            if any(binding.path == relpath for binding in claim.bindings)
        ]

    def reconcile_edge_claims_for_caller_path(self, relpath: str, current_edge_claims: list[Claim]) -> list[str]:
        """Delete stale edge claims whose caller/reader side is this path.

        Cross-file edge claims are multi-binding, so they are intentionally skipped
        by path-local node reconciliation. They need this edge-specific lifecycle.
        """
        current_ids = {claim.id for claim in current_edge_claims}
        deleted: list[str] = []
        for claim in self.iter_claims():
            if claim.scope != "cross-repo" and claim.body.get("edge_kind") not in {"calls", "reads", "writes", "inherits", "overrides", "uses_type", "reads_env", "reads_config_key", "injects", "publishes_to", "subscribes_to"}:
                continue
            edge_kind = claim.body.get("edge_kind")
            owner_path = (
                claim.body.get("caller_path") if edge_kind == "calls" else
                claim.body.get("reader_path") if edge_kind == "reads" else
                claim.body.get("writer_path") if edge_kind == "writes" else
                claim.body.get("child_path") if edge_kind == "inherits" else
                claim.body.get("method_path") if edge_kind == "overrides" else
                claim.body.get("reader_path") if edge_kind in {"reads_env", "reads_config_key"} else
                claim.body.get("injector_path") if edge_kind == "injects" else
                claim.body.get("source_path")
            )
            if owner_path != relpath:
                continue
            if claim.id not in current_ids:
                if self.delete_claim(claim.id):
                    deleted.append(claim.id)
        return deleted
