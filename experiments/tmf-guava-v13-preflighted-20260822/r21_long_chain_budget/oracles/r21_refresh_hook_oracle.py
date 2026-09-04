#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

DEFAULT_HOOK = "recordRefreshCompletionHook"


def find_matching_brace(text: str, open_pos: int) -> int:
    depth = 0
    for i in range(open_pos, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return i
    return -1


def method_span(text: str, signature_re: str) -> tuple[int, int]:
    m = re.search(signature_re, text, re.MULTILINE | re.DOTALL)
    if not m:
        return (-1, -1)
    open_pos = text.find("{", m.end() - 1)
    if open_pos < 0:
        return (-1, -1)
    close_pos = find_matching_brace(text, open_pos)
    return (m.start(), close_pos + 1 if close_pos >= 0 else -1)


def line_no(text: str, pos: int) -> int | None:
    if pos < 0:
        return None
    return text.count("\n", 0, pos) + 1


def classify(path: Path, hook: str = DEFAULT_HOOK) -> dict:
    text = path.read_text(encoding="utf-8")
    hook_positions = [m.start() for m in re.finditer(re.escape(hook), text)]

    refresh_span = method_span(text, r"@Nullable\s+V\s+refresh\s*\([^)]*?boolean\s+checkTime\s*\)")
    load_async_span = method_span(text, r"ListenableFuture<V>\s+loadAsync\s*\(")
    stats_span = method_span(text, r"V\s+getAndRecordStats\s*\(")
    load_future_span = method_span(text, r"public\s+ListenableFuture<V>\s+loadFuture\s*\(")

    anchors = {
        "refresh_span": refresh_span,
        "load_async_span": load_async_span,
        "get_and_record_stats_span": stats_span,
        "load_future_span": load_future_span,
        "load_async_call": text.find("ListenableFuture<V> result = loadAsync"),
        "listener": text.find("loadingFuture.addListener("),
        "get_and_record_stats_call": text.find("getAndRecordStats(key, hash, loadingValueReference, loadingFuture)"),
        "store_loaded_value": text.find("storeLoadedValue(key, hash, loadingValueReference, value);"),
        "transform_set": text.find("LoadingValueReference.this.set(newResult);"),
    }

    findings = []
    any_pass = False
    any_fail = False

    for pos in hook_positions:
        in_refresh = refresh_span[0] <= pos < refresh_span[1] if refresh_span[0] >= 0 else False
        in_load_async = load_async_span[0] <= pos < load_async_span[1] if load_async_span[0] >= 0 else False
        in_stats = stats_span[0] <= pos < stats_span[1] if stats_span[0] >= 0 else False
        in_load_future = load_future_span[0] <= pos < load_future_span[1] if load_future_span[0] >= 0 else False

        after_load_async_call = anchors["load_async_call"] >= 0 and pos > anchors["load_async_call"]
        after_stats_call_in_listener = (
            in_load_async
            and anchors["get_and_record_stats_call"] >= 0
            and pos > anchors["get_and_record_stats_call"]
        )
        after_store_loaded = in_stats and anchors["store_loaded_value"] >= 0 and pos > anchors["store_loaded_value"]
        before_transform_set = in_load_future and anchors["transform_set"] >= 0 and pos < anchors["transform_set"]

        if in_refresh and after_load_async_call:
            classification = "fail_initiation_path"
            any_fail = True
        elif before_transform_set:
            classification = "fail_before_publication"
            any_fail = True
        elif after_stats_call_in_listener or after_store_loaded:
            classification = "pass_completion_listener_after_publication"
            any_pass = True
        else:
            classification = "ambiguous_or_missing"

        findings.append(
            {
                "hook_pos": pos,
                "hook_line": line_no(text, pos),
                "in_refresh": in_refresh,
                "in_load_async": in_load_async,
                "in_get_and_record_stats": in_stats,
                "in_load_future": in_load_future,
                "classification": classification,
            }
        )

    if not hook_positions:
        overall = "ambiguous_or_missing"
        ok = False
    elif any_pass and not any_fail:
        overall = "pass_completion_listener_after_publication"
        ok = True
    elif any_fail:
        overall = "fail"
        ok = False
    else:
        overall = "ambiguous_or_missing"
        ok = False

    return {
        "schema": "r21-refresh-hook-oracle-v1",
        "file": str(path),
        "hook": hook,
        "ok": ok,
        "overall": overall,
        "hook_count": len(hook_positions),
        "findings": findings,
        "anchor_lines": {k: (line_no(text, v) if isinstance(v, int) else [line_no(text, v[0]), line_no(text, v[1])]) for k, v in anchors.items()},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("file", type=Path)
    ap.add_argument("--hook", default=DEFAULT_HOOK)
    args = ap.parse_args()
    result = classify(args.file, args.hook)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
