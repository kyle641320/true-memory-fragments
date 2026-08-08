#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Write a plan-only TMF field-test diary template. Does not clone/fetch/run scouting.")
    parser.add_argument("--out", default="reports/field_test_plan/diary_template.jsonl")
    parser.add_argument("--repo-placeholder", default="/path/to/repo", help="placeholder repo path for future commands; not accessed")
    parser.add_argument("--out-placeholder", default="reports/field", help="placeholder output path for future commands; not created")
    args = parser.parse_args()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    repo = args.repo_placeholder
    out_placeholder = args.out_placeholder
    plan = {
        "status": "plan_only_not_started",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "network": "not_used",
        "repo_placeholder": repo,
        "out_placeholder": out_placeholder,
        "commands": [
            f"python3 -m tmf.cli warm --repo {repo}",
            f"python3 -m tmf.cli stats --repo {repo}",
            f"python3 -m tmf.cli validate --repo {repo} --out {out_placeholder} --self-validate",
        ],
        "capture": [
            "files_seen", "claims_total", "cache_hit", "miss", "stale_detected",
            "rederive", "degrade_to_source", "rename_migration", "rename_mass_invalidation",
            "heldout_precision", "heldout_recall", "self_precision", "self_recall",
        ],
        "guardrails": [
            "offline harness only; do not clone, fetch, browse, or scout repositories from window 1/2 packaging",
            "do not start before windows 1-4 pass review",
            "do not use field scouting to change engine behavior without a separate reviewed window",
            "treat source as authority and prefer unresolved/source fallback over guessing",
        ],
    }
    out.write_text(json.dumps(plan, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"status": "plan_only_not_started", "written": str(out)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
