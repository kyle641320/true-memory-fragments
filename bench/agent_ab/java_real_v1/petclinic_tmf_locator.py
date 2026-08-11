#!/usr/bin/env python3
"""Experiment-only, repo-pinned TMF locator for java_real_v1.

This wrapper deliberately bypasses the globally registered Zhihu-pinned MCP instance.
It does not alter TMF engine behavior: it instantiates the existing McpService with the
Petclinic repository declared in the frozen manifest and refuses commit drift.
"""
from __future__ import annotations
import argparse, json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMF_ROOT = HERE.parents[2]
if str(TMF_ROOT) not in sys.path:
    sys.path.insert(0, str(TMF_ROOT))
MANIFEST = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
PETCLINIC = next(r for r in MANIFEST["repositories"] if r["id"] == "petclinic")
REPO = Path(PETCLINIC["path"]).resolve()
EXPECTED_COMMIT = PETCLINIC["commit"]


def verify_pin() -> str:
    actual = subprocess.check_output(
        ["git", "-C", str(REPO), "rev-parse", "HEAD"], text=True
    ).strip()
    if actual != EXPECTED_COMMIT:
        raise SystemExit(f"repo commit drift: expected {EXPECTED_COMMIT}, got {actual}")
    return actual


def main() -> int:
    ap = argparse.ArgumentParser(description="Petclinic-pinned TMF locator")
    ap.add_argument("question", nargs="?", help="natural-language code question")
    ap.add_argument("--max-chars", type=int, default=12000)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--warm", action="store_true")
    args = ap.parse_args()
    commit = verify_pin()
    # Import only after pin verification; PYTHONPATH must point at the frozen TMF checkout.
    from tmf.mcp_server import McpService
    svc = McpService(REPO)
    if args.status:
        payload = svc.tmf_status()
    elif args.warm:
        payload = svc.tmf_warm()
    else:
        if not args.question:
            ap.error("question is required unless --status or --warm is used")
        payload = svc.tmf_context(args.question, args.max_chars)
    print(json.dumps({"repo": str(REPO), "commit": commit, "result": payload}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
