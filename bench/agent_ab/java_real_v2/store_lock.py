#!/usr/bin/env python3
"""Deterministic locks and disposable execution for benchmark TMF stores."""
from __future__ import annotations

import hashlib
import json
import stat
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

LOCK_SCHEMA = "tmf-evaluation-store-lock-v1"
# Only ephemeral synchronization/temporary files are excluded. Identity,
# provenance, trust markers, and verification metadata can affect evaluation
# behavior and therefore remain part of the locked input.
_EXCLUDED_NAMES = frozenset({".lock"})


def _canonical(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _canonical(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        # List order can encode bindings, evidence, or relation order, so retain it.
        return [_canonical(item) for item in value]
    return value


def _content_digest(path: Path) -> str:
    data = path.read_bytes()
    if path.suffix == ".json":
        try:
            parsed = json.loads(data)
        except (UnicodeDecodeError, json.JSONDecodeError):
            pass
        else:
            data = json.dumps(_canonical(parsed), ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def store_inventory(store: Path) -> dict[str, Any]:
    """Return a path-private, order-independent semantic inventory."""
    store = store.resolve()
    if not store.is_dir():
        raise ValueError(f"TMF store missing: {store}")
    entries: list[tuple[str, str]] = []
    counts: dict[str, int] = {}
    for path in sorted(store.rglob("*")):
        # A symlinked store entry could make the disposable copy retain a path
        # back into the locked source store.  Fail closed instead of hashing
        # the target and later preserving the link via copytree(symlinks=True).
        if path.is_symlink():
            raise ValueError(f"TMF store contains unsupported symlink: {path.relative_to(store).as_posix()}")
        mode = path.stat().st_mode
        if stat.S_ISDIR(mode):
            continue
        if not stat.S_ISREG(mode):
            raise ValueError(f"TMF store contains unsupported file type: {path.relative_to(store).as_posix()}")
        if path.name in _EXCLUDED_NAMES or ".tmp" in path.suffixes:
            continue
        rel = path.relative_to(store).as_posix()
        kind = rel.split("/", 1)[0] if "/" in rel else rel
        counts[kind] = counts.get(kind, 0) + 1
        entries.append((rel, _content_digest(path)))
    digest_input = b"".join(
        rel.encode("utf-8") + b"\0" + digest.encode("ascii") + b"\n"
        for rel, digest in entries
    )
    return {
        "digest": hashlib.sha256(digest_input).hexdigest(),
        "file_count": len(entries),
        "component_counts": dict(sorted(counts.items())),
    }


def verify_lock(repo_id: str, commit: str, store: Path, lock: dict[str, Any]) -> dict[str, Any]:
    if lock.get("schema") != LOCK_SCHEMA:
        raise ValueError(f"unsupported store lock schema: {lock.get('schema')!r}")
    expected = next((item for item in lock.get("repositories", []) if item.get("id") == repo_id), None)
    if expected is None:
        raise ValueError(f"store lock has no repository {repo_id!r}")
    if expected.get("commit") != commit:
        raise ValueError(f"store lock commit drift for {repo_id}: expected {expected.get('commit')}, got {commit}")
    actual = store_inventory(store)
    for field in ("digest", "file_count", "component_counts"):
        if actual[field] != expected.get(field):
            raise ValueError(f"store drift for {repo_id}: {field} expected {expected.get(field)!r}, got {actual[field]!r}")
    return actual


@contextmanager
def disposable_repository(repo: Path) -> Iterator[Path]:
    """Copy repository and store so read-through writes cannot reach the source."""
    repo = repo.resolve()
    with tempfile.TemporaryDirectory(prefix="tmf-eval-") as tmp:
        target = Path(tmp) / "repo"
        shutil.copytree(
            repo,
            target,
            symlinks=True,
            ignore=shutil.ignore_patterns(".git", "target", "build", ".gradle", "node_modules"),
        )
        yield target
