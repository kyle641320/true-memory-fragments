#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TMF_ROOT = HERE.parents[2]
sys.path.insert(0, str(TMF_ROOT))
from bench.agent_ab.java_real_v2.store_lock import disposable_repository, verify_lock

manifest = json.loads((HERE / "manifest.json").read_text(encoding="utf-8"))
lock = json.loads((HERE / "store-lock.json").read_text(encoding="utf-8"))
parser = argparse.ArgumentParser()
parser.add_argument("repo", choices=[item["id"] for item in manifest["repositories"]])
parser.add_argument("question", nargs="?")
parser.add_argument("--max-chars", type=int, default=10000)
parser.add_argument("--status", action="store_true")
parser.add_argument("--warm", action="store_true")
args = parser.parse_args()

record = next(item for item in manifest["repositories"] if item["id"] == args.repo)
source = Path(record["path"]).resolve()
actual_commit = subprocess.check_output(["git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
if actual_commit != record["commit"]:
    raise SystemExit(f"commit drift for {args.repo}: expected {record['commit']}, got {actual_commit}")
try:
    inventory = verify_lock(args.repo, actual_commit, source / ".tmf", lock)
except ValueError as exc:
    raise SystemExit(str(exc)) from exc

# McpService freshness/read-through is permitted to mutate only this disposable copy.
with disposable_repository(source) as copy:
    from tmf.mcp_server import McpService

    service = McpService(copy)
    result = service.tmf_status() if args.status else service.tmf_warm() if args.warm else service.tmf_context(args.question or "", args.max_chars)
print(json.dumps({"repo_id": args.repo, "commit": actual_commit, "store_digest": inventory["digest"], "result": result}, ensure_ascii=False, sort_keys=True))
