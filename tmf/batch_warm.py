"""Batch warm: memory-bounded incremental TMF indexing for large repositories.

Memory-bounded warm for repos that OOM in single-pass warm. Two-phase approach:
1. Phase 1: Derive all source files in batches, write claims directly to disk
2. Phase 2: Build reverse index once all claims are on disk (no in-memory claim cache)

Usage:
    python3 -m tmf.cli batch-warm --repo <path> [--batch-size N]
"""
from __future__ import annotations

import gc
import json
import os
from pathlib import Path
from typing import Any

from .derive import derive_claims_for_path
from .git import GitRepo
from .store import Store
from .warm import (
    _manifest_derivation_versions,
    _claim_inventory,
    _tmf_file,
    _write_json,
    WARM_MANIFEST,
)

DEFAULT_BATCH_SIZE = 50  # Files per batch; tune based on available memory


def batch_warm(repo_path: Path, state_root: Path | None = None, batch_size: int = DEFAULT_BATCH_SIZE) -> dict[str, Any]:
    """Memory-bounded warm: index repo in batches to avoid OOM.
    
    Phase 1: Derive claims for all files, write directly to store.
    Phase 2: Build reverse index (not implemented yet).
    
    Returns final manifest with coverage="complete" if all files succeeded.
    """
    repo = GitRepo(repo_path)
    store = Store(repo_path)
    store.init()
    
    manifest_path = _tmf_file(store, WARM_MANIFEST)
    
    # Find all derivable files (match warm.py's _warmable_paths logic)
    paths: list[str] = []
    for suffix in ("*.py", "*.json", "*.toml", "*.java"):
        for path in sorted(repo_path.rglob(suffix)):
            rel = path.relative_to(repo_path).as_posix()
            if rel.startswith(".git/") or rel.startswith(".tmf/"):
                continue
            if rel not in paths:
                paths.append(rel)
    paths = sorted(paths)
    total_files = len(paths)
    
    print(f"TMF batch warm: {total_files} files, batch_size={batch_size}")
    
    warmed_files: dict[str, str] = {}
    failed_files: dict[str, str] = {}
    derived = 0
    batch_num = 0
    
    # Phase 1: Derive all files in batches
    for i in range(0, total_files, batch_size):
        batch_num += 1
        batch = paths[i:i + batch_size]
        batch_progress = f"[{i + 1}-{min(i + batch_size, total_files)}/{total_files}]"
        
        print(f"TMF: batch {batch_num} {batch_progress}")
        
        # Derive claims for this batch
        for relpath in batch:
            try:
                blob_sha = repo.blob_sha(relpath)
                file_path = repo_path / relpath
                
                if not file_path.is_file():
                    failed_files[relpath] = "file_not_found"
                    continue
                
                claims = derive_claims_for_path(repo, relpath)
                
                # Write claims directly to store, bypassing cache
                # This is the key: we don't accumulate claims in memory
                _write_claims_directly(store, relpath, claims, blob_sha)
                
                warmed_files[relpath] = blob_sha
                derived += 1
                
            except Exception as e:
                failed_files[relpath] = str(e)
                print(f"TMF: failed {relpath}: {e}")
        
        # Force memory release after each batch
        gc.collect()
        
        # Write incremental manifest
        partial_manifest = {
            "coverage": "partial",
            "phase": "derive",
            "batch_num": batch_num,
            "derived": derived,
            "failed_count": len(failed_files),
            "warmed_files": warmed_files,
            "failed_files": failed_files,
            "derivation_versions": _manifest_derivation_versions(paths),
        }
        _write_json(manifest_path, partial_manifest)
    
    # Final manifest
    coverage = "complete" if not failed_files else "partial"
    final_manifest = {
        "coverage": coverage,
        "phase": "derive_complete",
        "derived": derived,
        "files": total_files,
        "failed_files": failed_files,
        "warmed_files": warmed_files,
        "derivation_versions": _manifest_derivation_versions(paths),
        "claim_inventory": _claim_inventory(store),
    }
    _write_json(manifest_path, final_manifest)
    
    print(f"TMF batch warm complete: {coverage}, {derived}/{total_files} files, {len(failed_files)} failed")
    
    return final_manifest


def _write_claims_directly(store: Store, relpath: str, claims: list, blob_sha: str) -> None:
    """Write claims directly to store.
    
    Simple strategy: just write new claims. Let store.put_claim overwrite by ID.
    We rely on derive_claims_for_path producing stable IDs for the same source.
    
    This avoids both in-memory caching AND full-store scans.
    Trade-off: orphaned old claims may remain if IDs change, but that's acceptable
    for avoiding OOM on large repos.
    """
    # Write new claims directly
    for claim in claims:
        store.put_claim(claim)


def _get_claim_owner(claim_data: dict, relpath: str) -> str | None:
    """Extract claim owner path from raw claim data."""
    body = claim_data.get("body", {})
    scope = claim_data.get("scope")
    
    if scope == "api" and body.get("api_binding_model") == "dual-v2":
        return body.get("route_source_path")
    
    edge_kind = body.get("edge_kind")
    if edge_kind == "calls":
        return body.get("caller_path")
    if edge_kind == "reads":
        return body.get("reader_path")
    if edge_kind == "writes":
        return body.get("writer_path")
    if edge_kind == "inherits":
        return body.get("child_path")
    if edge_kind == "overrides":
        return body.get("method_path")
    if edge_kind == "uses_type":
        return body.get("user_path")
    if edge_kind in ("reads_env", "reads_config_key"):
        return body.get("reader_path")
    if edge_kind == "injects":
        return body.get("injector_path")
    if edge_kind in ("publishes_to", "subscribes_to", "publishes_type", "listens_type"):
        return body.get("source_path")
    
    bindings = claim_data.get("bindings", [])
    if len(bindings) == 1:
        return bindings[0].get("path")
    
    return None
