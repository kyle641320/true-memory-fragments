#!/usr/bin/env python3
"""
Validate that guava_cognitive_v1 suite is ready for human pilot.

Exit 0 if ready, nonzero otherwise.
"""
import json
import sys
from pathlib import Path

SUITE = Path(__file__).parent
FIXTURES = SUITE / "fixtures"
RESULTS = SUITE / "results"
PROMPTS = RESULTS / "prompts"


def main():
    issues = []

    # 1) tasks.json parseable and has 3 tasks
    tj = SUITE / "tasks.json"
    if not tj.exists():
        issues.append(f"missing {tj.relative_to(SUITE)}")
    else:
        try:
            tasks = json.loads(tj.read_text())["tasks"]
            if len(tasks) != 3:
                issues.append(f"tasks.json: expected 3 tasks, got {len(tasks)}")
        except Exception as e:
            issues.append(f"tasks.json parse: {e}")

    # 2) fixtures exist, with the variants each task type actually consumes.
    #
    # Only compile-repair tasks (those with a "mutation" field) get a mutated
    # work/ tree. Analysis tasks read the pristine base/ tree, so requiring
    # work/ for them would be a false alarm.
    wanted = {}
    if tj.exists():
        try:
            for t in json.loads(tj.read_text())["tasks"]:
                tid = t["id"]
                wanted.setdefault(tid, set()).add("base")
                if "mutation" in t:
                    wanted[tid].add("work")
        except Exception:
            pass  # tasks.json problems already reported above

    if not FIXTURES.exists():
        issues.append(f"missing {FIXTURES.relative_to(SUITE)}")
    else:
        for tid, variants in sorted(wanted.items()):
            for variant in sorted(variants):
                vdir = FIXTURES / tid / variant
                if not vdir.is_dir():
                    issues.append(f"missing {vdir.relative_to(SUITE)}")
                elif not list(vdir.glob("*.java")):
                    issues.append(f"no .java in {vdir.relative_to(SUITE)}")

    # 3) classpath.txt exists and is non-empty
    cp = SUITE / "classpath.txt"
    if not cp.exists():
        issues.append(f"missing {cp.relative_to(SUITE)}")
    elif not cp.read_text().strip():
        issues.append(f"{cp.relative_to(SUITE)} is empty")

    # 4) run_index.json exists, has 9 runs, all retrieval_ok=True
    idx = RESULTS / "run_index.json"
    if not idx.exists():
        issues.append(f"missing {idx.relative_to(SUITE)}")
    else:
        try:
            data = json.loads(idx.read_text())
            runs = data.get("runs", [])
            if len(runs) != 9:
                issues.append(f"run_index: expected 9 runs, got {len(runs)}")
            for r in runs:
                if not r.get("retrieval_ok"):
                    issues.append(
                        f"run {r['task']}__{r['arm']}: retrieval_ok={r.get('retrieval_ok')}"
                    )
        except Exception as e:
            issues.append(f"run_index parse: {e}")

    # 5) each run must have a .prompt.txt and .retrieval.json
    if idx.exists():
        try:
            data = json.loads(idx.read_text())
            for r in data.get("runs", []):
                stem = f"{r['task']}__{r['arm']}"
                prompt_file = PROMPTS / f"{stem}.prompt.txt"
                retr_file = PROMPTS / f"{stem}.retrieval.json"
                if not prompt_file.exists():
                    issues.append(f"missing {prompt_file.relative_to(SUITE)}")
                if not retr_file.exists():
                    issues.append(f"missing {retr_file.relative_to(SUITE)}")
                elif retr_file.exists():
                    try:
                        json.loads(retr_file.read_text())
                    except Exception as e:
                        issues.append(
                            f"{retr_file.relative_to(SUITE)} invalid: {e}"
                        )
        except Exception:
            pass  # already reported parse issue

    # 6) PROTOCOL.md must exist
    proto = SUITE / "PROTOCOL.md"
    if not proto.exists():
        issues.append(f"missing {proto.relative_to(SUITE)}")

    if issues:
        print("VALIDATION FAILED")
        for i in issues:
            print(f"  ✗ {i}")
        return 1

    print("✓ guava_cognitive_v1 suite is ready for human pilot.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
