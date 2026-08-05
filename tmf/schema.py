from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal

SCHEMA_VERSION = "tmf.schema.v1"
SUPPORTED_SCHEMA_VERSIONS = {"tmf.schema.v0", SCHEMA_VERSION}
MODULE_TOP_LEVEL_CONTRACT_SCHEMA_VERSION = "tmf.module_top_level_contract.v2"
SKIPPED_CLAIM_SCHEMA_VERSION = "tmf.skipped_claim.v1"
ClaimKind = Literal["structure", "architecture", "intent", "convention", "gotcha"]
ClaimScope = Literal["file", "function", "class", "module", "repo", "cross-repo", "declaration", "config", "api", "module_top_level"]
Evidence = Literal["observed", "inferred", "verified"]
SkipReason = Literal["derive_timeout", "derive_failed"]
InvalidationStatus = Literal["changed", "added", "deleted", "module_top_level_changed", "module_top_level_added", "module_top_level_removed"]
MODULE_TOP_LEVEL_STATUSES: tuple[InvalidationStatus, ...] = (
    "module_top_level_changed",
    "module_top_level_added",
    "module_top_level_removed",
)


def module_top_level_invalidation_status(
    *, old_present: bool, new_present: bool, hashes_equal: bool = False
) -> InvalidationStatus | None:
    """Classify a module-top-level identity transition without changing extraction scope."""

    if old_present and new_present:
        return None if hashes_equal else "module_top_level_changed"
    if old_present:
        return "module_top_level_removed"
    if new_present:
        return "module_top_level_added"
    return None


@dataclass(frozen=True)
class SourceAnchor:
    """Inclusive source line interval used by first-class claim contracts."""

    start: int
    end: int


@dataclass(frozen=True)
class ModuleTopLevelContract:
    """Stable module-top-level identity and its engine-owned source anchor."""

    region_id: str
    anchor: SourceAnchor
    schema_version: str = MODULE_TOP_LEVEL_CONTRACT_SCHEMA_VERSION


@dataclass(frozen=True)
class SkippedClaim:
    """Engine-owned fact that a file's cognition was not updated."""

    file: str
    reason: SkipReason
    elapsed_ms: int | None = None
    error: str | None = None
    schema_version: str = SKIPPED_CLAIM_SCHEMA_VERSION
    kind: Literal["skipped"] = "skipped"

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if self.elapsed_ms is None:
            data.pop("elapsed_ms")
        if self.error is None:
            data.pop("error")
        return {"schema_version": data.pop("schema_version"), **data}


@dataclass(frozen=True)
class Binding:
    path: str
    file_blob: str | None
    fn_hash: str | None
    commit: str | None
    qualname: str | None = None


@dataclass
class Claim:
    id: str
    claim: str
    kind: ClaimKind
    scope: ClaimScope
    bindings: list[Binding]
    provenance: str
    evidence: Evidence
    confidence: float
    endorsed_by: str | None
    last_verified: str
    model: str
    body: dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION
    module_top_level_contract: ModuleTopLevelContract | None = None

    def to_dict(self) -> dict[str, Any]:
        self.confidence = max(0.0, min(1.0, float(self.confidence)))
        data = asdict(self)
        data["schema_version"] = SCHEMA_VERSION
        if self.module_top_level_contract is None:
            data.pop("module_top_level_contract", None)
        return {"schema_version": data.pop("schema_version"), **data}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Claim":
        version = data.get("schema_version")
        if version not in SUPPORTED_SCHEMA_VERSIONS:
            raise ValueError(f"unsupported schema_version: {version!r}")
        bindings = [Binding(**item) for item in data.get("bindings", [])]
        payload = dict(data)
        payload["schema_version"] = SCHEMA_VERSION
        payload["bindings"] = bindings
        raw_contract = payload.get("module_top_level_contract")
        if isinstance(raw_contract, dict):
            raw_anchor = raw_contract.get("anchor")
            if isinstance(raw_anchor, dict):
                raw_contract = dict(raw_contract)
                raw_contract["anchor"] = SourceAnchor(**raw_anchor)
            payload["module_top_level_contract"] = ModuleTopLevelContract(**raw_contract)
        elif payload.get("scope") == "module_top_level":
            # Backward-compatible engine-side upgrade for v1 cached claims.
            body = payload.get("body") if isinstance(payload.get("body"), dict) else {}
            anchors = body.get("anchors") if isinstance(body.get("anchors"), list) else []
            binding_qualname = bindings[0].qualname if bindings else None
            region_id = body.get("region_id") or binding_qualname
            first = anchors[0] if anchors and isinstance(anchors[0], dict) else None
            if isinstance(region_id, str) and first and isinstance(first.get("line_start"), int) and isinstance(first.get("line_end"), int):
                payload["module_top_level_contract"] = ModuleTopLevelContract(
                    region_id=region_id,
                    anchor=SourceAnchor(start=first["line_start"], end=first["line_end"]),
                )
        return cls(**payload)
