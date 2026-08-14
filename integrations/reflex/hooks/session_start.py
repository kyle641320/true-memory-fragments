#!/usr/bin/env python3
"""
TMF SessionStart cognitive calibration.

At session start, consume the newest unconsumed TMF invalidation manifest and
emit a small context warning that marks changed/deleted code symbols as
"suspect". This deliberately does not read source files, derive claims, warm
TMF, delete memory, or block startup.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FUNCTION_SUSPECT_STATUSES = {"changed", "deleted"}
MODULE_TOP_LEVEL_SUSPECT_STATUSES = {"module_top_level_changed", "module_top_level_removed"}
SUSPECT_STATUSES = FUNCTION_SUSPECT_STATUSES | MODULE_TOP_LEVEL_SUSPECT_STATUSES
SKIPPED_STATUS = "skipped"
SCHEMA_VERSION = "tmf.sessionstart_calibration.v1"
DEFAULT_MANIFEST_GLOBS = (
    "invalidation-manifests/*.json",
    "invalidation_manifest*.json",
    "*invalidation*manifest*.json",
)


@dataclass(frozen=True)
class ManifestCandidate:
    path: Path
    fingerprint: str
    generated_at: str
    mtime_ns: int
    data: dict[str, Any]


def _sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def manifest_fingerprint(data: dict[str, Any]) -> str:
    """Return the stable delivery identity shared with the git calibrator."""
    revisions = "|".join(str(data.get(key, "")) for key in ("old_rev", "new_rev"))
    entries = json.dumps(data.get("entries") or [], sort_keys=True, ensure_ascii=False)
    return _sha256_bytes(f"{revisions}|{entries}".encode())


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _state_path(state_root: Path) -> Path:
    return state_root / "sessionstart_calibration_consumed.json"


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return data if isinstance(data, dict) else None


def _load_consumed(state_root: Path) -> dict[str, Any]:
    data = _load_json(_state_path(state_root))
    if not data:
        return {"schema_version": SCHEMA_VERSION, "consumed": {}}
    consumed = data.get("consumed")
    if not isinstance(consumed, dict):
        data["consumed"] = {}
    return data


def _save_consumed(state_root: Path, state: dict[str, Any]) -> None:
    path = _state_path(state_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _is_manifest(data: dict[str, Any]) -> bool:
    return data.get("schema_version") == "tmf.invalidation_manifest.v1" and isinstance(data.get("entries"), list)


def find_manifest_candidates(state_root: Path, extra_manifest_paths: list[Path] | None = None) -> list[ManifestCandidate]:
    seen: set[Path] = set()
    paths: list[tuple[int, Path]] = []
    for path in extra_manifest_paths or []:
        resolved = path if path.is_absolute() else state_root / path
        if resolved.is_file() and resolved.resolve() not in seen:
            seen.add(resolved.resolve())
            paths.append((0, resolved))
    for pattern in DEFAULT_MANIFEST_GLOBS:
        for path in state_root.glob(pattern):
            if path.is_file() and path.resolve() not in seen:
                seen.add(path.resolve())
                paths.append((1, path))

    prioritized: list[tuple[int, ManifestCandidate]] = []
    for priority, path in paths:
        try:
            payload = path.read_bytes()
            stat = path.stat()
        except OSError:
            continue
        data = _load_json(path)
        if not data or not _is_manifest(data):
            continue
        generated_at = str(data.get("generated_at") or "")
        prioritized.append((priority, ManifestCandidate(path=path, fingerprint=manifest_fingerprint(data), generated_at=generated_at, mtime_ns=stat.st_mtime_ns, data=data)))
    explicit = sorted((item for priority, item in prioritized if priority == 0), key=lambda item: (item.generated_at, item.mtime_ns, str(item.path)), reverse=True)
    discovered = sorted((item for priority, item in prioritized if priority != 0), key=lambda item: (item.generated_at, item.mtime_ns, str(item.path)), reverse=True)
    return explicit + discovered


def _qualifying_entries(manifest: dict[str, Any]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for raw in manifest.get("entries", []):
        if not isinstance(raw, dict):
            continue
        status = raw.get("status")
        file_name = raw.get("file")
        if status not in SUSPECT_STATUSES:
            continue
        if not isinstance(file_name, str) or not file_name:
            continue
        if str(status).startswith("module_top_level_"):
            if status not in MODULE_TOP_LEVEL_SUSPECT_STATUSES:
                continue
            contract = raw.get("module_top_level_contract")
            if not isinstance(contract, dict):
                continue
            anchor = contract.get("new_anchor") if status == "module_top_level_changed" else None
            if not isinstance(anchor, dict):
                anchor = contract.get("old_anchor")
            if not isinstance(anchor, dict) or "start" not in anchor or "end" not in anchor:
                continue
            entries.append({
                "status": str(status),
                "file": file_name,
                "qualname": "",
                "line_start": str(anchor["start"]),
                "line_end": str(anchor["end"]),
                "reason": str(raw.get("reason") or status),
            })
        else:
            qualname = raw.get("qualname")
            if not isinstance(qualname, str) or not qualname:
                continue
            entries.append({
                "status": str(status),
                "file": file_name,
                "qualname": qualname,
                "reason": str(raw.get("reason") or status),
            })
    for raw in manifest.get("skipped", []):
        if not isinstance(raw, dict) or raw.get("kind") != "skipped":
            continue
        file_name = raw.get("file")
        reason = raw.get("reason")
        if not isinstance(file_name, str) or not file_name or reason not in {"derive_timeout", "derive_failed"}:
            continue
        entries.append({
            "status": SKIPPED_STATUS,
            "file": file_name,
            "qualname": "",
            "reason": str(reason),
            "elapsed_ms": str(raw.get("elapsed_ms") or ""),
        })
    return entries


def build_warning_text(manifest: dict[str, Any], entries: list[dict[str, str]], *, manifest_path: Path | None = None, max_entries: int = 80) -> str:
    repo_root = str(manifest.get("repo_root") or "")
    generated_at = str(manifest.get("generated_at") or "")
    old_rev = str(manifest.get("old_rev") or "")
    new_rev = str(manifest.get("new_rev") or "")
    shown = entries[:max_entries]
    omitted = max(0, len(entries) - len(shown))

    has_skipped = any(entry["status"] == SKIPPED_STATUS for entry in shown)
    lines = [
        "═══ TMF SessionStart 认知校准：预先警觉 ═══",
        "你正在回到一个已有 TMF 记忆的代码领地。git-pull 校准清单显示，下列符号自上次认知以来发生了变化。",
        "这不是要求现在重读源码；不要全量重勘、不要删除记忆、不要阻断启动。只是在你的认知地图上把这些旧理解标为“存疑/可能过期”。实际用到其中某一处时，再读取当前源码或让既有 TMF 反射触发局部重新认知。",
        "",
        f"manifest: {manifest_path or '(unknown)'}",
        f"repo: {repo_root or '(unknown)'}",
        f"rev: {old_rev or '(unknown)'} → {new_rev or '(unknown)'}",
        f"generated_at: {generated_at or '(unknown)'}",
        "",
        (
            "存疑符号与未更新文件（changed/deleted/module_top_level_changed/module_top_level_removed/derive_timeout/derive_failed；added 不标存疑）："
            if has_skipped
            else "存疑符号（changed/deleted/module_top_level_changed/module_top_level_removed only；added 不标存疑）："
        ),
    ]
    for entry in shown:
        if entry["status"] == SKIPPED_STATUS:
            elapsed = f"（{entry['elapsed_ms']}ms）" if entry.get("elapsed_ms") else ""
            detail = "派生超时" if entry["reason"] == "derive_timeout" else "派生失败"
            lines.append(f"- ⚠️ {entry['file']} [{entry['reason']}] — {detail}{elapsed}，该文件认知未更新；实际用到时请读取当前源码。")
        elif entry["status"].startswith("module_top_level_"):
            detail = "已变化，旧认知可能错" if entry["status"] == "module_top_level_changed" else "已移除，旧认知指向的模块顶层逻辑可能不存在"
            lines.append(f"- ⚠️ 模块顶层逻辑已变更：{entry['file']} 第{entry['line_start']}-{entry['line_end']}行 [{entry['status']}] — {detail}；实际用到时请重新读取当前源码。")
        else:
            detail = "已变化，旧认知可能错" if entry["status"] == "changed" else "已删除，旧认知指向的东西可能不存在"
            lines.append(f"- ⚠️ {entry['file']}::{entry['qualname']} [{entry['status']}] — {detail}；实际用到时请重新读取当前源码。")
    if omitted:
        lines.append(f"- …另有 {omitted} 个存疑符号未展开；请查 manifest。")
    lines.append("═══ 校准边界：仅预警，不重读，不 warm，不清理，不强制。═══")
    return "\n".join(lines)


def consume_latest_manifest(repo_root: Path, *, state_root: Path, manifest_paths: list[Path] | None = None, mark_consumed: bool = True, max_entries: int = 80) -> dict[str, Any]:
    repo_root = repo_root.resolve()
    state_root = state_root.expanduser().resolve()
    consumed_state = _load_consumed(state_root)
    consumed = consumed_state.setdefault("consumed", {})

    for candidate in find_manifest_candidates(state_root, manifest_paths):
        if mark_consumed and candidate.fingerprint in consumed:
            continue
        entries = _qualifying_entries(candidate.data)
        if mark_consumed:
            consumed[candidate.fingerprint] = {
                "path": str(candidate.path),
                "generated_at": candidate.generated_at,
                "consumed_at": _now_iso(),
                "suspect_count": len(entries),
            }
            _save_consumed(state_root, consumed_state)
        if not entries:
            return {
                "injection": "",
                "manifest_path": str(candidate.path),
                "fingerprint": candidate.fingerprint,
                "suspect_entries": [],
                "consumed": mark_consumed,
                "reason": "no_changed_or_deleted_entries",
            }
        return {
            "injection": build_warning_text(candidate.data, entries, manifest_path=candidate.path, max_entries=max_entries),
            "manifest_path": str(candidate.path),
            "fingerprint": candidate.fingerprint,
            "suspect_entries": entries,
            "consumed": mark_consumed,
            "reason": "ok",
        }

    return {
        "injection": "",
        "manifest_path": None,
        "fingerprint": None,
        "suspect_entries": [],
        "consumed": False,
        "reason": "no_unconsumed_manifest",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Emit one TMF SessionStart suspect-cognition warning from an invalidation manifest.")
    parser.add_argument("--repo", default=".", help="Repository root recorded in the manifest warning.")
    parser.add_argument("--state-root", required=True, help="External TMF worktree-state directory containing manifests and consumption state.")
    parser.add_argument("--manifest", action="append", default=[], help="Extra manifest path to consider, relative to --state-root or absolute; may be repeated.")
    parser.add_argument("--no-consume", action="store_true", help="Do not mark the selected manifest as consumed.")
    parser.add_argument("--max-entries", type=int, default=80, help="Maximum suspect symbols to include in the warning text.")
    parser.add_argument("--json", action="store_true", help="Emit structured JSON instead of plain injection text.")
    args = parser.parse_args()

    result = consume_latest_manifest(
        Path(args.repo),
        state_root=Path(args.state_root),
        manifest_paths=[Path(item) for item in args.manifest],
        mark_consumed=not args.no_consume,
        max_entries=max(1, args.max_entries),
    )
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    elif result["injection"]:
        print(result["injection"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
