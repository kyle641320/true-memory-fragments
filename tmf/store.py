from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from .schema import Claim


class Store:
    def __init__(self, repo_root: str | Path = ".") -> None:
        self.repo_root = Path(repo_root).resolve()
        self.root = self.repo_root / ".tmf"
        self.claims_dir = self.root / "claims"

    def init(self) -> None:
        self.claims_dir.mkdir(parents=True, exist_ok=True)
        version_file = self.root / "schema_version"
        if not version_file.exists():
            version_file.write_text("tmf.schema.v1\n", encoding="utf-8")

    def claim_path(self, claim_id: str) -> Path:
        return self.claims_dir / f"{claim_id}.json"

    def put_claim(self, claim: Claim) -> None:
        self.init()
        path = self.claim_path(claim.id)
        path.write_text(json.dumps(claim.to_dict(), ensure_ascii=False, indent=2, sort_keys=False) + "\n", encoding="utf-8")

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
        return Claim.from_dict(json.loads(path.read_text(encoding="utf-8")))

    def iter_claims(self) -> Iterable[Claim]:
        self.init()
        for path in sorted(self.claims_dir.glob("*.json")):
            try:
                yield Claim.from_dict(json.loads(path.read_text(encoding="utf-8")))
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
        for claim in list(self.iter_claims()):
            if claim.scope != "cross-repo" and claim.body.get("edge_kind") not in {"calls", "reads", "writes", "inherits"}:
                continue
            edge_kind = claim.body.get("edge_kind")
            owner_path = claim.body.get("caller_path") if edge_kind == "calls" else (claim.body.get("reader_path") if edge_kind == "reads" else (claim.body.get("writer_path") if edge_kind == "writes" else claim.body.get("child_path")))
            if owner_path != relpath:
                continue
            if claim.id not in current_ids:
                if self.delete_claim(claim.id):
                    deleted.append(claim.id)
        return deleted
