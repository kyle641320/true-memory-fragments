from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal

SCHEMA_VERSION = "tmf.schema.v1"
SUPPORTED_SCHEMA_VERSIONS = {"tmf.schema.v0", SCHEMA_VERSION}
ClaimKind = Literal["structure", "architecture", "intent", "convention", "gotcha"]
ClaimScope = Literal["file", "function", "class", "module", "repo", "cross-repo", "declaration", "config", "api"]
Evidence = Literal["observed", "inferred", "verified"]


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

    def to_dict(self) -> dict[str, Any]:
        self.confidence = max(0.0, min(1.0, float(self.confidence)))
        data = asdict(self)
        data["schema_version"] = SCHEMA_VERSION
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
        return cls(**payload)
