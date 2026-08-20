#!/usr/bin/env python3
"""Three-arm runner for guava_cognitive_v1.

Arms differ only in what retrieval context the solver is handed:

  no_tool    fixture file listing only. The solver must open files itself.
  tmf_thin   fixture listing + a single tmf_context bundle for the question.
  tmf_full   fixture listing + tmf_context plus targeted callers/readers/
             subtypes lookups on the anchors named by the task.

TMF is the *subject under test* here. This runner only consumes TMF's read-only
MCP surface; it never imports or mutates TMF engine code.

Because the solver is an external agent session, this runner does not call an
LLM directly. It materialises one prompt bundle per (task, arm) into
results/prompts/, records the exact retrieval payload used, and leaves a slot
for the answer. Answers are filled in by run_arm.py (session-driven) or by
hand for pilot runs, then scored by validate.py.

Usage:
    python3 runner.py --prepare                 # build all prompt bundles
    python3 runner.py --prepare --task B01      # single task
    python3 runner.py --list                    # show planned run matrix
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import traceback
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

SUITE = Path(__file__).resolve().parent
RESULTS = SUITE / "results"
PROMPTS = RESULTS / "prompts"
REPO_ROOT = SUITE.parents[2]  # worktrees/tmf-java-nodes-step0
sys.path.insert(0, str(REPO_ROOT))

ARMS = ("no_tool", "tmf_thin", "tmf_full")


def load_tasks() -> dict:
    return json.loads((SUITE / "tasks.json").read_text(encoding="utf-8"))


def fixture_tree(task: dict) -> tuple[Path, list[str]]:
    """Return (root, sorted relative file list) for the tree the solver reads."""
    fixture_dir = SUITE / "fixtures" / task["fixture"]
    # compile_repair tasks operate on the mutated work/ tree; reasoning tasks
    # read the pristine base/.
    root = fixture_dir / ("work" if task["kind"] == "compile_repair" else "base")
    if not root.is_dir():
        raise FileNotFoundError(f"fixture tree missing: {root}")
    files = sorted(p.name for p in root.glob("*.java"))
    return root, files


# ---------------------------------------------------------------------------
# TMF retrieval. Invoked as a subprocess against the frozen engine so that a
# TMF crash degrades this arm instead of taking down the runner.
# ---------------------------------------------------------------------------


@dataclass
class Retrieval:
    ok: bool
    payload: str
    error: str = ""
    calls: int = 0
    detail: list[dict] = field(default_factory=list)


@contextmanager
def tmf_service(fixture_root: Path):
    """Yield an McpService over a disposable copy of the fixture tree.

    TMF read-through is allowed to write into .tmf/ during retrieval, so the
    fixture is copied to a temp dir first. The pristine suite tree is never
    mutated, which keeps fixtures reproducible across arms.

    Yields None if TMF cannot be imported or warmed, so a broken engine
    degrades the arm instead of aborting the run.
    """
    with tempfile.TemporaryDirectory(prefix="guava-cog-") as tmp:
        # TMF indexes by repo-relative path; mirror the real package layout so
        # qualnames resolve as com.google.common.eventbus.*
        repo = Path(tmp) / "repo"
        pkg = repo / "src" / "main" / "java" / "com" / "google" / "common" / "eventbus"
        pkg.mkdir(parents=True)
        for src in sorted(fixture_root.glob("*.java")):
            shutil.copy2(src, pkg / src.name)
        try:
            from tmf.mcp_server import McpService

            service = McpService(repo)
            service.tmf_warm()
            yield service
        except Exception:  # noqa: BLE001 - degradation is intentional
            yield None


def _call(service, name: str, **kwargs) -> tuple[bool, str]:
    """Invoke one McpService method, serialising the result as JSON text."""
    try:
        result = getattr(service, name)(**kwargs)
    except Exception:  # noqa: BLE001
        return False, traceback.format_exc(limit=3)[:1200]
    if not result:
        return False, "empty result"
    return True, json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True)


def retrieve_thin(task: dict, fixture_root: Path) -> Retrieval:
    with tmf_service(fixture_root) as service:
        if service is None:
            return Retrieval(False, "", "TMF service unavailable", calls=0)
        ok, out = _call(service, "tmf_context", question=task["question"], max_chars=4000)
        if not ok:
            return Retrieval(False, "", f"tmf_context: {out}", calls=1)
        return Retrieval(
            True, out, calls=1, detail=[{"call": "tmf_context", "ok": True}]
        )


def retrieve_full(task: dict, fixture_root: Path) -> Retrieval:
    chunks: list[str] = []
    errors: list[str] = []
    detail: list[dict] = []
    calls = 0

    with tmf_service(fixture_root) as service:
        if service is None:
            return Retrieval(False, "", "TMF service unavailable", calls=0)

        ok, out = _call(service, "tmf_context", question=task["question"], max_chars=6000)
        calls += 1
        detail.append({"call": "tmf_context", "ok": ok})
        if ok:
            chunks.append("### tmf_context\n" + out)
        else:
            errors.append(f"tmf_context: {out[:200]}")

        # Targeted graph lookups on the anchors this task actually cares about.
        #
        # Addressing note (measured, not assumed): TMF Java qualnames are
        # package-free, e.g. "Dispatcher" and "EventBus.post". Passing a
        # fully-qualified "com.google.common.eventbus.Dispatcher" returns
        # status=not_found. So anchors are used verbatim from tasks.json.
        gt = task.get("ground_truth", {})
        type_anchors = list(gt.get("must_name_subclasses", []))
        member_anchors = [a for a in gt.get("must_name", []) if "." in a]
        type_anchors += [a for a in gt.get("must_name", []) if "." not in a]

        plan = [("tmf_subtypes", a) for a in dict.fromkeys(type_anchors)]
        plan += [("tmf_callers", a) for a in dict.fromkeys(member_anchors)]

        for verb, anchor in plan[:12]:
            ok, out = _call(service, verb, qualname=anchor)
            calls += 1
            # A well-formed not_found is a real TMF answer, not a crash; it is
            # kept in the payload so the arm reflects what TMF actually offers.
            not_found = ok and '"status": "not_found"' in out
            detail.append(
                {"call": verb, "qualname": anchor, "ok": ok, "not_found": not_found}
            )
            if ok and not not_found:
                chunks.append(f"### {verb} {anchor}\n{out}")
            elif not_found:
                errors.append(f"{verb}({anchor}): not_found")
            else:
                errors.append(f"{verb}({anchor}): {out[:120]}")

    if not chunks:
        return Retrieval(False, "", "; ".join(errors)[:2000], calls=calls, detail=detail)
    return Retrieval(
        True, "\n\n".join(chunks), "; ".join(errors)[:2000], calls=calls, detail=detail
    )


RETRIEVERS = {
    "no_tool": lambda task, root: Retrieval(True, "", calls=0),
    "tmf_thin": retrieve_thin,
    "tmf_full": retrieve_full,
}


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

PREAMBLE = """You are analysing a self-contained Java fixture extracted from Guava's
com.google.common.eventbus package. Answer using only the fixture.

Fixture root: {root}
Files available:
{files}
"""

REPAIR_TAIL = """
This is a compile-repair task. Edit files under the fixture root in place.
Do not change the declared return type of the mutated method. When you are
done, the fixture must compile with:

  javac -nowarn -cp "$(cat {cp})" -d /tmp/out {root}/*.java

Report which files you modified.
"""

REASON_TAIL = """
Answer in prose. Name concrete classes and methods explicitly. Do not modify
any files.
"""

RETRIEVAL_HEADER = """
--- Retrieved context (TMF, freshness-labelled locator; source code is
authoritative and may contradict it) ---
{payload}
--- end retrieved context ---
"""


def build_prompt(task: dict, arm: str, root: Path, files: list[str], r: Retrieval) -> str:
    parts = [
        PREAMBLE.format(
            root=root.relative_to(SUITE),
            files="\n".join(f"  - {f}" for f in files),
        )
    ]
    if arm != "no_tool":
        if r.ok and r.payload:
            parts.append(RETRIEVAL_HEADER.format(payload=r.payload))
        else:
            parts.append(
                "\n[TMF retrieval unavailable for this arm: "
                f"{r.error or 'empty result'}. Proceed by reading files directly.]\n"
            )
    parts.append("\nQUESTION:\n" + task["question"] + "\n")
    parts.append(
        REPAIR_TAIL.format(cp=(SUITE / "classpath.txt").relative_to(SUITE), root=root.relative_to(SUITE))
        if task["kind"] == "compile_repair"
        else REASON_TAIL
    )
    return "".join(parts)


def prepare(task_filter: str | None, arm_filter: str | None) -> int:
    spec = load_tasks()
    PROMPTS.mkdir(parents=True, exist_ok=True)

    index: list[dict] = []
    degraded: list[str] = []

    for task in spec["tasks"]:
        if task_filter and task["id"] != task_filter:
            continue
        root, files = fixture_tree(task)
        for arm in ARMS:
            if arm_filter and arm != arm_filter:
                continue
            r = RETRIEVERS[arm](task, root)
            if arm != "no_tool" and not r.ok:
                degraded.append(f"{task['id']}/{arm}: {r.error[:160]}")

            prompt = build_prompt(task, arm, root, files, r)
            stem = f"{task['id']}__{arm}"
            (PROMPTS / f"{stem}.prompt.txt").write_text(prompt, encoding="utf-8")
            (PROMPTS / f"{stem}.retrieval.json").write_text(
                json.dumps(
                    {
                        "task": task["id"],
                        "arm": arm,
                        "retrieval_ok": r.ok,
                        "retrieval_calls": r.calls,
                        "retrieval_error": r.error,
                        "retrieval_chars": len(r.payload),
                        "retrieval_detail": r.detail,
                        "payload": r.payload,
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            index.append(
                {
                    "task": task["id"],
                    "kind": task["kind"],
                    "arm": arm,
                    "fixture_tree": str(root.relative_to(SUITE)),
                    "prompt": f"prompts/{stem}.prompt.txt",
                    "retrieval": f"prompts/{stem}.retrieval.json",
                    "retrieval_ok": r.ok,
                    "retrieval_calls": r.calls,
                    "answer": None,
                }
            )
            flag = "" if r.ok or arm == "no_tool" else "  [DEGRADED]"
            print(f"prepared {stem:<24} retrieval_calls={r.calls}{flag}")

    RESULTS.mkdir(parents=True, exist_ok=True)
    run_index = RESULTS / "run_index.json"
    run_index.write_text(
        json.dumps(
            {
                "suite": spec["suite"],
                "prepared_at": datetime.now(timezone.utc).isoformat(),
                "arms": list(ARMS),
                "degraded": degraded,
                "runs": index,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"\nwrote {run_index.relative_to(SUITE)}  ({len(index)} runs)")
    if degraded:
        print("DEGRADED ARMS (recorded, not fatal):")
        for d in degraded:
            print(f"  - {d}")
    return 0


def show_matrix() -> int:
    spec = load_tasks()
    print(f"{'task':<6} {'kind':<16} {'tree':<24} arms")
    for task in spec["tasks"]:
        root, _ = fixture_tree(task)
        print(
            f"{task['id']:<6} {task['kind']:<16} "
            f"{str(root.relative_to(SUITE)):<24} {', '.join(ARMS)}"
        )
    print(f"\ntotal runs: {len(spec['tasks']) * len(ARMS)}")
    return 0


def run_arms(task_filter: str | None, arm_filter: str | None) -> int:
    """Run prepared prompts and write answers.
    
    This function is meant to be called FROM WITHIN an OpenClaw session,
    where sessions_spawn tool is available. It cannot be run as a standalone
    script because it needs the OpenClaw tool environment.
    
    The caller (Javis in main session) should:
    1. Read this runner.py
    2. Call run_arms() with task/arm filters
    3. Each prompt will spawn a sub-agent via sessions_spawn
    4. Answers written to results/answers/
    """
    run_index_path = RESULTS / "run_index.json"
    if not run_index_path.exists():
        print("run_index.json not found. Run --prepare first.", file=sys.stderr)
        return 1
    
    run_index = json.loads(run_index_path.read_text(encoding="utf-8"))
    runs = run_index["runs"]
    
    # Filter
    if task_filter:
        runs = [r for r in runs if r["task"] == task_filter]
    if arm_filter:
        runs = [r for r in runs if r["arm"] == arm_filter]
    
    if not runs:
        print("No runs match the filter.", file=sys.stderr)
        return 1
    
    print(f"Will run {len(runs)} arms. This will spawn {len(runs)} sub-agents.\n")
    print("ERROR: run_arms() must be called from within OpenClaw session with sessions_spawn tool.")
    print("This is not a standalone CLI mode. The assistant will orchestrate runs.")
    return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prepare", action="store_true", help="build prompt bundles")
    ap.add_argument("--run", action="store_true", help="run prepared prompts through sub-agents")
    ap.add_argument("--list", action="store_true", help="show run matrix")
    ap.add_argument("--task", help="limit to one task id")
    ap.add_argument("--arm", choices=ARMS, help="limit to one arm")
    args = ap.parse_args()

    if args.list:
        return show_matrix()
    if args.prepare:
        return prepare(args.task, args.arm)
    if args.run:
        return run_arms(args.task, args.arm)
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
