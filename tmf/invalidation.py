from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import subprocess
from typing import Any

from .git import GitRepo
from .schema import module_top_level_invalidation_status
from .timeout import derive_claims_for_path_with_timeout

CODE_SUFFIXES = {".py"}


def _changed_files(repo_root: Path, old_rev: str, new_rev: str) -> list[str]:
    output = GitRepo(repo_root).run("diff", "--name-only", "--diff-filter=ACDMRT", old_rev, new_rev)
    return sorted({p.strip() for p in output.splitlines() if p.strip() and Path(p.strip()).suffix in CODE_SUFFIXES})


def _source_at_rev(repo_root: Path, rev: str, rel_path: str) -> str | None:
    proc = subprocess.run(["git", "show", f"{rev}:{rel_path}"], cwd=repo_root, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return proc.stdout if proc.returncode == 0 else None


def _snapshot(repo_root: Path, rev: str, rel_path: str) -> tuple[str | None, str | None]:
    repo = GitRepo(repo_root)
    source = _source_at_rev(repo_root, rev, rel_path)
    if source is None:
        return None, None
    blob = repo.run("rev-parse", f"{rev}:{rel_path}", check=False) or None
    return source, blob


def _function_claims(claims: list[Any]) -> dict[str, Any]:
    return {
        (claim.body.get("qualname") if isinstance(claim.body, dict) else None) or claim.bindings[0].qualname: claim
        for claim in claims
        if claim.scope == "function" and claim.bindings and ((claim.body.get("qualname") if isinstance(claim.body, dict) else None) or claim.bindings[0].qualname)
    }


def _claim_anchor(claim: Any) -> dict[str, Any] | None:
    body = claim.body if isinstance(claim.body, dict) else {}
    anchors = body.get("anchors")
    if isinstance(anchors, list) and anchors and isinstance(anchors[0], dict):
        return {"line_start": anchors[0].get("line_start"), "line_end": anchors[0].get("line_end")}
    return None


def _module_contract(claim: Any) -> dict[str, Any] | None:
    contract = getattr(claim, "module_top_level_contract", None)
    anchor = getattr(contract, "anchor", None)
    if claim is None or claim.scope != "module_top_level" or contract is None or anchor is None:
        return None
    return {"schema_version": contract.schema_version, "region_id": contract.region_id, "anchor": {"start": anchor.start, "end": anchor.end}}


def _module_top_levels(claims: list[Any]) -> dict[str, Any]:
    out = {}
    for claim in claims:
        contract = _module_contract(claim)
        if contract:
            out[contract["region_id"]] = claim
    return out


def _binding_hash(claim: Any) -> str | None:
    return claim.bindings[0].fn_hash if claim and claim.bindings else None


def _manifest(repo_root: Path, old_rev: str, new_rev: str, *, per_file_timeout: float) -> dict[str, Any]:
    paths = _changed_files(repo_root, old_rev, new_rev)
    return {"schema_version": "tmf.invalidation_manifest.v1", "kind": "code_cognition_invalidation_manifest",
            "generated_at": datetime.now(timezone.utc).isoformat(), "repo_root": str(repo_root), "old_rev": old_rev,
            "new_rev": new_rev, "changed_files": paths, "scanned_files": [], "entries": [], "skipped": [],
            "mode": "dry_run", "derive_timeout_sec": per_file_timeout, "cache_updated": False,
            "summary": {"files_changed": len(paths), "files_scanned": 0, "changed": 0, "deleted": 0, "added": 0,
                        "module_top_level_changed": 0, "module_top_level_removed": 0, "module_top_level_added": 0, "skipped": 0}}


def diff_revisions(repo_root: str | Path, old_rev: str, new_rev: str, *, per_file_timeout: float = 60) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    manifest = _manifest(root, old_rev, new_rev, per_file_timeout=per_file_timeout)
    repo = GitRepo(root)
    for path in manifest["changed_files"]:
        manifest["scanned_files"].append(path)
        old_source, old_blob = _snapshot(root, old_rev, path)
        new_source, new_blob = _snapshot(root, new_rev, path)
        old_out = None if old_source is None else derive_claims_for_path_with_timeout(repo, path, per_file_timeout=per_file_timeout, source=old_source, blob=old_blob, head="dry-run-blob")
        new_out = None if new_source is None else derive_claims_for_path_with_timeout(repo, path, per_file_timeout=per_file_timeout, source=new_source, blob=new_blob, head="dry-run-blob")
        skipped = next((out.skipped for out in (old_out, new_out) if out and out.skipped), None)
        if skipped:
            manifest["skipped"].append(skipped.to_dict())
            continue
        old_claims = [] if old_out is None else old_out.claims
        new_claims = [] if new_out is None else new_out.claims
        old_functions, new_functions = _function_claims(old_claims), _function_claims(new_claims)
        for name in sorted(set(old_functions) | set(new_functions)):
            old, new = old_functions.get(name), new_functions.get(name)
            oh, nh = _binding_hash(old), _binding_hash(new)
            if old and new and oh == nh: continue
            status, reason = (("changed", "fn_hash_mismatch") if old and new else ("deleted", "function_missing_in_current_code") if old else ("added", "new_function_not_present_in_old_tmf_cache"))
            manifest["entries"].append({"status": status, "file": path, "qualname": name, "old_fn_hash": oh, "new_fn_hash": nh, "reason": reason, "old_anchor": _claim_anchor(old) if old else None, "new_anchor": _claim_anchor(new) if new else None})
        old_top, new_top = _module_top_levels(old_claims), _module_top_levels(new_claims)
        for region in sorted(set(old_top) | set(new_top)):
            old, new = old_top.get(region), new_top.get(region)
            oh, nh = _binding_hash(old), _binding_hash(new)
            status = module_top_level_invalidation_status(old_present=old is not None, new_present=new is not None, hashes_equal=oh == nh)
            if status is None: continue
            reason = {"module_top_level_changed": "module_top_level_hash_mismatch", "module_top_level_removed": "module_top_level_region_missing_in_current_code", "module_top_level_added": "new_module_top_level_region_not_present_in_old_tmf_cache"}[status]
            oc, nc = _module_contract(old), _module_contract(new); contract = nc or oc
            manifest["entries"].append({"status": status, "file": path, "old_top_level_hash": oh, "new_top_level_hash": nh, "reason": reason, "old_anchor": _claim_anchor(old) if old else None, "new_anchor": _claim_anchor(new) if new else None, "module_top_level_contract": {"schema_version": contract["schema_version"], "region_id": contract["region_id"], "old_anchor": oc["anchor"] if oc else None, "new_anchor": nc["anchor"] if nc else None}})
    for entry in manifest["entries"]: manifest["summary"][entry["status"]] += 1
    manifest["summary"]["files_scanned"] = len(manifest["scanned_files"])
    manifest["summary"]["skipped"] = len(manifest["skipped"])
    return manifest
