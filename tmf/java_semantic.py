from __future__ import annotations

"""Provider-neutral Java external semantic facts v1 ingestion.

This module is deliberately an overlay.  It never parses Java or manufactures a
fact: every emitted claim corresponds to one validated external fact.
"""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
from typing import Any

from .backends import SemanticExtractorBackend
from .ids import now_utc
from .schema import Binding, Claim

FORMAT = "tmf.java-semantic-facts.v1"
FACT_KINDS = {"declaration", "reference", "call", "extends", "implements", "overrides", "uses_type"}
EDGE_MAP = {"reference": "semantic_depends_on", "call": "semantic_calls", "extends": "semantic_uses_type", "implements": "semantic_uses_type", "overrides": "semantic_depends_on", "uses_type": "semantic_uses_type"}


def content_sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _safe_path(value: Any) -> str | None:
    if not isinstance(value, str) or not value or "\\" in value:
        return None
    p = PurePosixPath(value)
    if p.is_absolute() or any(x in ("", ".", "..") for x in p.parts):
        return None
    return p.as_posix()


def _range(value: Any, text: str) -> tuple[int, int, int, int] | None:
    if not isinstance(value, dict):
        return None
    vals = tuple(value.get(k) for k in ("start_line", "start_column", "end_line", "end_column"))
    if not all(isinstance(x, int) and not isinstance(x, bool) and x >= 0 for x in vals):
        return None
    sl, sc, el, ec = vals
    lines = text.splitlines() or [""]
    if sl > el or el >= len(lines) or sc > len(lines[sl]) or ec > len(lines[el]) or (sl == el and sc >= ec):
        return None
    return vals


def _symbol(value: Any) -> str | None:
    # IDs are opaque provider-owned identifiers, but must be globally qualified
    # enough to avoid simple-name ambiguity and safe to serialize/log.
    if not isinstance(value, str) or len(value) > 2048 or any(c.isspace() or ord(c) < 32 for c in value):
        return None
    if ":" not in value or value.startswith(":") or value.endswith(":"):
        return None
    return value


class JavaSemanticFactsBackend(SemanticExtractorBackend):
    """Read immutable JSON documents from an explicitly enabled directory."""

    def __init__(self, facts_dir: str | Path | None = None, *, enabled: bool = False) -> None:
        self.facts_dir = Path(facts_dir).resolve() if facts_dir else None
        self.enabled = bool(enabled)
        self.last_status: dict[str, Any] = {"reason": "default_off" if not enabled else "no_provider"}

    def available(self) -> bool:
        ok = self.enabled and self.facts_dir is not None and self.facts_dir.is_dir()
        if not ok:
            self.last_status = {"reason": "default_off" if not self.enabled else "no_provider"}
        return ok

    def enqueue_background_refresh(self, repo_root: str, path: str) -> None:
        # Files are produced out-of-process. Ingestion has no compiler side effects.
        return None

    def semantic_claims_for_path(self, repo, path: str, source: str) -> list[Claim]:
        safe = _safe_path(path)
        if not self.available() or safe is None or not safe.endswith(".java"):
            self.last_status = {"reason": "path_escape" if safe is None else "unsupported_path"}
            return []
        docs: list[dict[str, Any]] = []
        reasons: list[str] = []
        for file in sorted(self.facts_dir.glob("*.json")):
            try:
                doc = json.loads(file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                reasons.append("malformed_document"); continue
            candidates = doc.get("documents", []) if doc.get("format") == "tmf.java-semantic-facts-batch.v1" else [doc]
            for candidate in candidates:
                if candidate.get("format") != FORMAT:
                    reasons.append("unsupported_format"); continue
                if _safe_path(candidate.get("path")) != safe: continue
                required = ("provider", "provider_version", "tool", "tool_version", "classpath_fingerprint", "build_fingerprint", "content_sha256", "facts")
                if any(not candidate.get(k) for k in required) or not isinstance(candidate.get("facts"), list): reasons.append("missing_provenance"); continue
                hashes=candidate.get("source_hashes")
                if hashes is not None:
                    if not isinstance(hashes,dict) or any(_safe_path(p) is None or not isinstance(h,str) or len(h)!=64 for p,h in hashes.items()): reasons.append("malformed_source_hashes"); continue
                    if any(not (repo.root / p).is_file() or content_sha256((repo.root / p).read_text(encoding="utf-8")) != h for p,h in hashes.items()): reasons.append("stale_participating_source"); continue
                if candidate["content_sha256"] != content_sha256(source): reasons.append("stale_content_hash"); continue
                docs.append(candidate)
        # Multiple providers may disagree. Never choose or merge confidence.
        signatures = {json.dumps(d["facts"], sort_keys=True, separators=(",", ":")) for d in docs}
        if len(signatures) > 1:
            self.last_status = {"reason": "conflicting_providers", "providers": sorted(str(d["provider"]) for d in docs)}
            return []
        if not docs:
            self.last_status = {"reason": reasons[0] if reasons else "no_facts_for_path", "reasons": sorted(set(reasons))}
            return []
        doc = sorted(docs, key=lambda d: (str(d["provider"]), str(d["provider_version"])))[0]
        claims: list[Claim] = []
        seen_keys: set[tuple[str, str, str, tuple[int, int, int, int]]] = set()
        for fact in doc["facts"]:
            if not isinstance(fact, dict) or fact.get("kind") not in FACT_KINDS:
                reasons.append("malformed_fact"); continue
            source_symbol = _symbol(fact.get("source_symbol"))
            target_symbol = _symbol(fact.get("target_symbol")) if fact.get("kind") != "declaration" else None
            rng = _range(fact.get("range"), source)
            if source_symbol is None or rng is None or (fact.get("kind") != "declaration" and target_symbol is None):
                reasons.append("ambiguous_symbol_id" if source_symbol is None or (fact.get("kind") != "declaration" and target_symbol is None) else "malformed_range"); continue
            # v1 attributed facts must be independently auditable: the source
            # range is the human anchor; offsets and erased JVM descriptors
            # make overload identity explicit rather than provider-implied.
            anchor = fact.get("anchor")
            owner_fields = (fact.get("source_owner"), fact.get("source_descriptor"))
            target_fields = (fact.get("target_owner"), fact.get("target_descriptor"))
            attributed_identity_ok = (
                isinstance(anchor, dict)
                and isinstance(anchor.get("start_offset"), int)
                and isinstance(anchor.get("end_offset"), int)
                and 0 <= anchor["start_offset"] < anchor["end_offset"] <= len(source)
                and all(isinstance(x, str) and x for x in owner_fields)
                and (fact.get("kind") == "declaration" or all(isinstance(x, str) and x for x in target_fields))
            )
            if not attributed_identity_ok:
                reasons.append("missing_attributed_identity"); continue
            key = (fact["kind"], source_symbol, target_symbol or "", rng)
            if key in seen_keys:
                continue
            seen_keys.add(key)
            digest = hashlib.sha256((FORMAT + "\0" + safe + "\0" + "\0".join(map(str, key))).encode()).hexdigest()[:24]
            body = {"extraction_tier": "compiler-attributed", "tier": "compiler-attributed", "semantic_fact_kind": fact["kind"], "source_symbol": source_symbol, "source_path": safe, "source_range": {k: v for k, v in zip(("start_line", "start_column", "end_line", "end_column"), rng)}, "anchor": dict(anchor), "source_owner": owner_fields[0], "source_descriptor": owner_fields[1], "content_sha256": doc["content_sha256"], "trust": "external-untrusted-attributed", "provider": doc["provider"], "provider_version": doc["provider_version"], "tool": doc["tool"], "tool_version": doc["tool_version"], "classpath_fingerprint": doc["classpath_fingerprint"], "build_fingerprint": doc["build_fingerprint"]}
            if target_symbol:
                body.update({"target_symbol": target_symbol, "target_owner": target_fields[0], "target_descriptor": target_fields[1], "edge_kind": EDGE_MAP[fact["kind"]]})
            claims.append(Claim(id=f"claim_java_semantic_{digest}", claim=f"external Java semantic {fact['kind']}", kind="structure", scope="cross-repo" if target_symbol else "declaration", bindings=[Binding(path=safe, file_blob=repo.blob_sha(safe), fn_hash=doc["content_sha256"], commit=repo.head(), role="semantic_source", line_start=rng[0] + 1, line_end=rng[2] + 1, hash_kind="sha256")], provenance=f"external:{doc['provider']}", evidence="inferred", confidence=0.6, endorsed_by=None, last_verified=now_utc(), model=f"{doc['tool']}@{doc['tool_version']}", body=body))
        self.last_status = {"reason": "accepted" if claims else (reasons[-1] if reasons else "no_valid_facts"), "accepted": len(claims), "reasons": sorted(set(reasons))}
        return sorted(claims, key=lambda c: c.id)
