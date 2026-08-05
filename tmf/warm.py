from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .freshness import check_freshness
from .git import GitRepo
from .schema import Claim
from .store import Store
from .timeout import DEFAULT_PER_FILE_TIMEOUT_SECONDS, derive_claims_for_path_with_timeout

WARM_MANIFEST = "warm_manifest.json"
REVERSE_INDEX = "reverse_callers.json"
COMPLETE_NOTE = "Known callers from fully warmed files; complete for the current warm manifest."
PARTIAL_NOTE = "Known callers from already-derived files only; not a complete blast radius."


def _tmf_file(store: Store, name: str) -> Path:
    store.init()
    return store.root / name


def _tmf_file_read_only(store: Store, name: str) -> Path:
    store.require_initialized()
    return store.root / name


def _load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _write_json(path: Path, data: Any) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


_WARMABLE_SUFFIXES = {".py", ".json", ".toml"}


def _warmable_paths(repo: GitRepo) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for path in sorted(repo.root.rglob("*")):
        if path.suffix not in _WARMABLE_SUFFIXES or not path.is_file():
            continue
        rel = path.relative_to(repo.root).as_posix()
        if rel.startswith(".git/") or rel.startswith(".tmf/"):
            continue
        if rel not in seen:
            seen.add(rel)
            out.append(rel)
    return sorted(out)


def _put_claims(store: Store, claims: list[Claim]) -> None:
    for claim in claims:
        store.put_claim(claim)


def _replace_path_claims(store: Store, relpath: str, claims: list[Claim]) -> None:
    _put_claims(store, claims)
    store.reconcile_path_claims(relpath, [c for c in claims if c.body.get("edge_kind") not in {"calls", "reads", "writes"}])
    store.reconcile_edge_claims_for_caller_path(relpath, [c for c in claims if c.body.get("edge_kind") in {"calls", "reads", "writes"}])


def _claims_for_path_fresh(repo: GitRepo, store: Store, relpath: str) -> bool:
    claims = store.claims_for_path(relpath)
    return bool(claims) and all(check_freshness(repo, claim).fresh for claim in claims)


def _build_reverse_index(repo: GitRepo, store: Store, warmed_files: dict[str, str | None]) -> dict[str, Any]:
    by_callee: dict[str, list[dict[str, str | None]]] = {}
    for claim in store.iter_claims():
        if claim.body.get("edge_kind") != "calls":
            continue
        if not check_freshness(repo, claim).fresh:
            continue
        callee_id = claim.body.get("callee_id")
        if not isinstance(callee_id, str):
            continue
        by_callee.setdefault(callee_id, []).append({
            "edge_id": claim.id,
            "caller_id": claim.body.get("caller_id"),
            "caller_path": claim.body.get("caller_path"),
            "callee_qualname": claim.body.get("callee_qualname"),
            "resolution": claim.body.get("resolution"),
            "evidence": claim.evidence,
            "anchor": claim.body.get("caller_anchor"),
        })
    return {"coverage": "complete", "warmed_files": warmed_files, "by_callee": by_callee}


def _current_warmed_files(repo: GitRepo) -> dict[str, str | None]:
    paths = _warmable_paths(repo)
    repo.preload_blob_shas(paths)
    return {p: repo.blob_sha(p) for p in paths}


def warm_is_complete(repo_root: str | Path, state_root: str | Path | None = None, *, read_only: bool = False) -> bool:
    repo = GitRepo(repo_root)
    store = Store(repo.root, state_root, read_only=read_only)
    manifest_path = _tmf_file_read_only(store, WARM_MANIFEST) if read_only else _tmf_file(store, WARM_MANIFEST)
    manifest = _load_json(manifest_path, {})
    warmed_files = manifest.get("warmed_files") if isinstance(manifest, dict) else None
    if not isinstance(warmed_files, dict):
        return False
    return warmed_files == _current_warmed_files(repo)


def load_complete_reverse_index(repo_root: str | Path, state_root: str | Path | None = None, *, read_only: bool = False) -> dict[str, Any] | None:
    repo = GitRepo(repo_root)
    store = Store(repo.root, state_root, read_only=read_only)
    tmf_file = _tmf_file_read_only if read_only else _tmf_file
    manifest = _load_json(tmf_file(store, WARM_MANIFEST), {})
    warmed_files = manifest.get("warmed_files") if isinstance(manifest, dict) else None
    if not isinstance(warmed_files, dict):
        return None
    current = _current_warmed_files(repo)
    if warmed_files != current:
        return None
    index = _load_json(tmf_file(store, REVERSE_INDEX), None)
    if not isinstance(index, dict) or index.get("coverage") != "complete":
        return None
    if index.get("warmed_files") != current:
        return None
    return index


def warm_repo(
    repo_root: str | Path,
    state_root: str | Path | None = None,
    *,
    per_file_timeout: float = DEFAULT_PER_FILE_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    repo = GitRepo(repo_root)
    store = Store(repo.root, state_root)
    manifest_path = _tmf_file(store, WARM_MANIFEST)
    manifest = _load_json(manifest_path, {})
    previous = manifest.get("warmed_files") if isinstance(manifest, dict) else {}
    if not isinstance(previous, dict):
        previous = {}

    paths = _warmable_paths(repo)
    repo.preload_blob_shas(paths)
    warmed_files: dict[str, str | None] = {}
    derived = 0
    skipped = 0
    skipped_claims = []
    for relpath in paths:
        blob = repo.blob_sha(relpath)
        warmed_files[relpath] = blob
        if previous.get(relpath) == blob and _claims_for_path_fresh(repo, store, relpath):
            skipped += 1
            continue
        outcome = derive_claims_for_path_with_timeout(repo, relpath, per_file_timeout=per_file_timeout)
        if outcome.skipped is not None:
            skipped += 1
            skipped_claims.append(outcome.skipped.to_dict())
            warmed_files.pop(relpath, None)
            continue
        _replace_path_claims(store, relpath, outcome.claims)
        derived += 1

    coverage = "partial" if skipped_claims else "complete"
    warm_manifest = {"coverage": coverage, "warmed_files": warmed_files}
    if skipped_claims:
        warm_manifest["skipped_claims"] = skipped_claims
    _write_json(manifest_path, warm_manifest)
    index = _build_reverse_index(repo, store, warmed_files)
    index["coverage"] = coverage
    if skipped_claims:
        index["skipped_claims"] = skipped_claims
    _write_json(_tmf_file(store, REVERSE_INDEX), index)
    result = {"coverage": coverage, "derived": derived, "skipped": skipped, "files": len(paths), "index_callees": len(index["by_callee"])}
    if skipped_claims:
        result["skipped_claims"] = skipped_claims
    return result
