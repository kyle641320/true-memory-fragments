#!/usr/bin/env python3
"""Score guava_cognitive_v1 answers against tasks.json ground truth.

Two scoring channels, deliberately kept separate:

  objective   Mechanically checkable facts only. For reasoning tasks this is
              anchor coverage (did the answer name the classes/methods the
              ground truth requires). For compile_repair it is javac exit
              status plus the touched-file constraints. No LLM involved.

  rubric      The per-task rubric in tasks.json, which needs judgement about
              *what the answer claims*, not just which tokens appear. This
              script does not attempt to fake that; it emits a scoring packet
              per answer for an external reviewer and records the rubric as
              pending.

Reporting objective coverage as if it were the rubric score would overstate
what was measured, so the two never get merged into one number here.

Usage:
    python3 score.py                 # score everything present
    python3 score.py --task B01
    python3 score.py --json          # machine-readable to stdout
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

SUITE = Path(__file__).resolve().parent
RESULTS = SUITE / "results"
ANSWERS = RESULTS / "answers"
WORK = RESULTS / "work"
ARMS = ("no_tool", "tmf_thin", "tmf_full")


def load_tasks() -> dict:
    return json.loads((SUITE / "tasks.json").read_text(encoding="utf-8"))


def _mentions(text: str, anchor: str) -> bool:
    """True if `anchor` is named in `text`.

    Matching is deliberately lenient about the separator: an answer that writes
    "EventBus#post" or "EventBus.post()" or "post() on EventBus" is naming the
    same member as "EventBus.post". It is strict about word boundaries so that
    "Dispatcher" is not credited by "PerThreadQueuedDispatcher".
    """
    if "." in anchor:
        owner, member = anchor.rsplit(".", 1)
        pat = (
            rf"\b{re.escape(owner)}\s*[.#:]{{1,2}}\s*{re.escape(member)}\b"
            rf"|\b{re.escape(member)}\b[^.\n]{{0,40}}\b{re.escape(owner)}\b"
        )
        return re.search(pat, text) is not None
    return re.search(rf"\b{re.escape(anchor)}\b", text) is not None


def score_reasoning(task: dict, answer: str) -> dict:
    gt = task["ground_truth"]
    required = list(gt.get("must_name", []))
    subclasses = list(gt.get("must_name_subclasses", []))

    named = {a: _mentions(answer, a) for a in required}
    named_sub = {a: _mentions(answer, a) for a in subclasses}

    total = len(named) + len(named_sub)
    hit = sum(named.values()) + sum(named_sub.values())

    return {
        "channel": "objective",
        "metric": "anchor_coverage",
        "anchors_total": total,
        "anchors_hit": hit,
        "coverage": round(hit / total, 3) if total else None,
        "must_name": named,
        "must_name_subclasses": named_sub,
        "missing": [a for a, ok in {**named, **named_sub}.items() if not ok],
        "answer_chars": len(answer),
    }


def score_repair(task: dict, arm: str, answer: str) -> dict:
    gt = task["ground_truth"]
    tree = WORK / f"{task['id']}__{arm}"
    pristine = SUITE / "fixtures" / task["fixture"] / "work"

    out: dict = {
        "channel": "objective",
        "metric": "compile_and_scope",
        "work_tree": str(tree.relative_to(SUITE)) if tree.exists() else None,
        "answer_chars": len(answer),
    }

    if not tree.is_dir():
        out["compiles"] = None
        out["error"] = "work tree missing"
        return out

    cp = (SUITE / "classpath.txt").read_text(encoding="utf-8").strip()
    proc = subprocess.run(
        ["javac", "-nowarn", "-cp", cp, "-d", f"/tmp/score_{task['id']}_{arm}"]
        + sorted(str(p) for p in tree.glob("*.java")),
        capture_output=True,
        text=True,
    )
    out["compiles"] = proc.returncode == 0
    out["javac_returncode"] = proc.returncode
    if proc.returncode != 0:
        out["javac_stderr"] = proc.stderr.strip()[:1500]

    # Which files actually differ from the pristine mutated tree.
    modified = []
    for p in sorted(tree.glob("*.java")):
        base = pristine / p.name
        if not base.exists():
            modified.append(p.name + " (new)")
        elif p.read_bytes() != base.read_bytes():
            modified.append(p.name)
    out["modified_files"] = modified

    must_touch = gt.get("must_touch_files", [])
    must_not = gt.get("must_not_touch", [])
    out["must_touch_ok"] = all(f in modified for f in must_touch)
    out["must_not_touch_violations"] = [f for f in must_not if f in modified]
    out["extra_files_touched"] = [f for f in modified if f not in must_touch]

    # The mutation must survive: getSubscribers still returns List<Subscriber>.
    reg = tree / "SubscriberRegistry.java"
    if reg.exists():
        src = reg.read_text(encoding="utf-8")
        out["return_type_preserved"] = (
            "List<Subscriber> getSubscribers(" in src
            and "Iterator<Subscriber> getSubscribers(" not in src
        )
    else:
        out["return_type_preserved"] = None

    return out


def rubric_packet(task: dict, arm: str, answer: str) -> dict:
    return {
        "channel": "rubric",
        "status": "pending_external_review",
        "max": task["scoring"]["max"],
        "rubric": task["scoring"]["rubric"],
        "key_insight": task["ground_truth"].get("key_insight"),
        "answer_path": f"answers/{task['id']}__{arm}.md",
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task")
    ap.add_argument("--arm", choices=ARMS)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    spec = load_tasks()
    rows: list[dict] = []

    for task in spec["tasks"]:
        if args.task and task["id"] != args.task:
            continue
        for arm in ARMS:
            if args.arm and arm != args.arm:
                continue
            path = ANSWERS / f"{task['id']}__{arm}.md"
            if not path.exists():
                rows.append(
                    {"task": task["id"], "arm": arm, "status": "missing_answer"}
                )
                continue
            answer = path.read_text(encoding="utf-8")
            objective = (
                score_repair(task, arm, answer)
                if task["kind"] == "compile_repair"
                else score_reasoning(task, answer)
            )
            rows.append(
                {
                    "task": task["id"],
                    "arm": arm,
                    "kind": task["kind"],
                    "status": "scored",
                    "objective": objective,
                    "rubric": rubric_packet(task, arm, answer),
                }
            )

    report = {
        "suite": spec["suite"],
        "scored_at": datetime.now(timezone.utc).isoformat(),
        "note": (
            "objective = mechanical checks only. rubric = pending external "
            "review; not scored here and must not be reported as a number."
        ),
        "rows": rows,
    }
    out_path = RESULTS / "scores.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    if args.json:
        print(json.dumps(report, indent=2))
        return 0

    print(f"{'task':<5} {'arm':<10} {'objective':<38} rubric")
    print("-" * 78)
    for r in rows:
        if r["status"] == "missing_answer":
            print(f"{r['task']:<5} {r['arm']:<10} {'(no answer yet)':<38} -")
            continue
        o = r["objective"]
        if o["metric"] == "anchor_coverage":
            cov = o["coverage"]
            summary = f"anchors {o['anchors_hit']}/{o['anchors_total']}  cov={cov}"
        else:
            ok = o.get("compiles")
            scope = "scope_ok" if not o.get("extra_files_touched") else "scope_wide"
            rt = "rt_ok" if o.get("return_type_preserved") else "rt_BROKEN"
            summary = f"compiles={ok}  {scope}  {rt}"
        print(f"{r['task']:<5} {r['arm']:<10} {summary:<38} pending")

    missing = [r for r in rows if r["status"] == "missing_answer"]
    print(f"\nwrote {out_path.relative_to(SUITE)}")
    print(f"scored {len(rows) - len(missing)}/{len(rows)} arms")
    if missing:
        print("rubric scores are pending external review and were NOT computed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
