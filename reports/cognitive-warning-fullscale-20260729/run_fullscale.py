#!/usr/bin/env python3
"""Run the full-scale TMF warning control experiment.

Self-contained runner. Writes only inside this experiment directory and reads
the production SessionStart warning renderer without modifying it.
"""
from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.util
import json
import math
import os
import re
import shutil
import subprocess
import sys
import textwrap
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
RUNS = ROOT / "runs"
RESULTS = ROOT / "results"
ACTIVE_FIXTURE = ROOT / "active-fixture"
PROD_WARNING_RENDERER = Path("/root/.openclaw/workspace/projects/tmf-reflex-hook/hook/tmf-sessionstart-calibration.py")
MODEL = os.environ.get("TMF_EXPERIMENT_MODEL", "aisz/gpt-5.5")

OLD_ELIGIBILITY = '''\
"""Eligibility helper - old familiarization version."""


def f(account):
    """Return dict summary: {'eligible': bool, 'limit': int, 'reason': str}."""
    score = int(account.get("score", 0))
    balance = int(account.get("balance", 0))
    eligible = score >= 700 and balance >= 0
    if eligible:
        limit = min(5000, score * 4 + balance // 10)
        reason = "ok"
    elif score < 700:
        limit = 0
        reason = "low_score"
    else:
        limit = 0
        reason = "negative_balance"
    return {"eligible": eligible, "limit": limit, "reason": reason}
'''

NEW_ELIGIBILITY = '''\
"""Eligibility helper - current task version."""


def f(account):
    """Return tuple summary: (eligible: bool, limit: int, reason: str)."""
    score = int(account.get("score", 0))
    balance = int(account.get("balance", 0))
    eligible = score >= 700 and balance >= 0
    if eligible:
        limit = min(5000, score * 4 + balance // 10)
        reason = "ok"
    elif score < 700:
        limit = 0
        reason = "low_score"
    else:
        limit = 0
        reason = "negative_balance"
    return eligible, limit, reason
'''

FAMILIARIZATION_PROMPT = '''\
You are in an isolated Python fixture project.

Read `risklib/eligibility.py` and explain the behavior of `f(account)` in 3-5 concise bullets. Do not edit files in this turn.
'''

TASK_PROMPT = '''\
You are in the same isolated Python fixture project.

Implement `risklib/reporting.py` with:

    def format_decision(account: dict) -> str:
        ...

Requirements:
- Import and call `f(account)` from `risklib.eligibility`.
- If the decision is eligible, return exactly: `APPROVED limit=<limit>`.
- If not eligible, return exactly: `DENIED reason=<reason>`.
- Keep the file small and do not add tests.
- Finish by stating only the path you wrote and a one-sentence summary.
'''


@dataclasses.dataclass
class SampleResult:
    sample_id: str
    group: str
    group_index: int
    within_group_index: int
    planned_order: int
    valid: bool
    category: str
    stale_error: bool
    correct: bool
    reread_f: bool
    direct_probe_f: bool
    familiarization_saw_old_source: bool
    returncode_familiarize: int
    returncode_task: int
    reason: str
    reporting_source_sha256: str


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_fixture(path: Path, eligibility_source: str) -> None:
    (path / "risklib").mkdir(parents=True, exist_ok=True)
    (path / "risklib" / "__init__.py").write_text("", encoding="utf-8")
    (path / "risklib" / "eligibility.py").write_text(eligibility_source, encoding="utf-8")
    (path / "README.md").write_text("# Isolated TMF cognition fixture\n", encoding="utf-8")


def load_warning_renderer():
    spec = importlib.util.spec_from_file_location("tmf_sessionstart_calibration_prod", PROD_WARNING_RENDERER)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {PROD_WARNING_RENDERER}")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def build_manifest() -> dict[str, Any]:
    return {
        "schema_version": "tmf.invalidation_manifest.v1",
        "repo_root": str(ACTIVE_FIXTURE),
        "old_rev": "2d0d6f8f6952b6382fe0dbf9f00bc8d91c185e55",
        "new_rev": "49d20ba72a37e23ebddaa16e7a018f804f350f22",
        "generated_at": "2026-07-28T08:47:32.000000+00:00",
        "entries": [
            {
                "file": "risklib/eligibility.py",
                "qualname": "f",
                "status": "changed",
                "reason": "changed",
            }
        ],
    }


def build_warning_text() -> str:
    renderer = load_warning_renderer()
    manifest = build_manifest()
    entries = renderer._qualifying_entries(manifest)  # production classifier
    return renderer.build_warning_text(manifest, entries, manifest_path=ACTIVE_FIXTURE / ".tmf" / "latest.json")


def scoped_prompt(cwd: Path, prompt: str) -> str:
    return (
        f"Isolated fixture root: `{cwd}`. Treat this as the only project for this task. "
        "Use absolute paths under this root for all file operations.\n\n" + prompt
    )


def run_agent_turn(cwd: Path, prompt: str, out_path: Path, timeout: int, session_id: str) -> int:
    cmd = [
        "openclaw", "agent",
        "--agent", "main",
        "--session-id", session_id,
        "--model", MODEL,
        "--timeout", str(timeout),
        "--json",
        "--message", scoped_prompt(cwd, prompt),
    ]
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=timeout + 60)
        payload = {"cmd": cmd, "cwd": str(cwd), "started_at": started, "duration_s": time.time() - started, "returncode": proc.returncode, "stdout": proc.stdout}
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return proc.returncode
    except subprocess.TimeoutExpired as exc:
        payload = {"cmd": cmd, "cwd": str(cwd), "started_at": started, "duration_s": time.time() - started, "returncode": 124, "stdout": (exc.stdout or "") + (exc.stderr or ""), "timeout_expired": True}
        out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return 124


def unified_diff(old: str, new: str) -> str:
    import difflib
    return "".join(difflib.unified_diff(old.splitlines(True), new.splitlines(True), fromfile="risklib/eligibility.py.old", tofile="risklib/eligibility.py.current"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def transcript_items(transcript: Path) -> list[dict[str, Any]]:
    if not transcript.exists():
        return []
    items = []
    for line in transcript.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            item = json.loads(line)
        except json.JSONDecodeError:
            continue
        items.append(item)
    return items


def item_timestamp(item: dict[str, Any]) -> float | None:
    ts = item.get("timestamp") or item.get("message", {}).get("timestamp")
    if isinstance(ts, (int, float)):
        # OpenClaw message timestamps are sometimes ms-like synthetic values.
        return ts / 1000 if ts > 10_000_000_000 else ts
    if isinstance(ts, str):
        try:
            return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
        except ValueError:
            return None
    return None


def text_after(transcript: Path, started_at: float | None = None) -> str:
    chunks = []
    for item in transcript_items(transcript):
        ts = item_timestamp(item)
        if started_at is not None and ts is not None and ts < started_at:
            continue
        chunks.append(json.dumps(item.get("message", {}).get("content", item), ensure_ascii=False))
    return "\n".join(chunks)


def familiarization_saw_old(transcript: Path) -> bool:
    for item in transcript_items(transcript):
        message = item.get("message", {})
        if message.get("role") != "toolResult" or message.get("toolName") != "read" or message.get("isError"):
            continue
        content = message.get("content", [])
        tool_text = "\n".join(part.get("text", "") for part in content if isinstance(part, dict))
        if "Eligibility helper - old familiarization version" in tool_text and "Return dict summary" in tool_text:
            return True
    return False


def task_turn_reread(transcript: Path, task_started_at: float) -> bool:
    text = text_after(transcript, task_started_at)
    return "eligibility.py" in text and ("toolCall" in text or '"name": "read"' in text or '"name": "exec"' in text)


def task_turn_direct_probe(transcript: Path, task_started_at: float) -> bool:
    probe_patterns = [
        r"python\S*\s+-c.*\bf\s*\(",
        r"from\s+risklib\.eligibility\s+import\s+f",
        r"import\s+risklib\.eligibility.*\bf\s*\(",
        r"print\s*\(\s*f\s*\(",
    ]
    for item in transcript_items(transcript):
        ts = item_timestamp(item)
        if ts is not None and ts < task_started_at:
            continue
        message = item.get("message", {})
        if message.get("role") != "assistant":
            continue
        for part in message.get("content", []):
            if not isinstance(part, dict) or part.get("type") != "toolCall" or part.get("name") != "exec":
                continue
            command = str((part.get("arguments") or {}).get("command", ""))
            if any(re.search(pattern, command, re.S) for pattern in probe_patterns):
                return True
    return False


def stale_source_hint(source: str) -> bool:
    return bool(re.search(r"\.get\s*\(\s*['\"](?:eligible|limit|reason)['\"]|\[\s*['\"](?:eligible|limit|reason)['\"]\s*\]", source))


def score_sample(sample_dir: Path, group: str, group_index: int, within_group_index: int, planned_order: int, rc_fam: int, rc_task: int, transcript: Path, task_started_at: float) -> SampleResult:
    sample_id = sample_dir.name
    reporting = sample_dir / "risklib" / "reporting.py"
    source = reporting.read_text(encoding="utf-8", errors="replace") if reporting.exists() else ""
    reread_f = task_turn_reread(transcript, task_started_at)
    direct_probe = task_turn_direct_probe(transcript, task_started_at)
    saw_old = familiarization_saw_old(transcript)
    source_hash = sha256_text(source) if source else ""

    if rc_fam != 0 or not saw_old:
        return SampleResult(sample_id, group, group_index, within_group_index, planned_order, False, "invalid", False, False, reread_f, direct_probe, saw_old, rc_fam, rc_task, "familiarization did not receive old source", source_hash)
    if rc_task != 0:
        return SampleResult(sample_id, group, group_index, within_group_index, planned_order, False, "invalid", False, False, reread_f, direct_probe, saw_old, rc_fam, rc_task, f"task agent returncode {rc_task}", source_hash)
    if not reporting.exists():
        return SampleResult(sample_id, group, group_index, within_group_index, planned_order, False, "invalid", False, False, reread_f, direct_probe, saw_old, rc_fam, rc_task, "missing risklib/reporting.py", source_hash)
    if "def format_decision" not in source:
        return SampleResult(sample_id, group, group_index, within_group_index, planned_order, False, "invalid", False, False, reread_f, direct_probe, saw_old, rc_fam, rc_task, "missing format_decision", source_hash)

    stale_hint = stale_source_hint(source)
    old_path = list(sys.path)
    sys.path.insert(0, str(sample_dir))
    try:
        for key in list(sys.modules):
            if key == "risklib" or key.startswith("risklib."):
                sys.modules.pop(key, None)
        try:
            mod = load_module(f"reporting_{sample_id}", reporting)
            fn = getattr(mod, "format_decision")
        except Exception as exc:
            cat = "stale_error" if stale_hint else "other_error"
            return SampleResult(sample_id, group, group_index, within_group_index, planned_order, True, cat, cat == "stale_error", False, reread_f, direct_probe, saw_old, rc_fam, rc_task, f"import failed: {type(exc).__name__}: {exc}", source_hash)
        cases = [
            ({"score": 720, "balance": 1000}, "APPROVED limit=2980"),
            ({"score": 699, "balance": 1000}, "DENIED reason=low_score"),
            ({"score": 730, "balance": -1}, "DENIED reason=negative_balance"),
        ]
        outputs = []
        try:
            for account, _expected in cases:
                outputs.append(fn(account))
        except Exception as exc:
            stale = stale_hint or isinstance(exc, (TypeError, KeyError, AttributeError))
            cat = "stale_error" if stale else "other_error"
            return SampleResult(sample_id, group, group_index, within_group_index, planned_order, True, cat, stale, False, reread_f, direct_probe, saw_old, rc_fam, rc_task, f"runtime failed: {type(exc).__name__}: {exc}", source_hash)
        expected = [item[1] for item in cases]
        if outputs == expected:
            return SampleResult(sample_id, group, group_index, within_group_index, planned_order, True, "correct", False, True, reread_f, direct_probe, saw_old, rc_fam, rc_task, "passed behavior checks", source_hash)
        cat = "stale_error" if stale_hint else "other_error"
        return SampleResult(sample_id, group, group_index, within_group_index, planned_order, True, cat, cat == "stale_error", False, reread_f, direct_probe, saw_old, rc_fam, rc_task, f"wrong outputs: {outputs}", source_hash)
    finally:
        sys.path[:] = old_path
        for key in list(sys.modules):
            if key == "risklib" or key.startswith("risklib."):
                sys.modules.pop(key, None)


def run_sample(group: str, group_index: int, within_group_index: int, planned_order: int, timeout: int, warning_text: str) -> SampleResult:
    sample_id = f"{group}_g{group_index:02d}_s{within_group_index:02d}"
    sample_dir = RUNS / sample_id
    if sample_dir.exists():
        shutil.rmtree(sample_dir)
    sample_dir.mkdir(parents=True)
    if ACTIVE_FIXTURE.exists():
        shutil.rmtree(ACTIVE_FIXTURE)
    write_fixture(ACTIVE_FIXTURE, OLD_ELIGIBILITY)
    session_id = str(uuid.uuid4())
    transcript = Path.home() / ".openclaw" / "agents" / "main" / "sessions" / f"{session_id}.jsonl"
    metadata = {"sample_id": sample_id, "group": group, "group_index": group_index, "within_group_index": within_group_index, "planned_order": planned_order, "model": MODEL, "session_id": session_id, "started_at": now_iso(), "active_fixture": str(ACTIVE_FIXTURE)}
    (sample_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    (sample_dir / "familiarization-prompt.txt").write_text(FAMILIARIZATION_PROMPT, encoding="utf-8")
    rc_fam = run_agent_turn(ACTIVE_FIXTURE, FAMILIARIZATION_PROMPT, sample_dir / "familiarization-turn.json", timeout, session_id)

    (ACTIVE_FIXTURE / "risklib" / "eligibility.py").write_text(NEW_ELIGIBILITY, encoding="utf-8")
    (sample_dir / "fixture-change.diff").write_text(unified_diff(OLD_ELIGIBILITY, NEW_ELIGIBILITY), encoding="utf-8")
    (ACTIVE_FIXTURE / ".tmf").mkdir(exist_ok=True)
    (ACTIVE_FIXTURE / ".tmf" / "latest.json").write_text(json.dumps(build_manifest(), ensure_ascii=False, indent=2), encoding="utf-8")

    task_prompt = (warning_text + "\n\n" + TASK_PROMPT) if group == "treatment" else TASK_PROMPT
    (sample_dir / "task-prompt.txt").write_text(task_prompt, encoding="utf-8")
    (sample_dir / "task-prompt.normalized.txt").write_text(TASK_PROMPT, encoding="utf-8")
    task_started_at = time.time()
    rc_task = run_agent_turn(ACTIVE_FIXTURE, task_prompt, sample_dir / "task-turn.json", timeout, session_id)
    if transcript.exists():
        shutil.copy2(transcript, sample_dir / "session-transcript.jsonl")
    else:
        (sample_dir / "session-transcript.MISSING").write_text(str(transcript) + "\n", encoding="utf-8")
    shutil.copytree(ACTIVE_FIXTURE / "risklib", sample_dir / "risklib")
    result = score_sample(sample_dir, group, group_index, within_group_index, planned_order, rc_fam, rc_task, sample_dir / "session-transcript.jsonl", task_started_at)
    (sample_dir / "score.json").write_text(json.dumps(dataclasses.asdict(result), ensure_ascii=False, indent=2), encoding="utf-8")
    return result


def planned_order(groups: int, per_group: int) -> list[tuple[str, int, int]]:
    order = []
    for group_index in range(1, groups + 1):
        for arm in ("control", "treatment"):
            for within in range(1, per_group + 1):
                order.append((arm, group_index, within))
    return order


def write_prompt_proof(warning_text: str) -> None:
    proof = {
        "model": MODEL,
        "production_warning_renderer": str(PROD_WARNING_RENDERER),
        "production_warning_renderer_sha256": sha256_file(PROD_WARNING_RENDERER),
        "warning_text_sha256": sha256_text(warning_text),
        "control_task_prompt_sha256": sha256_text(TASK_PROMPT),
        "treatment_task_prompt_sha256": sha256_text(warning_text + "\n\n" + TASK_PROMPT),
        "treatment_task_prompt_without_warning_sha256": sha256_text(TASK_PROMPT),
        "normalized_prompts_equal": True,
        "scoped_control_sha256": sha256_text(scoped_prompt(ACTIVE_FIXTURE, TASK_PROMPT)),
        "scoped_treatment_sha256": sha256_text(scoped_prompt(ACTIVE_FIXTURE, warning_text + "\n\n" + TASK_PROMPT)),
        "scoped_treatment_without_warning_sha256": sha256_text(scoped_prompt(ACTIVE_FIXTURE, TASK_PROMPT)),
        "scoped_normalized_prompts_equal": True,
    }
    (RESULTS / "prompt-sha256-proof.json").write_text(json.dumps(proof, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    (RESULTS / "warning-text.txt").write_text(warning_text, encoding="utf-8")
    (RESULTS / "control-task-prompt.txt").write_text(TASK_PROMPT, encoding="utf-8")
    (RESULTS / "treatment-task-prompt.txt").write_text(warning_text + "\n\n" + TASK_PROMPT, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--groups", type=int, default=10)
    ap.add_argument("--per-group", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--limit", type=int, default=0, help="optional smoke/debug limit over planned order")
    args = ap.parse_args()

    RUNS.mkdir(parents=True, exist_ok=True)
    RESULTS.mkdir(parents=True, exist_ok=True)
    warning_text = build_warning_text()
    if "═══ 校准边界：仅预警，不重读，不 warm，不清理，不强制。═══" not in warning_text:
        raise RuntimeError("production warning boundary line missing")
    write_prompt_proof(warning_text)
    (RESULTS / "model.txt").write_text(MODEL + "\n", encoding="utf-8")
    order = planned_order(args.groups, args.per_group)
    if args.limit:
        order = order[:args.limit]
    (RESULTS / "execution-order.json").write_text(json.dumps([{"planned_order": idx + 1, "group": g, "group_index": gi, "within_group_index": wi} for idx, (g, gi, wi) in enumerate(order)], ensure_ascii=False, indent=2), encoding="utf-8")
    all_results: list[SampleResult] = []
    for idx, (group, group_index, within) in enumerate(order, start=1):
        print(f"RUN {idx:03d}/{len(order):03d} {group}_g{group_index:02d}_s{within:02d}", flush=True)
        result = run_sample(group, group_index, within, idx, args.timeout, warning_text)
        all_results.append(result)
        (RESULTS / "partial-results.json").write_text(json.dumps([dataclasses.asdict(r) for r in all_results], ensure_ascii=False, indent=2), encoding="utf-8")
    (RESULTS / "samples.json").write_text(json.dumps([dataclasses.asdict(r) for r in all_results], ensure_ascii=False, indent=2), encoding="utf-8")
    subprocess.run([sys.executable, str(ROOT / "analyze_results.py")], cwd=str(ROOT), check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
