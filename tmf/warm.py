from __future__ import annotations

import json
import os
import signal
import hashlib
from pathlib import Path
from typing import Any
from collections import defaultdict

from .derive import derive_claims_for_path
from .freshness import check_freshness
from .git import GitRepo
from .schema import Claim
from .store import Store
from .identity import build_rename_id_map, rebind_claim_path
from .metrics import log_event
from .derivation_versions import versions_for_path

WARM_MANIFEST = "warm_manifest.json"
REVERSE_INDEX = "reverse_callers.json"
COMPLETE_NOTE = "Known callers from fully warmed files; complete for the current warm manifest."
PARTIAL_NOTE = "Known callers from already-derived files only; not a complete blast radius."
WARM_FILE_TIMEOUT_SECONDS = int(os.environ.get("TMF_WARM_FILE_TIMEOUT_SECONDS", "30"))

EDGE_KINDS = {"calls", "reads", "writes", "inherits", "overrides", "uses_type", "reads_env", "reads_config_key", "injects", "publishes_to", "subscribes_to"}

JAVA_ENDPOINT_KIND_FIELDS = {
    "calls": ("caller_node_kind", "callee_node_kind"),
    "reads": ("reader_node_kind", "declaration_node_kind"),
    "writes": ("writer_node_kind", "declaration_node_kind"),
    "uses_type": ("user_node_kind", "type_node_kind"),
    "inherits": ("child_node_kind", "parent_node_kind"),
    "overrides": ("method_node_kind", "overridden_node_kind"),
    "injects": ("injector_node_kind", "bean_node_kind"),
}


def _claim_owner_path(claim: Claim) -> str | None:
    if claim.scope == "api" and claim.body.get("api_binding_model") == "dual-v2":
        return claim.body.get("route_source_path")
    edge_kind = claim.body.get("edge_kind")
    if edge_kind == "calls":
        return claim.body.get("caller_path")
    if edge_kind == "reads":
        return claim.body.get("reader_path")
    if edge_kind == "writes":
        return claim.body.get("writer_path")
    if edge_kind == "inherits":
        return claim.body.get("child_path")
    if edge_kind == "overrides":
        return claim.body.get("method_path")
    if edge_kind == "uses_type":
        return claim.body.get("user_path")
    if edge_kind in {"reads_env", "reads_config_key"}:
        return claim.body.get("reader_path")
    if edge_kind == "injects":
        return claim.body.get("injector_path")
    if edge_kind in {"publishes_to", "subscribes_to"}:
        return claim.body.get("source_path")
    if len(claim.bindings) == 1:
        return claim.bindings[0].path
    return None


def _refresh_claim_cache_for_replaced_path(claims_by_path: dict[str, list[Claim]], relpath: str, claims: list[Claim]) -> None:
    """Refresh the binding-expanded path cache without scanning the whole cache.

    A clean warm grows this cache to hundreds of thousands of claims.  The old
    implementation walked every bucket after every source file, making first
    warm quadratic in the accumulated claim count (Guava: 137k claims).  Claims
    owned by ``relpath`` are necessarily present in that path's binding bucket,
    so use that bucket to find the exact old claim ids and remove them only from
    their known binding buckets before adding the replacement claims.
    """
    old_owned: dict[str, Claim] = {
        claim.id: claim
        for claim in claims_by_path.get(relpath, [])
        if _claim_owner_path(claim) == relpath
    }
    for claim_id, old_claim in old_owned.items():
        for binding_path in {binding.path for binding in old_claim.bindings}:
            bucket = claims_by_path.get(binding_path)
            if bucket is None:
                continue
            kept = [existing for existing in bucket if existing.id != claim_id]
            if kept:
                claims_by_path[binding_path] = kept
            else:
                claims_by_path.pop(binding_path, None)
    for claim in claims:
        for binding_path in {binding.path for binding in claim.bindings}:
            bucket = claims_by_path.setdefault(binding_path, [])
            # Normally the old owner removal above already removed this id.  The
            # guard also keeps the cache sound for unusual shared-id fixtures.
            if all(existing.id != claim.id for existing in bucket):
                bucket.append(claim)


def _replace_path_claims_cached(store: Store, relpath: str, claims: list[Claim], claims_by_path: dict[str, list[Claim]]) -> None:
    """Replace claims owned by relpath without repeatedly scanning the whole store.

    Store.reconcile_* remains the public/simple path, but warm already has a
    path index.  Reusing it avoids O(files * claims) JSON reloads on medium
    repos.  Deletion mirrors Store's lifecycle rules: single-binding node claims
    owned by relpath plus edge claims whose caller/reader/writer/source owner is
    relpath.
    """
    current_ids = {claim.id for claim in claims}
    candidate_ids: set[str] = set()
    for claim in claims_by_path.get(relpath, []):
        owner = _claim_owner_path(claim)
        if claim.id in current_ids:
            continue
        if owner == relpath:
            candidate_ids.add(claim.id)
    for claim_id in candidate_ids:
        store.delete_claim(claim_id)
    _put_claims(store, claims)
    _refresh_claim_cache_for_replaced_path(claims_by_path, relpath, claims)


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


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _claim_inventory(store: Store) -> dict[str, Any]:
    digest = hashlib.sha256()
    count = 0
    for path in sorted(store.claims_dir.glob("*.json")):
        stat = path.stat()
        digest.update(path.name.encode("utf-8"))
        digest.update(b"\0")
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(b"\n")
        count += 1
    return {"count": count, "name_size_sha256": digest.hexdigest()}


def _upgrade_complete_manifest(repo: GitRepo, store: Store, manifest_path: Path, manifest: dict[str, Any], paths: list[str]) -> dict[str, Any]:
    if manifest.get("coverage") != "complete" or manifest.get("failed_files") or store.is_foreign_store():
        return manifest
    warmed_files = manifest.get("warmed_files")
    current = {path: repo.blob_sha(path) for path in paths}
    if not isinstance(warmed_files, dict) or warmed_files != current:
        return manifest
    reverse_index_path = _tmf_file(store, REVERSE_INDEX)
    reverse_index = _load_json(reverse_index_path, None)
    if not isinstance(reverse_index, dict) or reverse_index.get("coverage") != "complete" or reverse_index.get("warmed_files") != current:
        return manifest
    bound_paths: set[str] = set()
    try:
        for claim_path in sorted(store.claims_dir.glob("*.json")):
            claim = Claim.from_dict(json.loads(claim_path.read_text(encoding="utf-8")))
            for binding in claim.bindings:
                if binding.path in current:
                    if binding.file_blob != current[binding.path]:
                        return manifest
                    bound_paths.add(binding.path)
    except Exception:
        return manifest
    if bound_paths != set(paths):
        return manifest
    upgraded = dict(manifest)
    upgraded["claim_inventory"] = _claim_inventory(store)
    upgraded["reverse_index"] = {
        "size": reverse_index_path.stat().st_size,
        "sha256": _file_sha256(reverse_index_path),
        "index_callees": len(reverse_index.get("by_callee", {})),
    }
    _write_json(manifest_path, upgraded)
    return upgraded


def _legacy_java_relationship_owners(store: Store, paths: set[str]) -> tuple[set[str], int]:
    """Locate old Java edges that cannot be freshness-checked without guessing.

    Endpoint kinds are derivation output, not facts that readers may infer from
    roles or qualnames.  Affected owner paths are therefore re-derived from
    source and atomically reconciled by the normal per-path warm checkpoint.
    """
    owners: set[str] = set()
    claims = 0
    for claim in store.iter_claims():
        if claim.body.get("language") != "java":
            continue
        required = JAVA_ENDPOINT_KIND_FIELDS.get(claim.body.get("edge_kind"))
        if not required or all(claim.body.get(field) for field in required):
            continue
        owner = _claim_owner_path(claim)
        if owner in paths and owner.endswith(".java"):
            owners.add(owner)
            claims += 1
    return owners, claims


def _complete_noop_result(repo: GitRepo, store: Store, manifest: dict[str, Any], paths: list[str]) -> dict[str, Any] | None:
    if manifest.get("coverage") != "complete" or manifest.get("failed_files") or store.is_foreign_store():
        return None
    warmed_files = manifest.get("warmed_files")
    if not isinstance(warmed_files, dict) or len(warmed_files) != len(paths):
        return None
    current = {path: repo.blob_sha(path) for path in paths}
    if warmed_files != current:
        return None
    if manifest.get("derivation_versions") != _manifest_derivation_versions(paths):
        return None
    if _legacy_java_relationship_owners(store, set(paths))[0]:
        return None
    expected_claims = manifest.get("claim_inventory")
    if not isinstance(expected_claims, dict) or expected_claims != _claim_inventory(store):
        return None
    reverse_index_path = _tmf_file(store, REVERSE_INDEX)
    expected_index = manifest.get("reverse_index")
    if not reverse_index_path.is_file() or not isinstance(expected_index, dict):
        return None
    if expected_index.get("size") != reverse_index_path.stat().st_size or expected_index.get("sha256") != _file_sha256(reverse_index_path):
        return None
    index_callees = expected_index.get("index_callees")
    if not isinstance(index_callees, int):
        return None
    return {"coverage": "complete", "derived": 0, "skipped": len(paths), "files": len(paths), "failed_files": {}, "index_callees": index_callees, "renamed_claims": 0, "deleted_missing_claims": 0, "migrated_legacy_java_claims": 0, "migrated_legacy_java_paths": 0}


def _manifest_derivation_versions(paths: list[str]) -> dict[str, str]:
    versions: dict[str, str] = {}
    for path in paths:
        versions.update(versions_for_path(path))
    return versions


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


class WarmFileTimeoutError(TimeoutError):
    pass


def _derive_claims_with_timeout(repo: GitRepo, relpath: str) -> list[Claim]:
    if WARM_FILE_TIMEOUT_SECONDS <= 0:
        return derive_claims_for_path(repo, relpath)

    def _handle_timeout(signum, frame):  # type: ignore[no-untyped-def]
        raise WarmFileTimeoutError(f"derive timed out after {WARM_FILE_TIMEOUT_SECONDS}s")

    previous_handler = signal.getsignal(signal.SIGALRM)
    signal.signal(signal.SIGALRM, _handle_timeout)
    signal.setitimer(signal.ITIMER_REAL, WARM_FILE_TIMEOUT_SECONDS)
    try:
        return derive_claims_for_path(repo, relpath)
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)


def _replace_path_claims(store: Store, relpath: str, claims: list[Claim]) -> None:
    _put_claims(store, claims)
    store.reconcile_path_claims(relpath, [c for c in claims if c.body.get("edge_kind") not in EDGE_KINDS])
    store.reconcile_edge_claims_for_caller_path(relpath, [c for c in claims if c.body.get("edge_kind") in EDGE_KINDS])


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


def _rebuild_topic_graphs(repo: GitRepo, store: Store) -> None:
    publishers: dict[str, list[dict[str, Any]]] = defaultdict(list)
    subscribers: dict[str, list[dict[str, Any]]] = defaultdict(list)
    topic_claims: list[Claim] = []
    for claim in store.iter_claims():
        if claim.body.get("node_kind") == "topic":
            topic_claims.append(claim)
            continue
        edge_kind = claim.body.get("edge_kind")
        topic_id = claim.body.get("topic_id")
        if edge_kind not in {"publishes_to", "subscribes_to"} or not isinstance(topic_id, str):
            continue
        if not check_freshness(repo, claim).fresh:
            continue
        item = {
            "source_id": claim.body.get("source_id"),
            "source_path": claim.body.get("source_path"),
            "evidence": claim.evidence,
            "confidence": claim.confidence,
            "resolution": claim.body.get("resolution"),
            "tier": claim.body.get("tier"),
        }
        target = publishers if edge_kind == "publishes_to" else subscribers
        target[topic_id].append(item)
    for claim in topic_claims:
        graph = claim.body.setdefault("graph", {})
        graph["publishers"] = sorted(publishers.get(claim.id, []), key=lambda item: (str(item.get("source_path")), str(item.get("source_id"))))
        graph["subscribers"] = sorted(subscribers.get(claim.id, []), key=lambda item: (str(item.get("source_path")), str(item.get("source_id"))))
        graph["topic_coverage"] = "complete"
        store.put_claim(claim)


def warm_is_complete(repo_root: str | Path) -> bool:
    repo = GitRepo(repo_root)
    store = Store(repo.root)
    manifest = _load_json(_tmf_file(store, WARM_MANIFEST), {})
    if not isinstance(manifest, dict) or manifest.get("coverage") != "complete" or manifest.get("failed_files"):
        return False
    warmed_files = manifest.get("warmed_files")
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




def _claims_by_path_from_claims(claims: list[Claim]) -> dict[str, list[Claim]]:
    by_path: dict[str, list[Claim]] = defaultdict(list)
    for claim in claims:
        for binding in claim.bindings:
            by_path[binding.path].append(claim)
    return dict(by_path)


def _claim_paths(store: Store, claims: list[Claim] | None = None) -> set[str]:
    paths: set[str] = set()
    source = claims if claims is not None else store.iter_claims()
    for claim in source:
        for binding in claim.bindings:
            paths.add(binding.path)
    return paths


def _detect_unique_blob_renames(repo: GitRepo, store: Store, current_paths: list[str], existing_claims: list[Claim] | None = None, claims_by_path: dict[str, list[Claim]] | None = None) -> dict[str, str]:
    current = set(current_paths)
    existing = existing_claims if existing_claims is not None else list(store.iter_claims())
    by_path = claims_by_path if claims_by_path is not None else _claims_by_path_from_claims(existing)
    old_missing = sorted(path for path in _claim_paths(store, existing) if path not in current and repo.blob_sha(path) is None)
    previous_blobs: dict[str, str] = {}
    for claim in existing:
        for binding in claim.bindings:
            if binding.path in old_missing and binding.file_blob:
                previous_blobs.setdefault(binding.path, binding.file_blob)
    by_blob_new: dict[str, list[str]] = {}
    for path in current_paths:
        blob = repo.blob_sha(path)
        if blob:
            by_blob_new.setdefault(blob, []).append(path)
    by_blob_old: dict[str, list[str]] = {}
    for path, blob in previous_blobs.items():
        by_blob_old.setdefault(blob, []).append(path)
    renames: dict[str, str] = {}
    ambiguous_or_changed: set[str] = set()
    for blob, olds in by_blob_old.items():
        news = by_blob_new.get(blob, [])
        if len(olds) == 1 and len(news) == 1:
            renames[olds[0]] = news[0]
        else:
            ambiguous_or_changed.update(olds)
            for old in olds:
                count = len(by_path.get(old, []))
                if count:
                    log_event(repo.root, "rename_mass_invalidation", node_id=old, count=count, reason="blob_not_unique_or_missing")
    for old in old_missing:
        if old not in renames and old not in ambiguous_or_changed:
            count = len(by_path.get(old, []))
            if count:
                log_event(repo.root, "rename_mass_invalidation", node_id=old, count=count, reason="blob_not_unique_or_missing")
    return renames


def _delete_claims_for_missing_paths(repo: GitRepo, store: Store, current_paths: list[str], migrated_old_paths: set[str], existing_claims: list[Claim] | None = None, claims_by_path: dict[str, list[Claim]] | None = None) -> int:
    current = set(current_paths)
    existing = existing_claims if existing_claims is not None else list(store.iter_claims())
    by_path = claims_by_path if claims_by_path is not None else _claims_by_path_from_claims(existing)
    deleted = 0
    for old_path in sorted(path for path in _claim_paths(store, existing) if path not in current and repo.blob_sha(path) is None and path not in migrated_old_paths):
        claims = list(by_path.get(old_path, []))
        for claim in claims:
            if store.delete_claim(claim.id):
                deleted += 1
        if claims:
            log_event(repo.root, "rename_mass_invalidation", node_id=old_path, count=len(claims), reason="old_path_missing_not_unique_pure_rename")
    return deleted


def _apply_rename_migrations(repo: GitRepo, store: Store, renames: dict[str, str], claims_by_path: dict[str, list[Claim]] | None = None) -> int:
    migrated = 0
    for old_path, new_path in renames.items():
        affected = list(claims_by_path.get(old_path, [])) if claims_by_path is not None else [claim for claim in store.iter_claims() if any(b.path == old_path for b in claim.bindings)]
        if not affected:
            continue
        id_map = build_rename_id_map(affected, old_path, new_path)
        for claim in affected:
            store.delete_claim(claim.id)
        for claim in affected:
            store.put_claim(rebind_claim_path(claim, old_path, new_path, id_map))
        migrated += len(affected)
        log_event(repo.root, "rename_migration", node_id=old_path, new_path=new_path, count=len(affected))
    return migrated


def _dependent_force_derive_paths(store: Store, changed_paths: set[str], paths: set[str]) -> set[str]:
    """Stream dependency edges without retaining the full claim graph.

    Ordinary content edits do not need the rename/delete index. Keeping this
    scan streaming prevents a one-file edit in a large repository from holding
    every claim plus a binding-expanded path index in memory.
    """
    force_derive: set[str] = set()
    for claim in store.iter_claims():
        # Any cross-file claim whose dependency changed must be regenerated by
        # its owner.  Binding freshness prevents serving it, while this owner
        # scheduling removes the stale stored edge instead of leaving cleanup
        # to a later read-through.  Single-file claims are handled directly by
        # changed_paths and do not widen the slice.
        if claim.body.get("language") == "java" and len({binding.path for binding in claim.bindings}) > 1 and any(
            binding.path in changed_paths for binding in claim.bindings
        ):
            owner = _claim_owner_path(claim)
            if owner in paths:
                force_derive.add(owner)
            continue
        if claim.scope == "api" and claim.body.get("api_binding_model") == "dual-v2" and any(
            binding.path in changed_paths for binding in claim.bindings
        ):
            owner = _claim_owner_path(claim)
            if owner in paths:
                force_derive.add(owner)
            continue
        if claim.body.get("saga_dependency_paths") and any(
            binding.path in changed_paths for binding in claim.bindings[1:]
        ):
            owner = _claim_owner_path(claim)
            if owner in paths:
                force_derive.add(owner)
            continue
        if claim.body.get("edge_kind") != "publishes_to" or not claim.body.get("dependency_path"):
            continue
        if not any(binding.path in changed_paths for binding in claim.bindings):
            continue
        owner = _claim_owner_path(claim)
        if owner in paths:
            force_derive.add(owner)
    return force_derive

def warm_repo(repo_root: str | Path) -> dict[str, Any]:
    repo = GitRepo(repo_root)
    store = Store(repo.root)
    with store.write_lock():
        manifest_path = _tmf_file(store, WARM_MANIFEST)
        manifest = _load_json(manifest_path, {})
        previous = manifest.get("warmed_files") if isinstance(manifest, dict) else {}
        if not isinstance(previous, dict):
            previous = {}
        failed_files = manifest.get("failed_files") if isinstance(manifest, dict) else {}
        if not isinstance(failed_files, dict):
            failed_files = {}

        paths = _warmable_paths(repo)
        if "claim_inventory" not in manifest or "reverse_index" not in manifest:
            manifest = _upgrade_complete_manifest(repo, store, manifest_path, manifest, paths)
        noop_result = _complete_noop_result(repo, store, manifest, paths)
        if noop_result is not None:
            return noop_result
        expected_inventory = manifest.get("claim_inventory")
        integrity_repair = (
            manifest.get("coverage") == "complete"
            and isinstance(expected_inventory, dict)
            and expected_inventory != _claim_inventory(store)
        )
        changed_paths = {path for path in paths if previous.get(path) != repo.blob_sha(path)}
        legacy_java_paths, legacy_java_claims = _legacy_java_relationship_owners(store, set(paths))
        stored_derivation_versions = manifest.get("derivation_versions")
        current_derivation_versions = _manifest_derivation_versions(paths)
        version_changed_paths = {
            path for path in paths
            if any(
                not isinstance(stored_derivation_versions, dict)
                or stored_derivation_versions.get(name) != version
                for name, version in versions_for_path(path).items()
            )
        }
        same_path_inventory = set(previous) == set(paths)
        pristine_clean = not previous and not failed_files and not any(store.claims_dir.glob("*.json"))
        claims_by_path: dict[str, list[Claim]] | None = None
        if pristine_clean:
            force_derive = set()
            renames = {}
            renamed_claims = 0
            deleted_missing_claims = 0
        elif not integrity_repair and same_path_inventory:
            force_derive = _dependent_force_derive_paths(store, changed_paths, set(paths))
            force_derive.update(version_changed_paths)
            force_derive.update(legacy_java_paths)
            renames: dict[str, str] = {}
            renamed_claims = 0
            deleted_missing_claims = 0
        else:
            existing_claims = list(store.iter_claims())
            claims_by_path = _claims_by_path_from_claims(existing_claims)
            force_derive = set(paths) if integrity_repair else _dependent_force_derive_paths(
                store, changed_paths, set(paths)
            )
            force_derive.update(version_changed_paths)
            force_derive.update(legacy_java_paths)
            renames = _detect_unique_blob_renames(repo, store, paths, existing_claims, claims_by_path)
            renamed_claims = _apply_rename_migrations(repo, store, renames, claims_by_path)
            if renamed_claims:
                existing_claims = list(store.iter_claims())
                claims_by_path = _claims_by_path_from_claims(existing_claims)
            deleted_missing_claims = _delete_claims_for_missing_paths(
                repo, store, paths, set(renames), existing_claims, claims_by_path
            )
            if deleted_missing_claims:
                existing_claims = list(store.iter_claims())
                claims_by_path = _claims_by_path_from_claims(existing_claims)
        warmed_files: dict[str, str | None] = {}
        derived = 0
        skipped = 0
        for relpath in paths:
            blob = repo.blob_sha(relpath)
            warmed_files[relpath] = blob
            path_claims = claims_by_path.get(relpath, []) if claims_by_path is not None else None
            # When warm has checkpointed this exact repo blob, the claims were
            # derived from that blob in a previous warm slice.  Trust the
            # checkpoint for resume instead of re-running per-claim freshness for
            # every already-warmed file; otherwise partial warm can spend minutes
            # rechecking old files before reaching remaining work.
            if previous.get(relpath) == blob and (path_claims is None or path_claims) and relpath not in failed_files and relpath not in force_derive:
                skipped += 1
                continue
            try:
                claims = _derive_claims_with_timeout(repo, relpath)
            except WarmFileTimeoutError as exc:
                failed_files[relpath] = {"blob": blob, "reason": str(exc)}
                previous[relpath] = blob
                _write_json(manifest_path, {"coverage": "partial", "warmed_files": dict(previous), "failed_files": failed_files, "total_files": len(paths), "last_path": relpath})
                skipped += 1
                continue
            if pristine_clean:
                _put_claims(store, claims)
            elif claims_by_path is None:
                _replace_path_claims(store, relpath, claims)
            else:
                _replace_path_claims_cached(store, relpath, claims, claims_by_path)
            previous[relpath] = blob
            failed_files.pop(relpath, None)
            _write_json(manifest_path, {"coverage": "partial", "warmed_files": dict(previous), "failed_files": failed_files, "total_files": len(paths), "last_path": relpath})
            derived += 1

        coverage = "complete" if not failed_files and dict(previous) == warmed_files else "partial"
        manifest_payload = {"coverage": coverage, "warmed_files": warmed_files if coverage == "complete" else dict(previous), "failed_files": failed_files, "total_files": len(paths), "derivation_versions": current_derivation_versions}
        _write_json(manifest_path, manifest_payload)
        index_callees = 0
        reverse_index_path = _tmf_file(store, REVERSE_INDEX)
        if coverage == "complete":
            _rebuild_topic_graphs(repo, store)
            index = _build_reverse_index(repo, store, warmed_files)
            _write_json(reverse_index_path, index)
            index_callees = len(index["by_callee"])
            manifest_payload["claim_inventory"] = _claim_inventory(store)
            manifest_payload["reverse_index"] = {"size": reverse_index_path.stat().st_size, "sha256": _file_sha256(reverse_index_path), "index_callees": index_callees}
            _write_json(manifest_path, manifest_payload)
        elif reverse_index_path.exists():
            reverse_index_path.unlink()
        if store.is_foreign_store():
            store.clear_foreign_marker()
        return {"coverage": coverage, "derived": derived, "skipped": skipped, "files": len(paths), "failed_files": failed_files, "index_callees": index_callees, "renamed_claims": renamed_claims, "deleted_missing_claims": deleted_missing_claims, "migrated_legacy_java_claims": legacy_java_claims, "migrated_legacy_java_paths": len(legacy_java_paths)}
