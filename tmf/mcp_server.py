from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

from .assist import ASSIST_SYSTEM_POLICY, AssistProvider, AssistProviderError, default_assist_provider
from .explain import explain_claim, full_view, thin_view
from .freshness import check_freshness
from .git import GitRepo
from .retrieve import retrieve_text, reverse_callers, reverse_readers, reverse_writers
from .store import Store, configure_state_root
from .warm import warm_is_complete


def _json_text(payload: Any) -> dict[str, Any]:
    return {"content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False, sort_keys=True)}]}


class McpService:
    def __init__(
        self,
        repo_root: str | Path,
        state_root: str | Path | None = None,
        *,
        assist_provider: AssistProvider | None = None,
        load_assist_provider: bool = True,
    ) -> None:
        self.repo = GitRepo(repo_root)
        self.state_root = Path(state_root).expanduser().resolve() if state_root is not None else None
        configure_state_root(self.state_root)
        self.store = Store(self.repo.root, self.state_root, read_only=True)
        self.store.require_initialized()
        self._warm_complete_cache: bool | None = None
        self.assist_provider = assist_provider if assist_provider is not None else (default_assist_provider() if load_assist_provider else None)

    def _inside_repo_path(self, path: str | None) -> str | None:
        if path is None:
            return None
        candidate = Path(path)
        resolved = (candidate if candidate.is_absolute() else self.repo.root / candidate).resolve()
        if resolved != self.repo.root and self.repo.root not in resolved.parents:
            raise ValueError("path is outside repo root")
        return resolved.relative_to(self.repo.root).as_posix()

    @staticmethod
    def _anchor_for_claim(claim: Any) -> str | None:
        anchors = claim.body.get("anchors") if isinstance(claim.body, dict) else None
        if isinstance(anchors, list) and anchors:
            first = anchors[0]
            if isinstance(first, str):
                return first
            if isinstance(first, dict):
                path = first.get("path") or (claim.bindings[0].path if claim.bindings else None)
                line = first.get("line") or first.get("line_start")
                if path and line:
                    return f"{path}:{line}"
        return claim.bindings[0].path if claim.bindings else None

    def _candidate_view(self, claim: Any) -> dict[str, Any]:
        return {
            "id": claim.id,
            "claim": claim.claim,
            "qualname": claim.body.get("qualname"),
            "scope": claim.scope,
            "kind": claim.kind,
            "path": claim.bindings[0].path if claim.bindings else None,
            "anchor": self._anchor_for_claim(claim),
        }

    @staticmethod
    def _locator_view(explained: dict[str, Any]) -> dict[str, Any]:
        payload = thin_view(explained)
        for key in ("callees", "callers", "reads", "read_by"):
            items = payload.get(key, [])
            payload[f"{key}_count"] = len(items) if isinstance(items, list) else 0
            payload[key] = items[:5] if isinstance(items, list) else []
        for key in ("unresolved_calls", "reads_unresolved"):
            payload.pop(key, None)
        return payload

    def _resolve_claim_id(
        self,
        *,
        claim_id: str | None = None,
        qualname: str | None = None,
        path: str | None = None,
        scopes: set[str] | None = None,
    ) -> tuple[str | None, dict[str, Any]]:
        if claim_id:
            if self.store.get_claim(str(claim_id)) is None:
                raise ValueError(f"claim not found: {claim_id}")
            return str(claim_id), {"mode": "claim_id", "claim_id": str(claim_id)}
        if not qualname:
            raise ValueError("provide claim_id or qualname")
        rel_path = self._inside_repo_path(path) if path else None
        matches = []
        for claim in self.store.iter_claims():
            if scopes and claim.scope not in scopes:
                continue
            stored = claim.body.get("qualname")
            simple = str(stored).split(".")[-1] if stored is not None else None
            if str(qualname) not in {str(stored), simple}:
                continue
            if rel_path and not any(binding.path == rel_path for binding in claim.bindings):
                continue
            matches.append(claim)
        matches.sort(key=lambda claim: ((claim.bindings[0].path if claim.bindings else ""), str(claim.body.get("qualname")), claim.id))
        if not matches:
            return None, {"mode": "qualname", "qualname": str(qualname), "path": rel_path, "status": "not_found", "candidates": []}
        if len(matches) > 1:
            return None, {"mode": "qualname", "qualname": str(qualname), "path": rel_path, "status": "ambiguous", "candidates": [self._candidate_view(claim) for claim in matches]}
        return matches[0].id, {"mode": "qualname", "qualname": str(qualname), "path": rel_path, "status": "resolved", "claim_id": matches[0].id}

    def tmf_retrieve(self, query: str, limit: int = 5) -> dict[str, Any]:
        requested = max(1, min(int(limit), 50))
        result = retrieve_text(self.repo.root, str(query), limit=50, read_only=True)
        nodes = [item for item in result.claims if item.claim.body.get("edge_kind") not in {"calls", "reads", "writes", "inherits"}][:requested]
        return {
            "query": result.query,
            "view": "thin",
            "coverage": "complete" if self._warm_complete() else "partial",
            "claims": [self._locator_view(explain_claim(self.repo, item.claim, read_only=True)) for item in nodes],
            "source_fallback_paths": sorted(result.source_fallback),
        }

    def tmf_explain(self, claim_id: str, full: bool = False) -> dict[str, Any]:
        claim = self.store.get_claim(str(claim_id))
        if claim is None:
            raise ValueError(f"claim not found: {claim_id}")
        payload = full_view(self.repo, claim, read_only=True) if full else self._locator_view(explain_claim(self.repo, claim, read_only=True))
        return {"view": "full" if full else "thin", "claim": payload}

    def _reverse_by_name(
        self,
        fn: Callable[..., dict[str, Any]],
        *,
        claim_id: str | None,
        qualname: str | None,
        path: str | None,
        scopes: set[str],
    ) -> dict[str, Any]:
        resolved, meta = self._resolve_claim_id(claim_id=claim_id, qualname=qualname, path=path, scopes=scopes)
        if resolved is None:
            return {"status": meta.get("status"), "addressing": meta, "candidates": meta.get("candidates", []), "action_hint": "Ambiguous or missing static target; pick a candidate by path/claim_id before continuing. Do not guess."}
        payload = fn(self.repo.root, resolved, read_only=True)
        payload["addressing"] = meta
        return payload

    def tmf_callers(self, claim_id: str | None = None, qualname: str | None = None, path: str | None = None) -> dict[str, Any]:
        return self._reverse_by_name(reverse_callers, claim_id=claim_id, qualname=qualname, path=path, scopes={"function"})

    def tmf_readers(self, claim_id: str | None = None, qualname: str | None = None, path: str | None = None) -> dict[str, Any]:
        return self._reverse_by_name(reverse_readers, claim_id=claim_id, qualname=qualname, path=path, scopes={"declaration"})

    def tmf_writers(self, claim_id: str | None = None, qualname: str | None = None, path: str | None = None) -> dict[str, Any]:
        return self._reverse_by_name(reverse_writers, claim_id=claim_id, qualname=qualname, path=path, scopes={"declaration"})

    def tmf_subtypes(self, claim_id: str | None = None, qualname: str | None = None, path: str | None = None) -> dict[str, Any]:
        resolved, meta = self._resolve_claim_id(claim_id=claim_id, qualname=qualname, path=path, scopes={"class"})
        if resolved is None:
            return {"status": meta.get("status"), "addressing": meta, "candidates": meta.get("candidates", []), "action_hint": "Ambiguous or missing static type; pick a candidate by path/claim_id before continuing. Do not guess."}
        subtypes, implementors, stale_skipped = [], [], 0
        for claim in self.store.iter_claims():
            body = claim.body
            if body.get("edge_kind") != "inherits" or body.get("parent_id") != resolved:
                continue
            freshness = check_freshness(self.repo, claim)
            if not freshness.fresh:
                stale_skipped += 1
                continue
            item = {"child_id": body.get("child_id"), "child_path": body.get("child_path"), "parent_qualname": body.get("parent_qualname"), "relation": body.get("relation"), "resolution": body.get("resolution"), "evidence": claim.evidence, "anchor": body.get("child_anchor")}
            (implementors if body.get("relation") == "implements" else subtypes).append(item)
        return {"node_id": resolved, "subtypes": subtypes, "implementors": implementors, "stale_skipped": stale_skipped, "coverage": "partial", "addressing": meta, "note": "Known fresh inheritance edges from stored claims only; stale claims are reported and never re-derived."}

    def _context_payload(self, question: str, max_chars: int) -> dict[str, Any]:
        limit = 8 if max_chars <= 3000 else 12 if max_chars <= 6000 else 16
        result = retrieve_text(self.repo.root, str(question), limit=50, read_only=True)
        nodes = [item for item in result.claims if item.claim.body.get("edge_kind") not in {"calls", "reads", "writes", "inherits"}][:limit]
        claims = [self._locator_view(explain_claim(self.repo, item.claim, read_only=True)) for item in nodes]
        relations = []
        for item in nodes:
            claim = item.claim
            if claim.scope == "function":
                callers = reverse_callers(self.repo.root, claim.id, read_only=True).get("callers", [])
                if callers:
                    relations.append({"for": claim.id, "kind": "callers", "items": callers[:5], "coverage": "partial"})
            elif claim.scope == "declaration":
                for kind, fn, key in (("readers", reverse_readers, "readers"), ("writers", reverse_writers, "writers")):
                    items = fn(self.repo.root, claim.id, read_only=True).get(key, [])
                    if items:
                        relations.append({"for": claim.id, "kind": kind, "items": items[:5], "coverage": "partial"})
        relations.sort(key=lambda relation: (str(relation.get("for")), str(relation.get("kind"))))
        return {"question": str(question), "view": "thin_context", "coverage": "complete" if self._warm_complete() else "partial", "truncated": False, "max_chars": max_chars, "claims": claims, "relations": relations, "source_fallback_paths": sorted(result.source_fallback)}

    def tmf_context(self, question: str, max_chars: int | None = None) -> dict[str, Any]:
        budget = max(180, int(max_chars)) if max_chars is not None else 3000
        payload = self._context_payload(question, budget)
        encode = lambda value: len(json.dumps(value, ensure_ascii=False, sort_keys=True))
        if encode(payload) <= budget:
            return payload
        payload = dict(payload)
        payload["truncated"] = True
        payload["relations"] = []
        packed = []
        for claim in payload.get("claims", []):
            trial = dict(payload)
            trial["claims"] = [*packed, claim]
            if encode(trial) <= budget:
                packed.append(claim)
                continue
            stub = {"stub": True, "claim_id": claim.get("id"), "scope": claim.get("scope"), "qualname": claim.get("qualname"), "anchor": (claim.get("anchors") or [None])[0], "expand": "tmf_explain"}
            trial["claims"] = [*packed, stub]
            if encode(trial) <= budget:
                packed.append(stub)
            else:
                break
        payload["claims"] = packed
        while encode(payload) > budget and payload.get("question"):
            payload["question"] = payload["question"][:-10]
        return payload

    @staticmethod
    def _assist_error(code: str, message: str) -> dict[str, str]:
        return {"code": code, "message": message}

    def _assist_bundle(
        self,
        *,
        question: str,
        claim_id: str | None,
        path: str | None,
        qualname: str | None,
        max_context_chars: int,
    ) -> dict[str, Any]:
        selector = " ".join(value for value in (claim_id, qualname, path) if value)
        bundle = self.tmf_context(f"{question} {selector}".strip(), max_context_chars)
        if claim_id:
            bundle = dict(bundle)
            bundle["selected_claim"] = self.tmf_explain(claim_id, full=False)["claim"]
        elif qualname:
            resolved, addressing = self._resolve_claim_id(claim_id=None, qualname=qualname, path=path)
            bundle = dict(bundle)
            bundle["addressing"] = addressing
            if resolved:
                bundle["selected_claim"] = self.tmf_explain(resolved, full=False)["claim"]
        return {"origin": "tmf_deterministic", "bundle": bundle}

    @staticmethod
    def _bundle_claims(bundle_wrapper: dict[str, Any]) -> list[dict[str, Any]]:
        bundle = bundle_wrapper.get("bundle", {})
        claims = list(bundle.get("claims", [])) if isinstance(bundle, dict) and isinstance(bundle.get("claims"), list) else []
        selected = bundle.get("selected_claim") if isinstance(bundle, dict) else None
        if isinstance(selected, dict):
            claims.append(selected)
        return [claim for claim in claims if isinstance(claim, dict)]

    @classmethod
    def _allowed_anchors(cls, bundle_wrapper: dict[str, Any]) -> list[dict[str, Any]]:
        anchors: list[dict[str, Any]] = []
        for claim in cls._bundle_claims(bundle_wrapper):
            candidates = claim.get("anchors") or ([claim.get("anchor")] if claim.get("anchor") else [])
            for anchor in candidates:
                if not isinstance(anchor, dict) or not isinstance(anchor.get("path"), str):
                    continue
                start = anchor.get("line_start", anchor.get("line"))
                end = anchor.get("line_end", start)
                if isinstance(start, int) and isinstance(end, int) and 1 <= start <= end:
                    normalized = {"path": anchor["path"], "line_start": start, "line_end": end}
                    if normalized not in anchors:
                        anchors.append(normalized)
        return anchors

    @classmethod
    def _assist_trust(cls, bundle_wrapper: dict[str, Any]) -> dict[str, Any]:
        refs: list[dict[str, Any]] = []
        stale_reasons: list[str] = []
        for claim in cls._bundle_claims(bundle_wrapper):
            for ref in claim.get("freshness_binding_refs", claim.get("freshness_bindings", [])):
                if isinstance(ref, dict) and ref not in refs:
                    refs.append(ref)
            for reason in claim.get("stale_reasons", []):
                if isinstance(reason, str) and reason not in stale_reasons:
                    stale_reasons.append(reason)
            if claim.get("fresh") is False and not stale_reasons:
                stale_reasons.append("supporting TMF claim is stale")
        trust: dict[str, Any] = {"level": "inferred", "status": "expired" if stale_reasons else "provisional", "freshness_binding_refs": refs}
        if stale_reasons:
            trust["stale_reasons"] = stale_reasons
        return trust

    @staticmethod
    def _contained_anchor(item: Any, allowed: list[dict[str, Any]]) -> bool:
        if not isinstance(item, dict):
            return False
        path, start, end = item.get("path"), item.get("line_start"), item.get("line_end")
        if not isinstance(start, int) or isinstance(start, bool) or not isinstance(end, int) or isinstance(end, bool) or not 1 <= start <= end:
            return False
        return any(path == anchor["path"] and anchor["line_start"] <= start <= end <= anchor["line_end"] for anchor in allowed)

    @classmethod
    def _validate_assist_response(cls, value: Any, allowed: list[dict[str, Any]]) -> dict[str, Any]:
        if not isinstance(value, dict):
            raise ValueError("response must be a JSON object")
        required = {"answer", "inferences", "confidence", "evidence", "assumptions", "unresolved", "suggested_source_reads"}
        if set(value) != required:
            raise ValueError(f"response keys must be exactly: {', '.join(sorted(required))}")
        if not isinstance(value["answer"], str):
            raise ValueError("answer must be a string")
        for key in ("inferences", "evidence", "assumptions", "unresolved", "suggested_source_reads"):
            if not isinstance(value[key], list):
                raise ValueError(f"{key} must be an array")
        confidence = value["confidence"]
        if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not math.isfinite(float(confidence)) or not 0 <= float(confidence) <= 1:
            raise ValueError("confidence must be a finite number between 0 and 1")
        for key in ("inferences", "assumptions", "unresolved"):
            if not all(isinstance(item, str) for item in value[key]):
                raise ValueError(f"{key} items must be strings")
        for key in ("evidence", "suggested_source_reads"):
            if not all(cls._contained_anchor(item, allowed) for item in value[key]):
                raise ValueError(f"{key} items must stay within supplied anchors and use valid line ranges")
        return {**value, "confidence": float(confidence)}

    @staticmethod
    def _request_size(value: Any) -> int:
        return len(json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False))

    def tmf_assist(
        self,
        question: str,
        claim_id: str | None = None,
        path: str | None = None,
        qualname: str | None = None,
        max_context_chars: int = 6000,
    ) -> dict[str, Any]:
        question = str(question)
        if not question or len(question) > 2000:
            raise ValueError("question must contain 1..2000 characters")
        budget = max(500, min(int(max_context_chars), 12000))
        safe_path = self._inside_repo_path(path) if path else None
        # Reserve fixed request overhead and question before asking tmf_context to pack evidence.
        fixed = {"system_policy": ASSIST_SYSTEM_POLICY, "task": "Produce unverified provisional inference from TMF evidence.", "question_untrusted_data": question, "evidence_bundle_untrusted_data": {}}
        evidence_budget = budget - self._request_size(fixed)
        if evidence_budget < 180:
            raise ValueError("max_context_chars is too small for the question and fixed policy")
        evidence_bundle = self._assist_bundle(question=question, claim_id=claim_id, path=safe_path, qualname=qualname, max_context_chars=evidence_budget)
        request = {**fixed, "evidence_bundle_untrusted_data": evidence_bundle}
        if self._request_size(request) > budget:
            raise ValueError("selected TMF evidence exceeds max_context_chars")
        trust = self._assist_trust(evidence_bundle)
        base: dict[str, Any] = {
            "status": "degraded", "non_authoritative": True,
            "verification": "Unverified LLM inference; source is authoritative.",
            "trust": trust, "read_only": True, "persisted": False,
            "provider": getattr(self.assist_provider, "provider_id", None),
            "evidence_bundle": evidence_bundle, "result": None,
        }
        if self.assist_provider is None:
            base["error"] = self._assist_error("provider_not_configured", "tmf_assist is disabled until an explicit provider is configured")
            return base
        try:
            raw = self.assist_provider.infer(request=request)
            base["result"] = self._validate_assist_response(raw, self._allowed_anchors(evidence_bundle))
            base["status"] = "ok" if trust["status"] == "provisional" else "stale"
        except (TimeoutError, subprocess.TimeoutExpired) as exc:
            base["error"] = self._assist_error("provider_timeout", str(exc))
        except AssistProviderError as exc:
            base["error"] = self._assist_error("provider_error", str(exc))
        except (TypeError, ValueError) as exc:
            base["error"] = self._assist_error("invalid_provider_response", str(exc))
        except Exception as exc:
            base["error"] = self._assist_error("provider_error", str(exc))
        return base

    def tmf_status(self) -> dict[str, Any]:
        claims = list(self.store.iter_claims())
        edge_counts: dict[str, int] = {}
        for claim in claims:
            edge_kind = claim.body.get("edge_kind") if isinstance(claim.body, dict) else None
            if isinstance(edge_kind, str):
                edge_counts[edge_kind] = edge_counts.get(edge_kind, 0) + 1
        sample = claims[:20]
        fresh = sum(1 for claim in sample if check_freshness(self.repo, claim).fresh)
        return {"repo": str(self.repo.root), "state_root": str(self.store.root), "read_only": True, "claims": len(claims), "freshness_sample": {"checked": len(sample), "fresh": fresh, "stale": len(sample) - fresh}, "warm_complete": self._warm_complete(), "edge_counts": edge_counts}

    def _warm_complete(self) -> bool:
        if self._warm_complete_cache is None:
            self._warm_complete_cache = warm_is_complete(self.repo.root, self.state_root, read_only=True)
        return self._warm_complete_cache

    def call_tool(self, name: str, arguments: dict[str, Any] | None) -> dict[str, Any]:
        mapping = {"tmf_retrieve": self.tmf_retrieve, "tmf_explain": self.tmf_explain, "tmf_callers": self.tmf_callers, "tmf_readers": self.tmf_readers, "tmf_writers": self.tmf_writers, "tmf_subtypes": self.tmf_subtypes, "tmf_context": self.tmf_context, "tmf_assist": self.tmf_assist, "tmf_status": self.tmf_status}
        if name not in mapping:
            raise ValueError(f"unknown tool: {name}")
        return _json_text(mapping[name](**(arguments or {})))


def tools_list() -> list[dict[str, Any]]:
    schema = lambda props, required=None: {"type": "object", "properties": props, "required": required or [], "additionalProperties": False}
    trust = " Partial coverage; fresh != correct; source is authoritative; stale claims are reported and never re-derived. Strictly read-only."
    reverse_props = {"claim_id": {"type": "string"}, "qualname": {"type": "string"}, "path": {"type": "string"}}
    return [
        {"name": "tmf_context", "description": "Return one deterministic thin context bundle with anchors and key fresh graph relations." + trust, "inputSchema": schema({"question": {"type": "string", "minLength": 1, "maxLength": 2000}, "max_chars": {"type": "integer", "minimum": 180}}, ["question"])},
        {"name": "tmf_assist", "description": "Explicit opt-in LLM inference over a bounded deterministic TMF evidence bundle. Output is inferred/unverified and never persisted; disabled unless a provider is configured." + trust, "inputSchema": schema({"question": {"type": "string", "minLength": 1, "maxLength": 2000}, "claim_id": {"type": "string"}, "path": {"type": "string"}, "qualname": {"type": "string"}, "max_context_chars": {"type": "integer", "minimum": 500, "maximum": 12000}}, ["question"])},
        {"name": "tmf_retrieve", "description": "Retrieve thin TMF claims for a lexical query." + trust, "inputSchema": schema({"query": {"type": "string"}, "limit": {"type": "integer", "minimum": 1, "maximum": 50}}, ["query"])},
        {"name": "tmf_explain", "description": "Explain one stored claim; full=true includes thick details." + trust, "inputSchema": schema({"claim_id": {"type": "string"}, "full": {"type": "boolean"}}, ["claim_id"])},
        {"name": "tmf_callers", "description": "List known fresh callers by claim_id or qualname plus optional path." + trust, "inputSchema": schema(reverse_props)},
        {"name": "tmf_readers", "description": "List known fresh readers by declaration claim_id or qualname plus optional path." + trust, "inputSchema": schema(reverse_props)},
        {"name": "tmf_writers", "description": "List known fresh writers by declaration claim_id or qualname plus optional path." + trust, "inputSchema": schema(reverse_props)},
        {"name": "tmf_subtypes", "description": "List known fresh subtype/implementor edges by type claim_id or qualname plus optional path." + trust, "inputSchema": schema(reverse_props)},
        {"name": "tmf_status", "description": "Report claim/freshness/cache status without modifying state." + trust, "inputSchema": schema({})},
    ]


def _response(request_id: Any, result: Any) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def handle(service: McpService, request: dict[str, Any]) -> dict[str, Any] | None:
    method, request_id = request.get("method"), request.get("id")
    if method == "notifications/initialized":
        return None
    if method == "initialize":
        return _response(request_id, {"protocolVersion": "2024-11-05", "serverInfo": {"name": "tmf-v2-locator", "version": "2.0.0-read-only"}, "capabilities": {"tools": {}}})
    if method == "ping":
        return _response(request_id, {})
    if method == "tools/list":
        return _response(request_id, {"tools": tools_list()})
    if method == "tools/call":
        params = request.get("params") or {}
        try:
            return _response(request_id, service.call_tool(str(params.get("name")), params.get("arguments") or {}))
        except Exception as exc:
            return _error(request_id, -32000, str(exc))
    return _error(request_id, -32601, f"method not found: {method}")


def serve(repo_root: str | Path, state_root: str | Path | None = None, stdin: Any = None, stdout: Any = None) -> int:
    service = McpService(repo_root, state_root)
    stdin, stdout = stdin or sys.stdin, stdout or sys.stdout
    for line in stdin:
        raw = line.strip()
        if not raw:
            continue
        try:
            request = json.loads(raw)
            if not isinstance(request, dict):
                raise ValueError("request must be an object")
            response = handle(service, request)
        except Exception as exc:
            response = _error(None, -32700, f"parse error: {exc}")
        if response is not None:
            print(json.dumps(response, ensure_ascii=False, sort_keys=True), file=stdout, flush=True)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="tmf mcp", description="Run strict read-only TMF v2 MCP stdio server")
    parser.add_argument("--repo", default=".")
    parser.add_argument("--state-root", default=os.environ.get("TMF_STATE_ROOT"))
    args = parser.parse_args(argv)
    return serve(args.repo, args.state_root)


if __name__ == "__main__":
    raise SystemExit(main())
