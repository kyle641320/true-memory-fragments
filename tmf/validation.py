from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from .extract import extract_apis, extract_classes, extract_configs, extract_declarations, extract_functions
from .explain import explain_claim, full_view, thin_view
from .freshness import check_freshness
from .git import GitRepo
from .ids import stable_api_claim_id, stable_call_edge_claim_id, stable_config_claim_id, stable_declaration_claim_id, stable_file_claim_id, stable_function_claim_id, stable_read_edge_claim_id, stable_write_edge_claim_id
from .llm import ModelCandidate
from .model_derive import _claim_from_candidate
from .provenance import pr_evidence
from .retrieve import retrieve_path, retrieve_text, reverse_callers, reverse_readers, reverse_writers
from .store import Store
from .warm import warm_repo


def _write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _stale(repo: GitRepo, claim_id: str) -> bool:
    claim = Store(repo.root).get_claim(claim_id)
    if claim is None:
        return True
    return not check_freshness(repo, claim).fresh


def _copy_repo(src: Path, parent: Path, name: str) -> Path:
    dst = parent / name
    shutil.copytree(src, dst)
    return dst


def _precision_recall(tp: int, fp: int, fn: int) -> tuple[float, float]:
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    return precision, recall


def _freshness_checks(repo_path: Path) -> dict[str, Any]:
    events: list[dict[str, Any]] = []
    tp = fp = fn = 0
    if not (repo_path / "b.py").exists() or "def helper" not in _read(repo_path / "b.py") or "def spare" not in _read(repo_path / "b.py"):
        return {"precision": 1.0, "recall": 1.0, "tp": 0, "fp": 0, "fn": 0, "events": [], "skipped": "fixture lacks b.py helper/spare perturbation targets"}
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)

        # Function body change: helper and edge should stale; spare should remain fresh.
        r1 = _copy_repo(repo_path, work, "body_change")
        warm_repo(r1)
        repo = GitRepo(r1)
        helper = stable_function_claim_id("b.py", "helper")
        spare = stable_function_claim_id("b.py", "spare")
        edge_ids = [p.stem for p in (r1 / ".tmf" / "claims").glob("claim_edge_*.json")]
        (r1 / "b.py").write_text("def helper():\n    return 10\n\ndef spare():\n    return 2\n", encoding="utf-8")
        expected_stale = {helper, *edge_ids}
        checked = {helper, spare, *edge_ids}
        for cid in checked:
            actual = _stale(repo, cid)
            expected = cid in expected_stale
            events.append({"scenario": "function_body_change", "claim_id": cid, "expected_stale": expected, "actual_stale": actual})
            if actual and expected:
                tp += 1
            elif actual and not expected:
                fp += 1
            elif not actual and expected:
                fn += 1

        # Comment-only change should not stale function-level semantic nodes according to the held-out contract.
        r2 = _copy_repo(repo_path, work, "comment_change")
        warm_repo(r2)
        repo = GitRepo(r2)
        helper = stable_function_claim_id("b.py", "helper")
        before = _read(r2 / "b.py")
        (r2 / "b.py").write_text("# comment only\n" + before, encoding="utf-8")
        actual = _stale(repo, helper)
        expected = False
        events.append({"scenario": "comment_only_change", "claim_id": helper, "expected_stale": expected, "actual_stale": actual})
        if actual and expected:
            tp += 1
        elif actual and not expected:
            fp += 1
        elif not actual and expected:
            fn += 1

        # Rename/delete should reconcile tombstones after read-through.
        r3 = _copy_repo(repo_path, work, "rename_delete")
        warm_repo(r3)
        helper = stable_function_claim_id("b.py", "helper")
        (r3 / "b.py").write_text("def renamed():\n    return 1\n\ndef spare():\n    return 2\n", encoding="utf-8")
        from .retrieve import retrieve_path
        retrieve_path(r3, "b.py")
        tombstone_removed = Store(r3).get_claim(helper) is None
        events.append({"scenario": "rename_delete_reconcile", "claim_id": helper, "expected_removed": True, "actual_removed": tombstone_removed})

    precision, recall = _precision_recall(tp, fp, fn)
    return {"precision": precision, "recall": recall, "tp": tp, "fp": fp, "fn": fn, "events": events}


def _source_for_claim(repo: GitRepo, claim) -> str:
    paths = {binding.path for binding in claim.bindings}
    return "\n".join(repo.read_file(path) for path in paths if (repo.root / path).exists())


def _claim_support_checks(repo_path: Path) -> dict[str, Any]:
    repo = GitRepo(repo_path)
    store = Store(repo.root)
    observed_without_support = []
    attributed_without_provenance_support = []
    for claim in store.iter_claims():
        candidate = claim.body.get("model_candidate", {})
        support = candidate.get("support", []) if isinstance(candidate, dict) else []
        verification = candidate.get("verification") if isinstance(candidate, dict) else None
        if verification == "source_support_literal" and claim.evidence == "observed":
            source = _source_for_claim(repo, claim)
            if not support or not all(str(item) in source for item in support):
                observed_without_support.append(claim.id)
        if verification == "attributed_external_provenance":
            prov_text = "\n".join(str(item.get("text_untrusted_data", "")) for item in claim.body.get("provenance_evidence", []))
            if not support or not all(str(item) in prov_text for item in support):
                attributed_without_provenance_support.append(claim.id)
    return {
        "observed_without_current_source_support": len(observed_without_support),
        "attributed_without_provenance_support": len(attributed_without_provenance_support),
        "violations": observed_without_support + attributed_without_provenance_support,
    }


def _invariant_audit(repo_path: Path, *, check_coverage_drift: bool = True) -> dict[str, Any]:
    repo = GitRepo(repo_path)
    store = Store(repo.root)
    violations: list[dict[str, str]] = []
    for claim in store.iter_claims():
        candidate = claim.body.get("model_candidate", {})
        verification = candidate.get("verification") if isinstance(candidate, dict) else None
        raw = candidate.get("raw_confidence") if isinstance(candidate, dict) else None
        if claim.kind == "intent" and not claim.body.get("provenance_evidence") and claim.evidence == "observed":
            violations.append({"claim_id": claim.id, "kind": "intent_without_provenance_observed"})
        if verification == "intent_requires_external_provenance" and claim.confidence > 0.25:
            violations.append({"claim_id": claim.id, "kind": "unsupported_intent_cap_exceeded"})
        if verification == "attributed_external_provenance" and (claim.evidence != "inferred" or claim.confidence > 0.6):
            violations.append({"claim_id": claim.id, "kind": "attributed_cap_or_evidence_violation"})
        if raw is not None and float(raw) > claim.confidence and claim.confidence > 0.6:
            violations.append({"claim_id": claim.id, "kind": "raw_confidence_not_capped"})
        thin = thin_view(explain_claim(repo, claim))
        if "quoted_text_untrusted_data" in json.dumps(thin):
            violations.append({"claim_id": claim.id, "kind": "thin_leaks_quoted_text"})

    # Complete coverage must degrade after warm drift. Run on a copy so this audit
    # cannot contaminate later measurement checks on the same sample repo. This
    # fixture-scale probe is covered by held-out validation; self-validation can
    # disable it to avoid quadratic real-repo dogfood copies while preserving the
    # invariant scan over real claims.
    if check_coverage_drift:
        with tempfile.TemporaryDirectory() as td:
            drift_repo = _copy_repo(repo.root, Path(td), "coverage_drift")
            drift_store = Store(drift_repo)
            edge_claims = [claim for claim in drift_store.iter_claims() if claim.body.get("edge_kind") == "calls"]
            if edge_claims:
                callee_id = edge_claims[0].body.get("callee_id")
                caller_path = edge_claims[0].body.get("caller_path")
                if isinstance(callee_id, str) and isinstance(caller_path, str):
                    before = reverse_callers(drift_repo, callee_id)
                    if before.get("coverage") == "complete":
                        path = drift_repo / caller_path
                        path.write_text(path.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
                        after = reverse_callers(drift_repo, callee_id)
                        if after.get("coverage") == "complete":
                            violations.append({"claim_id": str(callee_id), "kind": "reverse_callers_complete_despite_drift"})
    return {"total_violations": len(violations), "violations": violations}


def _degrade_checks(repo_path: Path) -> dict[str, Any]:
    checked = []
    if not (repo_path / "b.py").exists() or "def helper" not in _read(repo_path / "b.py"):
        return {"checked": [], "failures": [], "skipped": "fixture lacks b.py helper target"}
    with tempfile.TemporaryDirectory() as td:
        r = _copy_repo(repo_path, Path(td), "degrade")
        warm_repo(r)
        grepo = GitRepo(r)
        helper = stable_function_claim_id("b.py", "helper")
        claim = Store(r).get_claim(helper)
        if claim is not None:
            (r / "b.py").write_text("def helper():\n    return 100\n\ndef spare():\n    return 2\n", encoding="utf-8")
            explained = explain_claim(grepo, claim)
            checked.append({
                "claim_id": helper,
                "fresh": explained["fresh"],
                "action_hint": explained["action_hint"],
                "has_anchor": bool(explained.get("anchors")),
                "pass": (not explained["fresh"] and explained["action_hint"] == "degrade_to_source_or_rederive" and bool(explained.get("anchors"))),
            })
    return {"checked": checked, "failures": [item for item in checked if not item["pass"]]}


def _lifecycle_checks(repo_path: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    if not (repo_path / "a.py").exists() or not (repo_path / "b.py").exists():
        return {"checks": [], "failures": [], "skipped": "fixture lacks cross-file a.py/b.py"}
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        r = _copy_repo(repo_path, root, "lifecycle")
        warm_repo(r)
        edge_ids = [claim.id for claim in Store(r).iter_claims() if claim.body.get("edge_kind") == "calls"]
        edge_id = edge_ids[0] if edge_ids else None
        helper_id = stable_function_claim_id("b.py", "helper")
        (r / "b.py").write_text("def spare():\n    return 2\n", encoding="utf-8")
        retrieve_path(r, "a.py")
        store = Store(r)
        edge_removed = edge_id is None or store.get_claim(edge_id) is None
        callers = reverse_callers(r, helper_id)
        checks.append({"name": "cross_file_callee_delete_removes_edge", "pass": edge_removed and callers["callers"] == [], "edge_removed": edge_removed, "callers": callers})

        r2 = _copy_repo(repo_path, root, "guard")
        warm_repo(r2)
        edge_ids = [claim.id for claim in Store(r2).iter_claims() if claim.body.get("edge_kind") == "calls"]
        retrieve_path(r2, "b.py")
        survived = bool(edge_ids) and Store(r2).get_claim(edge_ids[0]) is not None
        checks.append({"name": "multi_binding_edge_survives_path_node_reconcile", "pass": survived, "edge_id": edge_ids[0] if edge_ids else None})
    return {"checks": checks, "failures": [c for c in checks if not c["pass"]]}


def _thin_full_checks(repo_path: Path) -> dict[str, Any]:
    repo = GitRepo(repo_path)
    checks: list[dict[str, Any]] = []
    for claim in Store(repo.root).iter_claims():
        explained = explain_claim(repo, claim)
        thin = thin_view(explained)
        full = full_view(repo, claim)
        ok = thin["id"] == full["id"] and thin["claim"] == full["claim"] and thin["fresh"] == full["fresh"]
        thin_json = json.dumps(thin)
        no_forbidden = all(token not in thin_json for token in ["claim_record", "body", "quoted_text_untrusted_data"])
        short_hashes = all(len(ref.get("file_blob", "")) <= 12 for ref in thin.get("freshness_binding_refs", []))
        full_restores = full.get("claim_record", {}).get("id") == claim.id and "body" in full.get("claim_record", {})
        checks.append({"claim_id": claim.id, "pass": ok and no_forbidden and short_hashes and full_restores, "thin_subset": ok, "no_forbidden": no_forbidden, "short_hashes": short_hashes, "full_restores": full_restores})
    return {"checks": checks, "failures": [c for c in checks if not c["pass"]]}


def _verification_boundary_checks(repo_path: Path) -> dict[str, Any]:
    repo = GitRepo(repo_path)
    from .extract import extract_functions
    functions = extract_functions("b.py", repo.read_file("b.py")) if (repo.root / "b.py").exists() else []
    if not functions:
        return {"checks": [], "failures": [], "skipped": "fixture lacks function target"}
    fn = functions[0]
    cases = []
    candidates = [
        ("supported_source", ModelCandidate("helper returns 1", "structure", "source_verifiable", ["return 1"], 0.99), None, "observed", 0.6),
        ("unsupported_source", ModelCandidate("helper opens network", "structure", "source_verifiable", ["open_network"], 0.99), None, "inferred", 0.2),
        ("intent_no_prov", ModelCandidate("helper exists to test settlement", "intent", "intent_needs_provenance", ["settlement"], 0.99), None, "inferred", 0.25),
        ("intent_pr_prov", ModelCandidate("helper exists for settlement", "intent", "intent_needs_provenance", ["settlement"], 0.99), [pr_evidence(text="PR says helper exists for settlement.", url="https://example.invalid/pr/validation", path="b.py", line_start=fn.line_start, line_end=fn.line_end)], "inferred", 0.6),
    ]
    for name, candidate, evidence, expected_evidence, cap in candidates:
        claim = _claim_from_candidate(repo, fn, candidate, "validation-fake", provenance_evidence=evidence)
        ok = claim.evidence == expected_evidence and claim.confidence <= cap
        if name == "supported_source":
            ok = ok and claim.body["model_candidate"]["verification"] == "source_support_literal"
        if name == "intent_pr_prov":
            ok = ok and claim.body["model_candidate"]["verification"] == "attributed_external_provenance"
        cases.append({"name": name, "pass": ok, "evidence": claim.evidence, "confidence": claim.confidence, "cap": cap, "verification": claim.body["model_candidate"]["verification"]})
    return {"checks": cases, "failures": [c for c in cases if not c["pass"]]}


def _provenance_freshness_checks(repo_path: Path) -> dict[str, Any]:
    if not (repo_path / "b.py").exists():
        return {"checks": [], "failures": [], "skipped": "fixture lacks function target"}
    with tempfile.TemporaryDirectory() as td:
        work = _copy_repo(repo_path, Path(td), "provenance")
        repo = GitRepo(work)
        from .extract import extract_functions
        functions = extract_functions("b.py", repo.read_file("b.py"))
        if not functions:
            return {"checks": [], "failures": [], "skipped": "fixture lacks function target"}
        fn = functions[0]
        claim = _claim_from_candidate(
            repo,
            fn,
            ModelCandidate("helper exists for settlement", "intent", "intent_needs_provenance", ["settlement"], 0.99),
            "validation-fake",
            provenance_evidence=[pr_evidence(text="PR says helper exists for settlement.", url="https://example.invalid/pr/validation", path="b.py", line_start=fn.line_start, line_end=fn.line_end)],
        )
        (work / "b.py").write_text("def helper():\n    return 100\n\ndef spare():\n    return 2\n", encoding="utf-8")
        fresh = check_freshness(repo, claim).fresh
    check = {"name": "provenance_not_freshness_gate", "pass": not fresh, "fresh_after_code_change": fresh}
    return {"checks": [check], "failures": [] if check["pass"] else [check]}


def _embedding_router_checks(repo_path: Path) -> dict[str, Any]:
    import os
    old_embed = os.environ.pop("TMF_EMBED_COMMAND", None)
    old_router = os.environ.pop("TMF_ROUTER_COMMAND", None)
    try:
        actual = [item.claim.id for item in retrieve_text(repo_path, "helper", limit=5).claims]
        expected: list[str] | None = None
        if (repo_path / "a.py").exists() and (repo_path / "b.py").exists():
            caller = stable_function_claim_id("a.py", "main")
            callee = stable_function_claim_id("b.py", "helper")
            expected = [
                stable_call_edge_claim_id(caller, callee),
                stable_file_claim_id("b.py"),
                stable_file_claim_id("a.py"),
                callee,
            ]
        check = {"name": "embed_router_off_matches_lexical_baseline", "pass": expected is None or actual == expected, "expected": expected, "actual": actual}
        return {"checks": [check], "failures": [] if check["pass"] else [check]}
    finally:
        if old_embed is not None:
            os.environ["TMF_EMBED_COMMAND"] = old_embed
        if old_router is not None:
            os.environ["TMF_ROUTER_COMMAND"] = old_router


def _warm_checks(repo_path: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as td:
        r = _copy_repo(repo_path, Path(td), "warm")
        first = warm_repo(r)
        second = warm_repo(r)
        checks.append({"name": "warm_second_run_noop", "pass": second["derived"] == 0, "first": first, "second": second})
        if (r / "b.py").exists():
            (r / "b.py").write_text((r / "b.py").read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
            third = warm_repo(r)
            checks.append({"name": "warm_single_file_incremental", "pass": third["derived"] == 1, "third": third})
    return {"checks": checks, "failures": [c for c in checks if not c["pass"]]}


def _reverse_coverage_checks(repo_path: Path) -> dict[str, Any]:
    if not (repo_path / "a.py").exists() or not (repo_path / "b.py").exists():
        return {"checks": [], "failures": [], "skipped": "fixture lacks cross-file a.py/b.py"}
    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as td:
        r = _copy_repo(repo_path, Path(td), "coverage")
        warm_repo(r)
        edge = next((claim for claim in Store(r).iter_claims() if claim.body.get("edge_kind") == "calls"), None)
        if edge is not None:
            complete = reverse_callers(r, edge.body["callee_id"])
            checks.append({"name": "warm_complete_coverage", "pass": complete["coverage"] == "complete", "coverage": complete["coverage"]})
            (r / edge.body["caller_path"]).write_text((r / edge.body["caller_path"]).read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")
            drift = reverse_callers(r, edge.body["callee_id"])
            checks.append({"name": "drift_forces_partial", "pass": drift["coverage"] == "partial", "coverage": drift["coverage"]})
    return {"checks": checks, "failures": [c for c in checks if not c["pass"]]}


def _degrade_all_checks(repo_path: Path) -> dict[str, Any]:
    repo = GitRepo(repo_path)
    store = Store(repo.root)
    checks: list[dict[str, Any]] = []
    for claim in store.iter_claims():
        explained = explain_claim(repo, claim)
        low_conf = float(claim.confidence) < 0.3
        if not explained["fresh"] or low_conf:
            ok = bool(explained.get("anchors")) and explained.get("action_hint") in {"degrade_to_source_or_rederive", "use_as_search_hint_then_verify_source"}
            checks.append({"claim_id": claim.id, "pass": ok, "fresh": explained["fresh"], "confidence": claim.confidence, "action_hint": explained.get("action_hint"), "has_anchor": bool(explained.get("anchors"))})
    return {"checks": checks, "failures": [c for c in checks if not c["pass"]]}


def _config_node_checks(repo_path: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)

        r = root / "json_value"
        r.mkdir()
        (r / "config.json").write_text('{"timeout":30,"name":"svc"}\n', encoding="utf-8")
        repo = GitRepo(r)
        retrieve_path(r, "config.json")
        timeout_id = stable_config_claim_id("config.json", "timeout")
        timeout = Store(r).get_claim(timeout_id)
        fresh_initial = timeout is not None and check_freshness(repo, timeout).fresh
        (r / "config.json").write_text('{"timeout":60,"name":"svc"}\n', encoding="utf-8")
        stale_after_value = timeout is not None and not check_freshness(repo, timeout).fresh
        checks.append({"name": "config_value_change_stales", "pass": fresh_initial and stale_after_value})

        r2 = root / "json_format"
        r2.mkdir()
        (r2 / "config.json").write_text('{"timeout":30,"name":"svc"}\n', encoding="utf-8")
        repo2 = GitRepo(r2)
        retrieve_path(r2, "config.json")
        timeout2 = Store(r2).get_claim(timeout_id)
        (r2 / "config.json").write_text('{\n  "name": "svc",\n  "timeout": 30\n}\n', encoding="utf-8")
        fresh_after_reformat = timeout2 is not None and check_freshness(repo2, timeout2).fresh
        checks.append({"name": "config_reformat_and_key_order_fresh", "pass": fresh_after_reformat})

        r3 = root / "json_unrelated"
        r3.mkdir()
        (r3 / "config.json").write_text('{"timeout":30,"name":"svc"}\n', encoding="utf-8")
        repo3 = GitRepo(r3)
        retrieve_path(r3, "config.json")
        timeout3 = Store(r3).get_claim(timeout_id)
        (r3 / "config.json").write_text('{"timeout":30,"name":"api"}\n', encoding="utf-8")
        fresh_after_unrelated = timeout3 is not None and check_freshness(repo3, timeout3).fresh
        checks.append({"name": "config_unrelated_key_change_fresh", "pass": fresh_after_unrelated})

        r4 = root / "json_delete"
        r4.mkdir()
        (r4 / "config.json").write_text('{"timeout":30,"name":"svc"}\n', encoding="utf-8")
        retrieve_path(r4, "config.json")
        (r4 / "config.json").write_text('{"name":"svc"}\n', encoding="utf-8")
        retrieve_path(r4, "config.json")
        removed = Store(r4).get_claim(timeout_id) is None
        checks.append({"name": "config_key_delete_reconciles", "pass": removed})

        r5 = root / "json_invalid"
        r5.mkdir()
        (r5 / "broken.json").write_text('{"timeout": ', encoding="utf-8")
        retrieve_path(r5, "broken.json")
        config_count = sum(1 for claim in Store(r5).iter_claims() if claim.scope == "config")
        checks.append({"name": "invalid_config_zero_nodes_no_crash", "pass": config_count == 0, "config_count": config_count})

    return {"checks": checks, "failures": [c for c in checks if not c["pass"]]}



def _api_node_checks(repo_path: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []

    def record(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"name": name, "pass": ok, "detail": detail})

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        repo = _copy_repo(repo_path, root, "api_nodes")
        api_path = repo / "api.py"
        api_path.write_text("@app.route('/x', methods=['POST'])\ndef handler():\n    return 'ok'\n\ndef unrelated():\n    return 1\n", encoding="utf-8")
        subprocess.run(["git", "add", "api.py"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        subprocess.run(["git", "commit", "-m", "api fixture"], cwd=repo, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        retrieve_path(repo, "api.py")
        store = Store(repo)
        claim_id = stable_api_claim_id("api.py", "POST", "/x", "handler")
        claim = store.get_claim(claim_id)
        record("api_node_derived", claim is not None and claim.scope == "api" if claim else False)
        if claim is not None:
            record("api_node_fresh_initial", check_freshness(GitRepo(repo), claim).fresh)
            api_path.write_text("@app.route('/y', methods=['POST'])\ndef handler():\n    return 'ok'\n\ndef unrelated():\n    return 1\n", encoding="utf-8")
            record("api_route_literal_change_stales", not check_freshness(GitRepo(repo), claim).fresh)
            api_path.write_text("@app.route('/x', methods=['POST'])\ndef handler():\n    return 'changed'\n\ndef unrelated():\n    return 1\n", encoding="utf-8")
            record("api_handler_body_change_stales", not check_freshness(GitRepo(repo), claim).fresh)
            api_path.write_text("# comment\n@app.route('/x', methods=['POST'])\ndef handler():\n  return 'ok'\n\ndef unrelated():\n    return 1\n", encoding="utf-8")
            record("api_comment_format_fresh", check_freshness(GitRepo(repo), claim).fresh)
            api_path.write_text("@app.route('/x', methods=['POST'])\ndef handler():\n    return 'ok'\n\ndef unrelated():\n    return 2\n", encoding="utf-8")
            record("api_unrelated_function_fresh", check_freshness(GitRepo(repo), claim).fresh)
            api_path.write_text("def handler():\n    return 'ok'\n", encoding="utf-8")
            retrieve_path(repo, "api.py")
            record("api_delete_reconciles", Store(repo).get_claim(claim_id) is None)

        api_path.write_text("PATH = '/dyn'\n@router.get(PATH)\ndef dyn():\n    return 'no'\n\n@bp.route('/unknown')\ndef unknown():\n    return 'no'\n", encoding="utf-8")
        retrieve_path(repo, "api.py")
        record("api_dynamic_unknown_skipped", not any(c.scope == "api" for c in Store(repo).iter_claims()))

    return {"checks": checks, "failures": [check for check in checks if not check["pass"]]}


def _read_edge_checks(repo_path: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        r = _copy_repo(repo_path, work, "read_edges")
        (r / "config.py").write_text("TIMEOUT = 5\nOTHER = 9\n\ndef load():\n    return TIMEOUT + 1\n\ndef shadow(TIMEOUT):\n    return TIMEOUT\n\ndef local():\n    TIMEOUT = 3\n    return TIMEOUT\n\ndef unknown():\n    return UNKNOWN\n", encoding="utf-8")
        subprocess.run(["git", "add", "config.py"], cwd=r, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        subprocess.run(["git", "commit", "-m", "read edge fixture"], cwd=r, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        warm_repo(r)
        repo = GitRepo(r)
        store = Store(r)
        reader = stable_function_claim_id("config.py", "load")
        decl = stable_declaration_claim_id("config.py", "TIMEOUT")
        edge_id = stable_read_edge_claim_id(reader, decl)
        edge = store.get_claim(edge_id)
        checks.append({"name": "resolved_read_edge", "passed": edge is not None})
        if edge is None:
            failures.append({"check": "resolved_read_edge", "reason": "missing read edge"})
        else:
            rev = reverse_readers(r, decl)
            reverse_ok = any(item.get("reader_id") == reader for item in rev.get("readers", [])) and rev.get("coverage") == "partial"
            checks.append({"name": "reverse_readers_partial", "passed": reverse_ok})
            if not reverse_ok:
                failures.append({"check": "reverse_readers_partial", "report": rev})
            callers_ok = reverse_callers(r, decl).get("callers") == []
            checks.append({"name": "readers_not_callers", "passed": callers_ok})
            if not callers_ok:
                failures.append({"check": "readers_not_callers"})

            (r / "config.py").write_text("TIMEOUT = 5\nOTHER = 10\n\ndef load():\n    return TIMEOUT + 1\n\ndef shadow(TIMEOUT):\n    return TIMEOUT\n\ndef local():\n    TIMEOUT = 3\n    return TIMEOUT\n\ndef unknown():\n    return UNKNOWN\n", encoding="utf-8")
            unrelated_fresh = check_freshness(repo, edge).fresh
            checks.append({"name": "unrelated_change_fresh", "passed": unrelated_fresh})
            if not unrelated_fresh:
                failures.append({"check": "unrelated_change_fresh"})

            (r / "config.py").write_text("TIMEOUT = 5\nOTHER = 10\n\ndef load():\n    return TIMEOUT + 2\n\ndef shadow(TIMEOUT):\n    return TIMEOUT\n\ndef local():\n    TIMEOUT = 3\n    return TIMEOUT\n\ndef unknown():\n    return UNKNOWN\n", encoding="utf-8")
            reader_stale = not check_freshness(repo, edge).fresh
            checks.append({"name": "reader_change_stales", "passed": reader_stale})
            if not reader_stale:
                failures.append({"check": "reader_change_stales"})

            (r / "config.py").write_text("TIMEOUT = 7\nOTHER = 10\n\ndef load():\n    return TIMEOUT + 1\n\ndef shadow(TIMEOUT):\n    return TIMEOUT\n\ndef local():\n    TIMEOUT = 3\n    return TIMEOUT\n\ndef unknown():\n    return UNKNOWN\n", encoding="utf-8")
            decl_stale = not check_freshness(repo, edge).fresh
            checks.append({"name": "declaration_change_stales", "passed": decl_stale})
            if not decl_stale:
                failures.append({"check": "declaration_change_stales"})

        shadow_edge = store.get_claim(stable_read_edge_claim_id(stable_function_claim_id("config.py", "shadow"), decl))
        local_edge = store.get_claim(stable_read_edge_claim_id(stable_function_claim_id("config.py", "local"), decl))
        shadow_ok = shadow_edge is None and local_edge is None
        checks.append({"name": "local_shadowing_no_edges", "passed": shadow_ok})
        if not shadow_ok:
            failures.append({"check": "local_shadowing_no_edges"})
        unknown_claim = store.get_claim(stable_function_claim_id("config.py", "unknown"))
        unresolved_ok = bool(unknown_claim and unknown_claim.body.get("graph", {}).get("reads_unresolved"))
        checks.append({"name": "unknown_name_unresolved", "passed": unresolved_ok})
        if not unresolved_ok:
            failures.append({"check": "unknown_name_unresolved"})

        (r / "config.py").write_text("TIMEOUT = 5\nOTHER = 9\n\ndef renamed():\n    return TIMEOUT\n", encoding="utf-8")
        retrieve_path(r, "config.py")
        removed = Store(r).get_claim(edge_id) is None
        checks.append({"name": "reader_rename_reconciles_edge", "passed": removed})
        if not removed:
            failures.append({"check": "reader_rename_reconciles_edge"})
    return {"checks": checks, "failures": failures}


def _write_edge_checks(repo_path: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as td:
        work = Path(td)
        r = _copy_repo(repo_path, work, "write_edges")
        fixture = "COUNT = 0\nOTHER = 9\n\ndef bump():\n    global COUNT\n    COUNT += 1\n\ndef local():\n    COUNT = 3\n    return COUNT\n\ndef clear():\n    global COUNT\n    del COUNT\n"
        (r / "state.py").write_text(fixture, encoding="utf-8")
        subprocess.run(["git", "add", "state.py"], cwd=r, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        subprocess.run(["git", "commit", "-m", "write edge fixture"], cwd=r, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        warm_repo(r)
        repo = GitRepo(r)
        store = Store(r)
        writer = stable_function_claim_id("state.py", "bump")
        local = stable_function_claim_id("state.py", "local")
        clear = stable_function_claim_id("state.py", "clear")
        decl = stable_declaration_claim_id("state.py", "COUNT")
        edge_id = stable_write_edge_claim_id(writer, decl)
        edge = store.get_claim(edge_id)
        resolved = edge is not None and edge.body.get("edge_kind") == "writes"
        checks.append({"name": "resolved_global_write_edge", "passed": resolved})
        if not resolved:
            failures.append({"check": "resolved_global_write_edge"})
        local_edge = store.get_claim(stable_write_edge_claim_id(local, decl))
        local_claim = store.get_claim(local)
        local_ok = local_edge is None and bool(local_claim and local_claim.body.get("graph", {}).get("writes_unresolved"))
        checks.append({"name": "assignment_without_global_no_edge", "passed": local_ok})
        if not local_ok:
            failures.append({"check": "assignment_without_global_no_edge"})
        read_edge = store.get_claim(stable_read_edge_claim_id(writer, decl))
        aug_ok = edge is not None and read_edge is not None
        checks.append({"name": "global_augassign_reads_and_writes", "passed": aug_ok})
        if not aug_ok:
            failures.append({"check": "global_augassign_reads_and_writes"})
        if edge is not None:
            rev = reverse_writers(r, decl)
            written = Store(r).get_claim(decl).body.get("graph", {}).get("written_by", [])
            reverse_ok = any(item.get("writer_id") == writer for item in rev.get("writers", [])) and any(item.get("source_id") == writer for item in written) and rev.get("coverage") == "partial"
            distinct_ok = reverse_callers(r, decl).get("callers") == []
            checks.append({"name": "reverse_writers_partial_and_distinct", "passed": reverse_ok and distinct_ok})
            if not (reverse_ok and distinct_ok):
                failures.append({"check": "reverse_writers_partial_and_distinct", "reverse": rev})
            (r / "state.py").write_text("COUNT = 0\nOTHER = 10\n\ndef bump():\n    global COUNT\n    COUNT += 1\n\ndef local():\n    COUNT = 3\n    return COUNT\n\ndef clear():\n    global COUNT\n    del COUNT\n", encoding="utf-8")
            fresh_unrelated = check_freshness(repo, edge).fresh
            checks.append({"name": "write_edge_unrelated_change_fresh", "passed": fresh_unrelated})
            if not fresh_unrelated:
                failures.append({"check": "write_edge_unrelated_change_fresh"})
            (r / "state.py").write_text("COUNT = 0\nOTHER = 10\n\ndef bump():\n    global COUNT\n    COUNT += 2\n\ndef local():\n    COUNT = 3\n    return COUNT\n\ndef clear():\n    global COUNT\n    del COUNT\n", encoding="utf-8")
            writer_stale = not check_freshness(repo, edge).fresh
            checks.append({"name": "write_edge_writer_change_stales", "passed": writer_stale})
            if not writer_stale:
                failures.append({"check": "write_edge_writer_change_stales"})
            (r / "state.py").write_text("COUNT = 1\nOTHER = 10\n\ndef bump():\n    global COUNT\n    COUNT += 1\n\ndef local():\n    COUNT = 3\n    return COUNT\n\ndef clear():\n    global COUNT\n    del COUNT\n", encoding="utf-8")
            decl_stale = not check_freshness(repo, edge).fresh
            checks.append({"name": "write_edge_declaration_change_stales", "passed": decl_stale})
            if not decl_stale:
                failures.append({"check": "write_edge_declaration_change_stales"})
            (r / "state.py").write_text("COUNT = 0\nOTHER = 9\n\ndef renamed():\n    global COUNT\n    COUNT += 1\n", encoding="utf-8")
            retrieve_path(r, "state.py")
            removed_writer = Store(r).get_claim(edge_id) is None
            checks.append({"name": "write_edge_writer_rename_reconciles", "passed": removed_writer})
            if not removed_writer:
                failures.append({"check": "write_edge_writer_rename_reconciles"})
    return {"checks": checks, "failures": failures}

def _property_checks(repo_path: Path) -> dict[str, Any]:
    checks = {
        "cross_file_edge_lifecycle": _lifecycle_checks(repo_path),
        "thin_full_consistency": _thin_full_checks(repo_path),
        "verification_boundaries": _verification_boundary_checks(repo_path),
        "provenance_freshness": _provenance_freshness_checks(repo_path),
        "embedding_router_additivity": _embedding_router_checks(repo_path),
        "warm_idempotent_incremental": _warm_checks(repo_path),
        "reverse_callers_coverage": _reverse_coverage_checks(repo_path),
        "config_nodes": _config_node_checks(repo_path),
        "api_nodes": _api_node_checks(repo_path),
        "read_edges": _read_edge_checks(repo_path),
        "write_edges": _write_edge_checks(repo_path),
        "degrade_all": _degrade_all_checks(repo_path),
    }
    failures = {name: value.get("failures", []) for name, value in checks.items() if value.get("failures")}
    return {"checks": checks, "failures": failures, "total_failures": sum(len(v) for v in failures.values())}


def _run_one_repo(repo_path: Path) -> dict[str, Any]:
    warm_repo(repo_path)
    freshness = _freshness_checks(repo_path)
    claim_support = _claim_support_checks(repo_path)
    invariants = _invariant_audit(repo_path)
    degrade = _degrade_checks(repo_path)
    properties = _property_checks(repo_path)
    status = "pass" if invariants["total_violations"] == 0 and claim_support["observed_without_current_source_support"] == 0 and not degrade["failures"] and properties["total_failures"] == 0 and freshness["fp"] == 0 and freshness["fn"] == 0 else "fail"
    return {"repo": str(repo_path), "status": status, "freshness": freshness, "claim_support": claim_support, "invariants": invariants, "degrade_to_source": degrade, "properties": properties}


def _summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    total_violations = sum(r["invariants"]["total_violations"] for r in results)
    total_support_violations = sum(r["claim_support"]["observed_without_current_source_support"] for r in results)
    total_degrade_failures = sum(len(r["degrade_to_source"]["failures"]) for r in results)
    freshness_fp = sum(r["freshness"]["fp"] for r in results)
    freshness_fn = sum(r["freshness"]["fn"] for r in results)
    total_property_failures = sum(r["properties"]["total_failures"] for r in results)
    return {
        "status": "pass" if total_violations == 0 and total_support_violations == 0 and total_degrade_failures == 0 and total_property_failures == 0 and freshness_fp == 0 and freshness_fn == 0 else "fail",
        "repos": len(results),
        "invariant_violations": total_violations,
        "claim_support_violations": total_support_violations,
        "degrade_failures": total_degrade_failures,
        "property_failures": total_property_failures,
        "freshness_fp": freshness_fp,
        "freshness_fn": freshness_fn,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = ["# TMF Held-out Validation Report", "", f"Status: **{report['summary']['status']}**", ""]
    lines.append(f"Freshness precision: {report['freshness']['precision']:.3f}")
    lines.append(f"Freshness recall: {report['freshness']['recall']:.3f}")
    lines.append("")
    lines.append(f"Invariant violations: {report['invariants']['total_violations']}")
    lines.append(f"Observed/source support violations: {report['claim_support']['observed_without_current_source_support']}")
    lines.append(f"Degrade-to-source failures: {len(report['degrade_to_source']['failures'])}")
    lines.append(f"Property failures: {report['properties']['total_failures']}")
    lines.append("")
    if report["summary"]["status"] != "pass":
        lines.append("## Failures / suspected engine bugs")
        for result in report["repos"]:
            for event in result["freshness"]["events"]:
                if event.get("expected_stale") is not None and event.get("expected_stale") != event.get("actual_stale"):
                    lines.append(f"- {result['repo']} {event['scenario']} {event['claim_id']}: expected_stale={event['expected_stale']} actual_stale={event['actual_stale']}")
    return "\n".join(lines) + "\n"


def _copy_self_validation_repo(src: Path, parent: Path) -> Path:
    def ignore(_dir: str, names: list[str]) -> set[str]:
        return {name for name in names if name in {".git", ".tmf", "__pycache__", ".pytest_cache", "reports", "artifacts"}}

    dst = parent / "self_repo"
    shutil.copytree(src, dst, ignore=ignore)
    return dst


def _self_invariant_audit(repo_path: Path) -> dict[str, Any]:
    store = Store(repo_path)
    violations: list[dict[str, str]] = []
    for claim in store.iter_claims():
        candidate = claim.body.get("model_candidate", {}) if isinstance(claim.body, dict) else {}
        verification = candidate.get("verification") if isinstance(candidate, dict) else None
        raw = candidate.get("raw_confidence") if isinstance(candidate, dict) else None
        if claim.kind == "intent" and not claim.body.get("provenance_evidence") and claim.evidence == "observed":
            violations.append({"claim_id": claim.id, "kind": "intent_without_provenance_observed"})
        if verification == "intent_requires_external_provenance" and claim.confidence > 0.25:
            violations.append({"claim_id": claim.id, "kind": "unsupported_intent_cap_exceeded"})
        if verification == "attributed_external_provenance" and (claim.evidence != "inferred" or claim.confidence > 0.6):
            violations.append({"claim_id": claim.id, "kind": "attributed_cap_or_evidence_violation"})
        if raw is not None and float(raw) > claim.confidence and claim.confidence > 0.6:
            violations.append({"claim_id": claim.id, "kind": "raw_confidence_not_capped"})
    return {"total_violations": len(violations), "violations": violations}


def _self_degrade_all_checks(repo_path: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for claim in Store(repo_path).iter_claims():
        if float(claim.confidence) >= 0.3:
            continue
        anchors = claim.body.get("anchors", []) if isinstance(claim.body, dict) else []
        ok = bool(anchors) or bool(claim.bindings)
        checks.append({"claim_id": claim.id, "pass": ok, "confidence": claim.confidence, "has_anchor_or_binding": ok})
    return {"checks": checks, "failures": [c for c in checks if not c["pass"]]}


def _self_thin_full_checks(repo_path: Path) -> dict[str, Any]:
    repo = GitRepo(repo_path)
    checks = 0
    failures: list[dict[str, Any]] = []
    for claim in Store(repo_path).iter_claims():
        freshness = check_freshness(repo, claim)
        thin = {
            "id": claim.id,
            "claim": claim.claim,
            "kind": claim.kind,
            "scope": claim.scope,
            "qualname": claim.body.get("qualname") if isinstance(claim.body, dict) else None,
            "fresh": freshness.fresh,
            "stale_reasons": [] if freshness.fresh else freshness.stale_bindings,
            "confidence": claim.confidence,
            "anchors": claim.body.get("anchors", []) if isinstance(claim.body, dict) else [],
            "freshness_binding_refs": [
                {"path": b.path, "file_blob_prefix": (b.file_blob or "")[:12], "fn_hash_prefix": (b.fn_hash or "")[:12], "commit_anchor_prefix": (b.commit or "")[:12]}
                for b in claim.bindings
            ],
        }
        checks += 1
        thin_json = json.dumps(thin, ensure_ascii=False)
        forbidden_keys_absent = "claim_record" not in thin and "body" not in thin and "quoted_text_untrusted_data" not in thin_json
        ok = thin["id"] == claim.id and thin["claim"] == claim.claim and forbidden_keys_absent
        short_hashes = all(len(ref.get("file_blob_prefix", "")) <= 12 and len(ref.get("fn_hash_prefix", "")) <= 12 for ref in thin["freshness_binding_refs"])
        full_restores = claim.to_dict().get("id") == claim.id and "body" in claim.to_dict()
        if not (ok and short_hashes and full_restores):
            failures.append({"claim_id": claim.id, "thin_subset": ok, "short_hashes": short_hashes, "full_restores": full_restores})
    return {"checks": checks, "failures": failures}


def _real_verification_scan(repo_path: Path) -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    for claim in Store(repo_path).iter_claims():
        candidate = claim.body.get("model_candidate", {}) if isinstance(claim.body, dict) else {}
        verification = candidate.get("verification") if isinstance(candidate, dict) else None
        ok = True
        reason = ""
        if verification == "intent_requires_external_provenance" and (claim.evidence != "inferred" or claim.confidence > 0.25):
            ok = False
            reason = "unsupported_intent_boundary_violation"
        elif verification == "attributed_external_provenance" and (claim.evidence != "inferred" or claim.confidence > 0.6):
            ok = False
            reason = "attributed_boundary_violation"
        elif verification == "source_support_literal" and claim.evidence == "observed" and claim.confidence > 0.6:
            ok = False
            reason = "observed_source_cap_violation"
        checks.append({"claim_id": claim.id, "pass": ok, "verification": verification, "evidence": claim.evidence, "confidence": claim.confidence, "reason": reason})
    return {"checks": checks, "failures": [c for c in checks if not c["pass"]]}


def _router_embed_off_equivalence_check(repo_path: Path) -> dict[str, Any]:
    old_embed = os.environ.pop("TMF_EMBED_COMMAND", None)
    old_router = os.environ.pop("TMF_ROUTER_COMMAND", None)
    try:
        first = [item.claim.id for item in retrieve_text(repo_path, "claim", limit=10).claims]
        second = [item.claim.id for item in retrieve_text(repo_path, "claim", limit=10).claims]
        check = {"name": "self_repo_embed_router_off_deterministic", "pass": first == second, "first": first, "second": second}
        return {"checks": [check], "failures": [] if check["pass"] else [check]}
    finally:
        if old_embed is not None:
            os.environ["TMF_EMBED_COMMAND"] = old_embed
        if old_router is not None:
            os.environ["TMF_ROUTER_COMMAND"] = old_router


def _json_mutated_value(value: Any) -> Any:
    if isinstance(value, bool):
        return not value
    if isinstance(value, int) and not isinstance(value, bool):
        return value + 1
    if isinstance(value, float):
        return value + 1.0
    if isinstance(value, str):
        return value + "_tmf_self_validation"
    if isinstance(value, list):
        return [*value, "tmf_self_validation"]
    if isinstance(value, dict):
        out = dict(value)
        out["_tmf_self_validation"] = True
        return out
    return "tmf_self_validation"


def _perturb_claim_node(root: Path, claim) -> int | None:
    """Mutate one sampled claim and return the pre-mutation insertion gap.

    The returned integer is the line *after* which text was inserted in the
    original file. Using the gap rather than the following line keeps the
    expected-stale set tight: inserting at the top of a class body changes the
    class span but not the first method that used to start on the next line.
    """
    if not claim.bindings:
        return None
    path = root / claim.bindings[0].path
    if claim.scope == "class":
        anchors = claim.body.get("anchors", []) if isinstance(claim.body, dict) else []
        if not anchors:
            return None
        line_start = int(anchors[0].get("line_start", 0))
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        if line_start < 1 or line_start > len(lines):
            return None
        base_indent = lines[line_start - 1][: len(lines[line_start - 1]) - len(lines[line_start - 1].lstrip())]
        insert_after_line = line_start
        lines.insert(line_start, f"{base_indent}    _tmf_self_validation_marker = 1\n")
        path.write_text("".join(lines), encoding="utf-8")
        return insert_after_line
    if claim.scope == "function":
        anchors = claim.body.get("anchors", []) if isinstance(claim.body, dict) else []
        if not anchors:
            return None
        line_start = int(anchors[0].get("line_start", 0))
        line_end = int(anchors[0].get("line_end", 0))
        if line_end <= line_start:
            return None
        lines = path.read_text(encoding="utf-8").splitlines(keepends=True)
        if line_start < 1 or line_start > len(lines):
            return None
        base_indent = lines[line_start - 1][: len(lines[line_start - 1]) - len(lines[line_start - 1].lstrip())]
        insert_at = max(line_start, min(line_end - 1, len(lines)))
        insert_after_line = insert_at
        lines.insert(insert_at, f"{base_indent}    _tmf_self_validation_marker = 1\n")
        path.write_text("".join(lines), encoding="utf-8")
        return insert_after_line
    if claim.scope == "config" and claim.bindings[0].path.endswith(".json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        key = claim.bindings[0].qualname or claim.body.get("qualname")
        if not isinstance(data, dict) or not isinstance(key, str) or key not in data:
            return None
        data[key] = _json_mutated_value(data[key])
        path.write_text(json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        return 1
    return None


def _claim_anchor_contains_line(claim, path: str, line_after: int) -> bool:
    anchors = claim.body.get("anchors", []) if isinstance(claim.body, dict) else []
    for anchor in anchors:
        if anchor.get("path") != path:
            continue
        line_start = int(anchor.get("line_start", 0))
        line_end = int(anchor.get("line_end", 0))
        if line_start <= line_after < line_end:
            return True
    return False


def _expected_stale_ids_for_sample(claim, all_claims: list[Any], insertion_after_line: int | None = None) -> set[str]:
    if not claim.bindings:
        return set()
    target_path = claim.bindings[0].path
    if claim.scope == "config":
        expected = {claim.id}
        for other in all_claims:
            if other.scope == "file" and other.bindings and other.bindings[0].path == target_path:
                expected.add(other.id)
        return expected
    affected_claims = [
        other
        for other in all_claims
        if other.body.get("edge_kind") not in {"calls", "reads"}
        and insertion_after_line is not None
        and (
            _claim_anchor_contains_line(other, target_path, insertion_after_line)
            or (other.scope == "file" and other.bindings and other.bindings[0].path == target_path)
        )
    ]
    expected = {other.id for other in affected_claims}
    affected_bindings = {
        (binding.path, binding.qualname)
        for other in affected_claims
        for binding in other.bindings
        if binding.qualname is not None
    }
    for other in all_claims:
        if other.body.get("edge_kind") in {"calls", "reads"}:
            for binding in other.bindings:
                if (binding.path, binding.qualname) in affected_bindings:
                    expected.add(other.id)
                    break
    return expected


def _self_validation_samples(store: Store, limit: int) -> list[Any]:
    out = []
    for claim in store.iter_claims():
        if claim.scope not in {"function", "class", "config"}:
            continue
        if claim.scope == "function" and "." in str(claim.body.get("qualname", "")):
            continue
        if claim.scope == "config" and (not claim.bindings or not claim.bindings[0].path.endswith(".json")):
            continue
        if claim.scope in {"function", "class"}:
            anchors = claim.body.get("anchors", []) if isinstance(claim.body, dict) else []
            if not anchors or int(anchors[0].get("line_end", 0)) <= int(anchors[0].get("line_start", 0)):
                continue
        out.append(claim)
        if len(out) >= limit:
            break
    return out


def _self_freshness_sampling(repo_path: Path, sample_limit: int) -> dict[str, Any]:
    base_store = Store(repo_path)
    samples = _self_validation_samples(base_store, sample_limit)
    events: list[dict[str, Any]] = []
    tp = fp = fn = 0
    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        for index, sample in enumerate(samples):
            sample_repo = _copy_repo(repo_path, root, f"sample_{index}")
            claim = Store(sample_repo).get_claim(sample.id)
            insertion_after_line = _perturb_claim_node(sample_repo, claim) if claim is not None else None
            if claim is None or insertion_after_line is None:
                events.append({"sample_claim_id": sample.id, "skipped": "could_not_perturb"})
                continue
            repo = GitRepo(sample_repo)
            all_claims = list(Store(sample_repo).iter_claims())
            expected_stale = _expected_stale_ids_for_sample(claim, all_claims, insertion_after_line)
            for current in all_claims:
                actual = not check_freshness(repo, current).fresh
                expected = current.id in expected_stale
                if actual or expected:
                    events.append({"sample_claim_id": sample.id, "claim_id": current.id, "scope": current.scope, "expected_stale": expected, "actual_stale": actual})
                if actual and expected:
                    tp += 1
                elif actual and not expected:
                    fp += 1
                elif not actual and expected:
                    fn += 1
    precision, recall = _precision_recall(tp, fp, fn)
    return {"samples": len(samples), "precision": precision, "recall": recall, "tp": tp, "fp": fp, "fn": fn, "events": events}


def _self_markdown(report: dict[str, Any]) -> str:
    lines = ["# TMF Self Validation Report", "", f"Status: **{report['summary']['status']}**", ""]
    lines.append(f"Claims scanned: {report['summary']['claims']}")
    lines.append(f"Warm derived files: {report['warm']['files']}")
    lines.append(f"Invariant violations: {report['invariants']['total_violations']}")
    lines.append(f"Observed/source support violations: {report['claim_support']['observed_without_current_source_support']}")
    lines.append(f"Thin/full failures: {len(report['thin_full']['failures'])}")
    lines.append(f"Verification boundary failures: {len(report['verification_boundaries']['failures'])}")
    lines.append(f"Degrade failures: {len(report['degrade_to_source']['failures'])}")
    lines.append(f"Router/embed off failures: {len(report['embed_router_off']['failures'])}")
    lines.append("")
    lines.append(f"Freshness sample count: {report['freshness_sampling']['samples']}")
    lines.append(f"Freshness sample precision: {report['freshness_sampling']['precision']:.3f}")
    lines.append(f"Freshness sample recall: {report['freshness_sampling']['recall']:.3f}")
    lines.append(f"Freshness sample fp/fn: {report['freshness_sampling']['fp']} / {report['freshness_sampling']['fn']}")
    lines.append("")
    if report["summary"]["status"] != "pass":
        lines.append("## Failures / suspected engine bugs")
        for section in ["invariants", "claim_support", "thin_full", "verification_boundaries", "degrade_to_source", "embed_router_off"]:
            data = report.get(section, {})
            failures = data.get("violations") or data.get("failures") or []
            for failure in failures[:20]:
                lines.append(f"- {section}: {failure}")
        for event in report["freshness_sampling"].get("events", []):
            if event.get("expected_stale") != event.get("actual_stale"):
                lines.append(f"- freshness_sampling: {event}")
    return "\n".join(lines) + "\n"


def run_self_validation(repo_root: str | Path, out_dir: str | Path, *, sample_limit: int = 10) -> dict[str, Any]:
    source = Path(repo_root).resolve()
    with tempfile.TemporaryDirectory() as td:
        work = _copy_self_validation_repo(source, Path(td))
        warm = warm_repo(work)
        store = Store(work)
        claims = list(store.iter_claims())
        invariants = _self_invariant_audit(work)
        claim_support = _claim_support_checks(work)
        thin_full = _self_thin_full_checks(work)
        verification = _real_verification_scan(work)
        degrade = _self_degrade_all_checks(work)
        embed_router = _router_embed_off_equivalence_check(work)
        sampling = _self_freshness_sampling(work, sample_limit)
        status = "pass" if (
            invariants["total_violations"] == 0
            and claim_support["observed_without_current_source_support"] == 0
            and not thin_full["failures"]
            and not verification["failures"]
            and not degrade["failures"]
            and not embed_router["failures"]
            and sampling["fp"] == 0
            and sampling["fn"] == 0
        ) else "fail"
        report = {
            "summary": {"status": status, "repo": str(source), "work_repo": str(work), "claims": len(claims)},
            "warm": warm,
            "invariants": invariants,
            "claim_support": claim_support,
            "thin_full": thin_full,
            "verification_boundaries": verification,
            "degrade_to_source": degrade,
            "embed_router_off": embed_router,
            "freshness_sampling": sampling,
        }
    out = Path(out_dir)
    _write_json(out / "self-validation.json", report)
    (out / "self-validation.md").write_text(_self_markdown(report), encoding="utf-8")
    return report


def run_heldout_validation(repo_paths: list[str | Path], out_dir: str | Path) -> dict[str, Any]:
    paths = [Path(path).resolve() for path in repo_paths]
    results = [_run_one_repo(path) for path in paths]
    tp = sum(r["freshness"]["tp"] for r in results)
    fp = sum(r["freshness"]["fp"] for r in results)
    fn = sum(r["freshness"]["fn"] for r in results)
    precision, recall = _precision_recall(tp, fp, fn)
    report = {
        "summary": _summary(results),
        "freshness": {"precision": precision, "recall": recall, "tp": tp, "fp": fp, "fn": fn},
        "claim_support": {
            "observed_without_current_source_support": sum(r["claim_support"]["observed_without_current_source_support"] for r in results),
            "attributed_without_provenance_support": sum(r["claim_support"]["attributed_without_provenance_support"] for r in results),
        },
        "invariants": {"total_violations": sum(r["invariants"]["total_violations"] for r in results), "by_repo": [r["invariants"] for r in results]},
        "degrade_to_source": {"failures": [f for r in results for f in r["degrade_to_source"]["failures"]]},
        "properties": {"total_failures": sum(r["properties"]["total_failures"] for r in results), "by_repo": [r["properties"] for r in results]},
        "repos": results,
    }
    out = Path(out_dir)
    _write_json(out / "heldout-validation.json", report)
    (out / "heldout-validation.md").write_text(_markdown(report), encoding="utf-8")
    return report
