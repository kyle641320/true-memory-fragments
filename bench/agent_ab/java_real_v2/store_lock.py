#!/usr/bin/env python3
"""Deterministic locks and disposable execution for benchmark TMF stores."""
from __future__ import annotations

import hashlib
import json
import stat
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path, PurePosixPath
from typing import Any, Iterator

LOCK_SCHEMA = "tmf-evaluation-store-lock-v1"
ARCHIVE_SCHEMA = "tmf-evaluation-store-archive-v1"
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
    if store.is_symlink():
        raise ValueError(f"TMF store contains unsupported root symlink: {store}")
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


def _safe_archive_path(value: object) -> str:
    if not isinstance(value, str) or not value or "\\" in value or "\0" in value:
        raise ValueError(f"unsafe archive path: {value!r}")
    if any(part in ("", ".", "..") for part in value.split("/")):
        raise ValueError(f"unsafe archive path: {value!r}")
    path = PurePosixPath(value)
    if path.is_absolute():
        raise ValueError(f"unsafe archive path: {value!r}")
    return path.as_posix()


def create_store_archive(store: Path, archive_root: Path) -> dict[str, Any]:
    """Materialize an immutable, content-addressed archive of a locked store."""
    inventory = store_inventory(store)  # also rejects links and special files
    store = store.resolve()
    files: list[dict[str, str]] = []
    payloads: dict[str, bytes] = {}
    for path in sorted(store.rglob("*")):
        if path.is_dir() or path.name in _EXCLUDED_NAMES or ".tmp" in path.suffixes:
            continue
        # Re-check at the byte-read boundary rather than trusting the inventory pass.
        if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
            raise ValueError(f"TMF store contains unsupported archive entry: {path.relative_to(store).as_posix()}")
        rel = _safe_archive_path(path.relative_to(store).as_posix())
        data = path.read_bytes()
        blob = hashlib.sha256(data).hexdigest()
        payloads.setdefault(blob, data)
        files.append({"path": rel, "blob": blob})
    manifest = {"schema": ARCHIVE_SCHEMA, "inventory": inventory, "files": files}
    encoded = json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    archive_id = hashlib.sha256(encoded).hexdigest()
    root = archive_root / archive_id
    if root.exists():
        verify_store_archive(root, archive_id)
        return {"archive_id": archive_id, **inventory}
    archive_root.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{archive_id}.tmp-", dir=archive_root))
    try:
        (staging / "blobs").mkdir()
        for digest, data in sorted(payloads.items()):
            (staging / "blobs" / digest).write_bytes(data)
        (staging / "manifest.json").write_bytes(encoded)
        for path in staging.rglob("*"):
            path.chmod(0o555 if path.is_dir() else 0o444)
        staging.chmod(0o555)
        staging.rename(root)
    except Exception:
        shutil.rmtree(staging, ignore_errors=True)
        raise
    return {"archive_id": archive_id, **inventory}


def verify_store_archive(archive: Path, expected_id: str | None = None) -> dict[str, Any]:
    """Fail closed unless an archive manifest and every referenced blob are intact."""
    if archive.is_symlink() or not archive.is_dir():
        raise ValueError("archive must be a regular directory")
    manifest_path = archive / "manifest.json"
    if manifest_path.is_symlink() or not manifest_path.is_file():
        raise ValueError("archive manifest missing or unsupported")
    blobs_dir = archive / "blobs"
    if blobs_dir.is_symlink() or not blobs_dir.is_dir():
        raise ValueError("archive blobs directory missing or unsupported")
    encoded = manifest_path.read_bytes()
    archive_id = hashlib.sha256(encoded).hexdigest()
    if expected_id is not None and archive_id != expected_id:
        raise ValueError(f"archive id mismatch: expected {expected_id}, got {archive_id}")
    try:
        manifest = json.loads(encoded)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid archive manifest") from exc
    if manifest.get("schema") != ARCHIVE_SCHEMA or not isinstance(manifest.get("files"), list):
        raise ValueError("unsupported archive manifest")
    seen: set[str] = set()
    for entry in manifest["files"]:
        if not isinstance(entry, dict):
            raise ValueError("invalid archive file entry")
        rel = _safe_archive_path(entry.get("path"))
        blob = entry.get("blob")
        if rel in seen or not isinstance(blob, str) or len(blob) != 64 or any(c not in "0123456789abcdef" for c in blob):
            raise ValueError(f"invalid archive file entry: {rel}")
        seen.add(rel)
        blob_path = archive / "blobs" / blob
        if blob_path.is_symlink() or not blob_path.is_file() or hashlib.sha256(blob_path.read_bytes()).hexdigest() != blob:
            raise ValueError(f"archive blob mismatch: {blob}")
    return {"archive_id": archive_id, **manifest["inventory"]}


def reconstruct_store_archive(archive: Path, destination: Path, expected_id: str | None = None) -> dict[str, Any]:
    """Reconstruct an archive into a new store and verify semantic fidelity."""
    verified = verify_store_archive(archive, expected_id)
    if destination.exists():
        raise ValueError(f"archive destination already exists: {destination}")
    manifest = json.loads((archive / "manifest.json").read_bytes())
    destination.mkdir(parents=True)
    try:
        for entry in manifest["files"]:
            target = destination / _safe_archive_path(entry["path"])
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((archive / "blobs" / entry["blob"]).read_bytes())
        actual = store_inventory(destination)
        if actual != manifest["inventory"]:
            raise ValueError(f"reconstructed store inventory mismatch: expected {manifest['inventory']!r}, got {actual!r}")
    except Exception:
        shutil.rmtree(destination, ignore_errors=True)
        raise
    return verified


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
