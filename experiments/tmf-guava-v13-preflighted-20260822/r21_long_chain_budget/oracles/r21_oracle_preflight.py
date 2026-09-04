#!/usr/bin/env python3
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
REPO_ROOT = HERE.parents[2]
SOURCE_LOCAL_CACHE = Path("/root/.openclaw/workspace/repos/guava/guava/src/com/google/common/cache/LocalCache.java")
ORACLE = HERE / "oracles" / "r21_refresh_hook_oracle.py"

CASES = {
    "good": {
        "expected_ok": True,
        "old": "              getAndRecordStats(key, hash, loadingValueReference, loadingFuture);\n",
        "new": "              getAndRecordStats(key, hash, loadingValueReference, loadingFuture);\n              recordRefreshCompletionHook(key);\n",
    },
    "bad_initiation": {
        "expected_ok": False,
        "old": "      ListenableFuture<V> result = loadAsync(key, hash, loadingValueReference, loader);\n",
        "new": "      ListenableFuture<V> result = loadAsync(key, hash, loadingValueReference, loader);\n      recordRefreshCompletionHook(key);\n",
    },
    "bad_transform": {
        "expected_ok": False,
        "old": "              LoadingValueReference.this.set(newResult);\n",
        "new": "              recordRefreshCompletionHook(key);\n              LoadingValueReference.this.set(newResult);\n",
    },
}


def make_case(tmp: Path, name: str, spec: dict) -> Path:
    target = tmp / name / "LocalCache.java"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE_LOCAL_CACHE, target)
    text = target.read_text(encoding="utf-8")
    if text.count(spec["old"]) != 1:
        raise AssertionError(f"{name}: replacement anchor count != 1")
    target.write_text(text.replace(spec["old"], spec["new"]), encoding="utf-8")
    return target


def main() -> int:
    rows = []
    errors = []
    if not SOURCE_LOCAL_CACHE.exists():
        errors.append(f"missing source baseline: {SOURCE_LOCAL_CACHE}")
    with tempfile.TemporaryDirectory(prefix="r21_oracle_preflight_") as td:
        tmp = Path(td)
        for name, spec in CASES.items():
            try:
                target = make_case(tmp, name, spec)
                proc = subprocess.run([sys.executable, str(ORACLE), str(target)], text=True, capture_output=True)
                payload = json.loads(proc.stdout)
            except Exception as exc:
                errors.append(f"{name}: {exc}")
                continue
            expected_ok = bool(spec["expected_ok"])
            actual_ok = bool(payload.get("ok"))
            rows.append({
                "case": name,
                "expected_ok": expected_ok,
                "actual_ok": actual_ok,
                "returncode": proc.returncode,
                "overall": payload.get("overall"),
                "hook_lines": [f.get("hook_line") for f in payload.get("findings", [])],
            })
            if actual_ok != expected_ok:
                errors.append(f"{name}: expected ok={expected_ok}, got {actual_ok} ({payload.get('overall')})")
    report = {"schema": "r21-oracle-preflight-v1", "pass": not errors, "errors": errors, "rows": rows}
    (HERE / "reports" / "r21_oracle_preflight.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
