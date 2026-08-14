#!/usr/bin/env python3
"""Generate a TMF invalidation manifest for a Git revision transition.

The current checkout's TMF cache is treated as the old cognition. Changed files
are derived from current source, compared at function scope, then reconciled
locally. This product adapter intentionally uses repository-local ``.tmf``;
external state-root support belongs in the engine, not in this hook.
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo
from tmf.store import Store


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, check=True, text=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE).stdout.strip()


def _functions(claims: list[Any]) -> dict[str, Any]:
    result = {}
    for claim in claims:
        if claim.scope != "function" or not claim.bindings:
            continue
        qualname = claim.body.get("qualname") or claim.bindings[0].qualname
        if qualname:
            result[str(qualname)] = claim
    return result


def _hash(claim: Any | None) -> str | None:
    return claim.bindings[0].fn_hash if claim and claim.bindings else None


def calibrate(repo_root: Path, old_rev: str, new_rev: str = "HEAD", *, update_cache: bool = True) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    changed = _git(repo_root, "diff", "--name-only", "--diff-filter=ACDMRT", old_rev, new_rev).splitlines()
    changed = sorted({p for p in changed if Path(p).suffix == ".py"})
    repo, store = GitRepo(repo_root), Store(repo_root)
    entries: list[dict[str, Any]] = []
    scanned: list[str] = []
    skipped: list[dict[str, str]] = []
    for rel in changed:
        old_claims = store.claims_for_path(rel)
        try:
            current = derive_claims_for_path(repo, rel) if (repo_root / rel).is_file() else []
        except Exception as exc:
            skipped.append({"kind": "skipped", "file": rel, "reason": "derive_failed", "detail": str(exc)})
            continue
        scanned.append(rel)
        before, after = _functions(old_claims), _functions(current)
        for name in sorted(set(before) | set(after)):
            old, new = before.get(name), after.get(name)
            if old and new and _hash(old) == _hash(new):
                continue
            status = "changed" if old and new else "deleted" if old else "added"
            entries.append({"status": status, "file": rel, "qualname": name,
                            "old_fn_hash": _hash(old), "new_fn_hash": _hash(new),
                            "reason": {"changed": "fn_hash_mismatch", "deleted": "function_missing_in_current_code", "added": "new_function_not_present_in_old_tmf_cache"}[status]})
        if update_cache:
            with store.write_lock():
                store.reconcile_path_claims(rel, current)
                store.reconcile_edge_claims_for_caller_path(rel, [c for c in current if c.body.get("edge_kind")])
                for claim in current:
                    store.put_claim(claim)
    summary = {key: sum(e["status"] == key for e in entries) for key in ("changed", "deleted", "added")}
    summary.update(files_changed=len(changed), files_scanned=len(scanned), skipped=len(skipped))
    return {"schema_version": "tmf.invalidation_manifest.v1", "kind": "code_cognition_invalidation_manifest",
            "generated_at": datetime.now(timezone.utc).isoformat(), "repo_root": str(repo_root),
            "old_rev": old_rev, "new_rev": new_rev, "changed_files": changed, "scanned_files": scanned,
            "entries": entries, "skipped": skipped, "cache_updated": update_cache and not skipped, "summary": summary}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="."); parser.add_argument("--old", required=True)
    parser.add_argument("--new", default="HEAD"); parser.add_argument("--output")
    parser.add_argument("--no-update-cache", action="store_true")
    args = parser.parse_args(); root = Path(_git(Path(args.repo).resolve(), "rev-parse", "--show-toplevel"))
    result = calibrate(root, args.old, args.new, update_cache=not args.no_update_cache)
    payload = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = Path(args.output); output = output if output.is_absolute() else root / output
        output.parent.mkdir(parents=True, exist_ok=True); output.write_text(payload, encoding="utf-8")
    print(payload, end=""); return 0

if __name__ == "__main__": raise SystemExit(main())
