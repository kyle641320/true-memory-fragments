from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .derive import derive_claims_for_path
from .freshness import check_freshness
from .git import GitRepo
from .schema import Claim
from .store import Store

WARM_MANIFEST = "warm_manifest.json"
REVERSE_INDEX = "reverse_callers.json"
COMPLETE_NOTE = "Known callers from fully warmed files; complete for the current warm manifest."
PARTIAL_NOTE = "Known callers from already-derived files only; not a complete blast radius."


def _tmf_file(store: Store, name: str) -> Path:
    store.init()
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


def _ignore_prefixes(repo: GitRepo) -> list[str]:
    path = repo.root / ".tmfignore"
    if not path.exists():
        return []
    prefixes: list[str] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.endswith("/"):
            prefixes.append(line)
        else:
            prefixes.append(line.rstrip("/") + "/")
            prefixes.append(line)
    return prefixes


def _is_ignored(rel: str, prefixes: list[str]) -> bool:
    return any(rel == prefix.rstrip("/") or rel.startswith(prefix) for prefix in prefixes)


def _warmable_paths(repo: GitRepo) -> list[str]:
    out: list[str] = []
    prefixes = _ignore_prefixes(repo)
    for suffix in ("*.py", "*.json", "*.toml", "*.java"):
        for path in sorted(repo.root.rglob(suffix)):
            rel = path.relative_to(repo.root).as_posix()
            if rel.startswith(".git/") or rel.startswith(".tmf/") or _is_ignored(rel, prefixes):
                continue
            if rel not in out:
                out.append(rel)
    return sorted(out)


def _put_claims(store: Store, claims: list[Claim]) -> None:
    for claim in claims:
        store.put_claim(claim)


def _replace_path_claims(store: Store, relpath: str, claims: list[Claim]) -> None:
    _put_claims(store, claims)
    store.reconcile_path_claims(relpath, [c for c in claims if c.body.get("edge_kind") not in {"calls", "reads", "writes", "inherits"}])
    store.reconcile_edge_claims_for_caller_path(relpath, [c for c in claims if c.body.get("edge_kind") in {"calls", "reads", "writes", "inherits"}])


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


def warm_is_complete(repo_root: str | Path) -> bool:
    repo = GitRepo(repo_root)
    store = Store(repo.root)
    manifest = _load_json(_tmf_file(store, WARM_MANIFEST), {})
    warmed_files = manifest.get("warmed_files") if isinstance(manifest, dict) else None
    if not isinstance(warmed_files, dict):
        return False
    current = {path: repo.blob_sha(path) for path in _warmable_paths(repo)}
    return warmed_files == current


def load_complete_reverse_index(repo_root: str | Path) -> dict[str, Any] | None:
    if not warm_is_complete(repo_root):
        return None
    repo = GitRepo(repo_root)
    store = Store(repo.root)
    index = _load_json(_tmf_file(store, REVERSE_INDEX), None)
    if not isinstance(index, dict) or index.get("coverage") != "complete":
        return None
    if index.get("warmed_files") != {path: repo.blob_sha(path) for path in _warmable_paths(repo)}:
        return None
    return index


def warm_repo(repo_root: str | Path) -> dict[str, Any]:
    repo = GitRepo(repo_root)
    store = Store(repo.root)
    manifest_path = _tmf_file(store, WARM_MANIFEST)
    manifest = _load_json(manifest_path, {})
    previous = manifest.get("warmed_files") if isinstance(manifest, dict) else {}
    if not isinstance(previous, dict):
        previous = {}

    paths = _warmable_paths(repo)
    warmed_files: dict[str, str | None] = {}
    derived = 0
    skipped = 0
    for relpath in paths:
        blob = repo.blob_sha(relpath)
        warmed_files[relpath] = blob
        if previous.get(relpath) == blob and _claims_for_path_fresh(repo, store, relpath):
            skipped += 1
            continue
        claims = derive_claims_for_path(repo, relpath)
        _replace_path_claims(store, relpath, claims)
        derived += 1

    _write_json(manifest_path, {"coverage": "complete", "warmed_files": warmed_files})
    index = _build_reverse_index(repo, store, warmed_files)
    _write_json(_tmf_file(store, REVERSE_INDEX), index)
    return {"coverage": "complete", "derived": derived, "skipped": skipped, "files": len(paths), "index_callees": len(index["by_callee"])}
