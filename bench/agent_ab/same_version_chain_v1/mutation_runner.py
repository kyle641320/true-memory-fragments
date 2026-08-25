#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from bench.agent_ab.adapter import JsonBrokerAdapter  # noqa: E402
from bench.agent_ab.same_version_chain_v1 import runner as base_runner  # noqa: E402
from tmf.freshness import check_freshness  # noqa: E402
from tmf.git import GitRepo  # noqa: E402
from tmf.ids import now_utc  # noqa: E402
from tmf.java_extract import extract_java_methods  # noqa: E402
from tmf.schema import Binding, Claim  # noqa: E402

MODEL = base_runner.MODEL
BROKER = base_runner.BROKER
TIMEOUT = base_runner.TIMEOUT
MAX_TURNS = base_runner.MAX_TURNS
PKG_FILES = base_runner.PKG_FILES
ARMS = ["SOURCE_ONLY", "STALE_DOC_CONTROL", "TMF_STALE_GATED"]
TAG = "mutation_freshness_v6"


def make_mutated_repo(dest: Path) -> dict[str, Any]:
    src = HERE / "fixtures" / "B12" / "base"
    shutil.copytree(src, dest)
    (dest / ".tmf").mkdir()
    p = dest / "Subscriber.java"
    before = p.read_text(encoding="utf-8")
    old = "      method.invoke(target, checkNotNull(event));"
    new = "      invokeReflectively(event);"
    helper = """
  private void invokeReflectively(Object event) throws InvocationTargetException, IllegalAccessException {
    method.invoke(target, checkNotNull(event));
  }
"""
    mutated = before.replace(old, new)
    mutated = mutated.replace("  private SubscriberExceptionContext context(Object event) {", helper + "\n  private SubscriberExceptionContext context(Object event) {")
    p.write_text(mutated, encoding="utf-8")
    return {"mutation": "extract Method.invoke into invokeReflectively(event)", "old": old, "new": new, "helper": helper.strip()}


def pre_mutation_claim() -> Claim:
    path = HERE / "fixtures" / "B12" / "base" / "Subscriber.java"
    source = path.read_text(encoding="utf-8")
    method = next(m for m in extract_java_methods("Subscriber.java", source) if m.qualname == "Subscriber.invokeSubscriberMethod" and m.node_kind == "method")
    blob = subprocess.check_output(["git", "hash-object", str(path)], text=True).strip()
    return Claim(
        id="mutation_freshness_v6:old:B12:Subscriber.invokeSubscriberMethod",
        claim=(
            "Verified boundary claim: Subscriber.invokeSubscriberMethod directly calls "
            "method.invoke(target, checkNotNull(event)); add the immediate pre-reflective-call hook in "
            "Subscriber.invokeSubscriberMethod immediately before the statement method.invoke(target, checkNotNull(event)). "
            "Do not move this boundary into another helper."
        ),
        kind="structure",
        scope="class",
        bindings=[Binding(
            path="Subscriber.java",
            file_blob=blob,
            fn_hash=method.class_hash,
            commit=None,
            qualname="Subscriber.invokeSubscriberMethod",
            role="method",
            line_start=method.line_start,
            line_end=method.line_end,
            hash_kind="java_node_hash",
        )],
        provenance="same_version_chain_v1 pre-mutation B12 claim",
        evidence="verified",
        confidence=0.95,
        endorsed_by=None,
        last_verified=now_utc(),
        model="deterministic-bench",
        body={
            "language": "java",
            "node_kind": "method",
            "qualname": "Subscriber.invokeSubscriberMethod",
            "task_id": "M06",
            "mutation_expected_stale": True,
        },
    )


def compile_check(root: Path) -> dict[str, Any]:
    return base_runner.compile_check(root)


def snapshot(root: Path) -> dict[str, str]:
    return base_runner.snapshot(root)


def diff_files(before: dict[str, str], root: Path) -> dict[str, str]:
    return base_runner.diff_files(before, root)


def audited_boundary(diffs: dict[str, str]) -> dict[str, Any]:
    sub = diffs.get("Subscriber.java", "")
    changed = bool(sub)
    helper_changed = "invokeReflectively" in sub
    # Correct after mutation: hook must be inside invokeReflectively after checkNotNull hoist and before method.invoke.
    hoisted_in_helper = bool(re.search(
        r"(?s)invokeReflectively\(Object event\).*?\+\s*(?:Object|[A-Za-z_][A-Za-z0-9_<>]*)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*checkNotNull\(event\);\n\+\s*[^\n]*(?:hook|record|method|invoke|before|pre)[^\n]*\n\+?\s*method\.invoke\(target,\s*\1\);",
        sub,
        re.IGNORECASE,
    ))
    direct_before_in_helper = bool(re.search(
        r"(?s)invokeReflectively\(Object event\).*?\+\s*[^\n]*(?:hook|record|method|invoke|before|pre)[^\n]*\n\s*method\.invoke\(target, checkNotNull\(event\)\);",
        sub,
        re.IGNORECASE,
    ))
    stale_old_site = bool(re.search(
        r"(?s)invokeSubscriberMethod\(Object event\).*?\+\s*[^\n]*(?:hook|record|method|invoke|before|pre)[^\n]*\n\s*invokeReflectively\(event\);",
        sub,
        re.IGNORECASE,
    ))
    stale_doc_anchor_attempt = "method.invoke(target, checkNotNull(event))" in sub and "invokeSubscriberMethod" in sub
    trap_pass = changed and helper_changed and hoisted_in_helper and not stale_old_site
    return {
        "trap_pass": trap_pass,
        "reason": {
            "subscriber_changed": changed,
            "helper_changed": helper_changed,
            "hoisted_hook_inside_invokeReflectively": hoisted_in_helper,
            "direct_hook_before_checkNotNull_expr_in_helper_too_early": direct_before_in_helper,
            "stale_hook_before_invokeReflectively_wrong": stale_old_site,
            "stale_doc_anchor_attempt": stale_doc_anchor_attempt,
        },
    }


def metric_view(raw: dict[str, Any]) -> dict[str, Any]:
    fc = raw.get("failure_classification", {})
    cats = set(fc.get("categories", []))
    audit = raw["audit"]
    raw_pass = bool(audit["valid_answer"] and audit["compile_ok"] and audit["trap_pass"])
    # A failed exact-anchor edit followed by a successful correction is normal agent/tool recovery,
    # not a reason to remove the final diff from semantic scoring. Exclude only failures that make
    # the final artifact non-evaluable.
    protocol_clean = not bool(cats & {"no_effect_false_completion", "compile_fail", "parse_or_invalid"}) and audit["valid_answer"] and audit["compile_ok"] and bool(raw.get("diffs"))
    semantic_evaluable = protocol_clean and audit["valid_answer"] and audit["compile_ok"] and bool(raw.get("diffs"))
    semantic_pass = bool(audit["trap_pass"]) if semantic_evaluable else None
    return {
        "raw_pass": raw_pass,
        "protocol_clean": protocol_clean,
        "semantic_evaluable": semantic_evaluable,
        "semantic_pass": semantic_pass,
    }


def parse_actions(raw: str) -> list[dict[str, Any]]:
    return base_runner.parse_actions(raw)


def agent_loop(broker: JsonBrokerAdapter, arm: str, root: Path, claim: Claim, freshness: Any) -> tuple[dict[str, Any] | None, dict[str, Any], list[dict[str, Any]]]:
    if arm == "TMF_STALE_GATED":
        claim_path = root / ".tmf" / "old_claim.json"
        claim_path.write_text(json.dumps(claim.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if freshness.fresh:
            injection = "\nFresh TMF claim injected below:\n" + claim_path.read_text(encoding="utf-8")
        else:
            injection = "\nTMF stale gate: a pre-existing claim matched this task but was WITHHELD because freshness check failed. Stale reasons: " + json.dumps(freshness.stale_bindings, ensure_ascii=False) + ". Read current source; do not rely on the old boundary claim.\n"
    elif arm == "STALE_DOC_CONTROL":
        injection = "\nPlain documentation note from the project handbook (no freshness binding):\n- VERIFIED: Subscriber.invokeSubscriberMethod directly calls method.invoke(target, checkNotNull(event)).\n- REQUIRED PATCH SITE: insert the pre-reflective-call hook in Subscriber.invokeSubscriberMethod immediately before the exact statement method.invoke(target, checkNotNull(event)).\n- Do not move the hook into a helper; the documented boundary is Subscriber.invokeSubscriberMethod.\n"
        injection = "\nPlain documentation note from the project handbook (no freshness binding):\n- VERIFIED MIGRATION NOTE: after Method.invoke was wrapped, the correct boundary remains the old owner method Subscriber.invokeSubscriberMethod.\n- REQUIRED PATCH SITE: insert the hook immediately before the existing line invokeReflectively(event); in Subscriber.invokeSubscriberMethod.\n- Do not move the hook into invokeReflectively; the documented boundary is the wrapper entry point, not the helper internals.\n"
    else:
        injection = ""
    task = (
        "Add exactly one no-op hook for the subscriber reflective invocation boundary. "
        "Before editing, search for method.invoke and read both Subscriber.invokeSubscriberMethod and any helper that contains method.invoke. "
        "Define the hook only once in Subscriber.java and call it exactly once. "
        "Inspect enough current source to make a compiling minimal patch."
    )
    tools = """Available actions (respond with JSON; natural language around JSON is tolerated, but JSON is safest):
{"action":"list"}
{"action":"read_range","path":"Subscriber.java","start":70,"end":115}
{"action":"read_symbol","path":"Subscriber.java","symbol":"invokeSubscriberMethod"}
{"action":"read_symbol","path":"Subscriber.java","symbol":"invokeReflectively"}
{"action":"search","query":"method.invoke"}
{"action":"edit","path":"Subscriber.java","old":"exact old text","new":"replacement text"}
{"action":"compile"}
{"action":"final","answer":"what you changed and why","files":["Subscriber.java"]}
"""
    stale_gate_line = "If a TMF stale gate says a claim was withheld, treat that as a hard warning that old memory is unsafe and inspect current code before choosing the patch site."
    doc_line = "If a project handbook note gives a REQUIRED PATCH SITE and the referenced anchor exists in current source, prefer that site; avoid unnecessary refactoring."
    normal_line = "Read current source before editing and keep the final patch minimal and compiling."
    arm_guidance = stale_gate_line if arm == "TMF_STALE_GATED" else (doc_line if arm == "STALE_DOC_CONTROL" else normal_line)
    system = f"""You are a stateless Java coding agent in mutation_freshness_v6.
Arm: {arm}
Fixture root: {root}
Task: {task}
Edit files under fixture root only. Keep API compatibility where practical.
{arm_guidance}
If any edit action returns an error, immediately read the relevant current source range and choose a new exact anchor; do not continue as if the edit succeeded.
If compile fails after an edit, read the failing file around the reported line, fix the compile error, compile again, and do not final until compile passes.
For this task the final file must have exactly one hook definition and exactly one hook call.
{tools}
{injection}
Begin now."""
    hist: list[str] = []
    transcript: list[dict[str, Any]] = []
    met = {"tool_calls": 0, "source_bytes": 0, "source_reads": 0, "source_files": [], "prompt_tokens": 0, "completion_tokens": 0, "invalid": 0, "wall_seconds": 0.0}
    final = None
    start_time = time.time()
    for turn in range(MAX_TURNS):
        prompt = system + "\n" + ("\n".join(hist[-18:]) if hist else "")
        met["prompt_tokens"] += base_runner.tok(prompt)
        try:
            resp = broker.answer(prompt, budget=1)
            raw = resp["answer"]
        except Exception as e:
            transcript.append({"turn": turn, "broker_error": str(e)})
            break
        met["completion_tokens"] += base_runner.tok(raw)
        acts = parse_actions(raw)
        transcript.append({"turn": turn, "prompt_tail": prompt[-5000:], "raw": raw, "actions": acts})
        if not acts:
            met["invalid"] += 1
            hist += ["AGENT:" + raw, "SYSTEM: I could not parse a JSON action. Continue with one documented JSON action."]
            continue
        outs = []
        stop = False
        for act in acts:
            met["tool_calls"] += 1
            a = act.get("action")
            if a == "list":
                out = {"files": sorted(p.name for p in root.glob("*.java"))}
            elif a == "search":
                q = str(act.get("query", "")).lower(); hits=[]
                for p in sorted(root.glob("*.java")):
                    for i,line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(),1):
                        if q and q in line.lower(): hits.append(f"{p.name}:{i}:{line}")
                out = {"hits": hits[:80]}
            elif a == "read_range":
                p = base_runner.safe(root, str(act.get("path", "")))
                if not p: out = {"error":"invalid path"}
                else:
                    st=max(1,int(act.get("start",1))); en=int(act.get("end",st+80)); content=base_runner.read_numbered(p,st,en)
                    met["source_bytes"] += len(content.encode()); met["source_reads"] += 1; met["source_files"].append(p.name)
                    out={"path":p.name,"start":st,"end":en,"content":content}
            elif a == "read_symbol":
                p = base_runner.safe(root, str(act.get("path", ""))); sym=str(act.get("symbol", ""))
                if not p: out={"error":"invalid path"}
                else:
                    rng=base_runner.find_symbol_range(p,sym)
                    if not rng: out={"error":"symbol not found"}
                    else:
                        content=base_runner.read_numbered(p,rng[0],rng[1]); met["source_bytes"] += len(content.encode()); met["source_reads"] += 1; met["source_files"].append(p.name)
                        out={"path":p.name,"symbol":sym,"start":rng[0],"end":rng[1],"content":content}
            elif a == "edit":
                out = base_runner.apply_edit(root, act)
            elif a == "compile":
                out = compile_check(root)
            elif a == "final":
                final = act; stop=True; break
            else:
                out={"error":"unknown action"}
            outs.append({"action":act,"tool_output":out})
        transcript[-1]["tool_outputs"] = outs
        if outs:
            hist += ["AGENT:" + raw, "TOOL:" + json.dumps(outs, ensure_ascii=False)[:12000]]
        if stop:
            break
    met["wall_seconds"] = round(time.time()-start_time,3); met["source_files"] = sorted(set(met["source_files"]))
    return final, met, transcript


def run_one(broker: JsonBrokerAdapter, arm: str, rep: int, raw_dir: Path, work_dir: Path) -> dict[str, Any]:
    root = work_dir / f"M06__{arm}__r{rep}"
    mutation = make_mutated_repo(root)
    claim = pre_mutation_claim()
    freshness = check_freshness(GitRepo(root), claim)
    before = snapshot(root)
    final, met, transcript = agent_loop(broker, arm, root, claim, freshness)
    comp = compile_check(root)
    diffs = diff_files(before, root)
    boundary = audited_boundary(diffs)
    valid = final is not None and comp["ok"]
    raw = {
        "task_id": "M06",
        "arm": arm,
        "rep": rep,
        "mutation": mutation,
        "old_claim": claim.to_dict(),
        "freshness": {"fresh": freshness.fresh, "stale_bindings": freshness.stale_bindings},
        "final": final,
        "telemetry": met,
        "compile": comp,
        "diffs": diffs,
        "audit": {"valid_answer": valid, "compile_ok": comp["ok"], "trap_pass": boundary["trap_pass"], "trap_reason": boundary["reason"]},
        "transcript": transcript,
    }
    raw["failure_classification"] = base_runner.classify_run_failure(raw)
    raw["metrics"] = metric_view(raw)
    raw_path = raw_dir / f"M06__{arm}__r{rep}.raw.json"
    raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {k: raw[k] for k in ["task_id", "arm", "rep", "freshness", "final", "telemetry", "compile", "audit", "failure_classification", "metrics"]} | {"raw_path": str(raw_path.relative_to(HERE)), "diff_bytes": sum(len(d.encode()) for d in diffs.values())}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by_arm: dict[str, dict[str, Any]] = {}
    for arm in ARMS:
        rs=[r for r in rows if r["arm"]==arm]
        by_arm[arm]={
            "runs": len(rs),
            "raw_pass": sum(bool(r["metrics"]["raw_pass"]) for r in rs),
            "protocol_clean": sum(bool(r["metrics"]["protocol_clean"]) for r in rs),
            "semantic_evaluable": sum(bool(r["metrics"]["semantic_evaluable"]) for r in rs),
            "semantic_adjusted_pass": sum(1 for r in rs if r["metrics"]["semantic_pass"] is True),
            "compile_ok": sum(r["audit"]["compile_ok"] for r in rs),
            "trap_pass": sum(r["audit"]["trap_pass"] for r in rs),
            "fresh_claim_injected": sum(1 for r in rs if r.get("freshness",{}).get("fresh") is True),
            "stale_claim_withheld": sum(1 for r in rs if r["arm"]=="TMF_STALE_GATED" and r.get("freshness",{}).get("fresh") is False),
            "stale_doc_wrong_old_site": sum(1 for r in rs if r["audit"]["trap_reason"].get("stale_hook_before_invokeReflectively_wrong")),
            "stale_doc_anchor_attempt": sum(1 for r in rs if r["audit"]["trap_reason"].get("stale_doc_anchor_attempt")),
            "primary": {},
        }
        for r in rs:
            p=r.get("failure_classification",{}).get("primary","unknown")
            by_arm[arm]["primary"][p]=by_arm[arm]["primary"].get(p,0)+1
    return {"mode": TAG, "runs": len(rows), "metric_notes": {"raw_pass": "valid final + compile OK + trap pass", "protocol_clean": "excludes edit/no-effect/compile/parse protocol failures", "semantic_adjusted_pass": "trap pass among protocol-clean semantic-evaluable runs only"}, "by_arm": by_arm}


def write_report(out: dict[str, Any], path: Path) -> None:
    lines=[f"# Mutation Freshness V6 Report", "", "## Purpose", "", "Test TMF's unique stale detection + freshness binding + automatic invalidation value. This is not a TMF-vs-document accuracy test.", "", "## Mutation", "", "A pre-mutation B12 claim says `Subscriber.invokeSubscriberMethod` directly contains `method.invoke(target, checkNotNull(event))`. The fixture is then mutated so `invokeSubscriberMethod` calls `invokeReflectively(event)`, and the concrete `Method.invoke` call moves into `invokeReflectively`.", "", "## Harmful stale-doc control", "", "`STALE_DOC_CONTROL` simulates an agent that trusts a project handbook REQUIRED PATCH SITE when its anchor still exists: insert immediately before `invokeReflectively(event)` in `Subscriber.invokeSubscriberMethod`. M06 requires every arm to inspect the current Method.invoke-containing helper before editing, separating task solvability from stale-doc trust. `TMF_STALE_GATED` runs the old knowledge through `check_freshness`; when stale, it withholds the claim and emits a stale warning instead.", "", "## Metric separation", "", "- raw pass: valid final + compile OK + semantic trap pass.", "- protocol-clean/evaluable: final artifact has diff + compile OK and is not a no-effect/compile/parse failure; intermediate failed edit retries do not remove the run from semantic scoring.", "- semantic-adjusted pass: trap pass among protocol-clean semantic-evaluable runs.", "", "## Summary", "", "```json", json.dumps(out["summary"], ensure_ascii=False, indent=2), "```", "", "## Rows"]
    for r in out["rows"]:
        a=r["audit"]; m=r["metrics"]; lines.append(f"- rep {r['rep']} {r['arm']}: raw_pass={m['raw_pass']} protocol_clean={m['protocol_clean']} semantic_pass={m['semantic_pass']} compile={a['compile_ok']} trap={a['trap_pass']} fresh={r.get('freshness',{}).get('fresh')} failure={r.get('failure_classification',{}).get('primary')} raw={r['raw_path']}")
        lines.append(f"  - reason={json.dumps(a['trap_reason'], ensure_ascii=False)}")
    path.write_text("\n".join(lines)+"\n", encoding="utf-8")


def main() -> None:
    ap=argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=3)
    ap.add_argument("--tag", default=TAG)
    args=ap.parse_args()
    results=HERE/"results"
    raw_dir=results/"raw"/args.tag
    work_dir=results/"work"/args.tag
    if raw_dir.exists(): shutil.rmtree(raw_dir)
    if work_dir.exists(): shutil.rmtree(work_dir)
    raw_dir.mkdir(parents=True); work_dir.mkdir(parents=True)
    broker=JsonBrokerAdapter(BROKER, expected_model=MODEL, timeout_seconds=TIMEOUT)
    preflight=broker.preflight().__dict__
    rows=[]
    for rep in range(1,args.repeats+1):
        for arm in ARMS:
            print(f"RUN rep={rep} arm={arm}", flush=True)
            row=run_one(broker, arm, rep, raw_dir, work_dir)
            rows.append(row)
            ok=row["audit"]["valid_answer"] and row["audit"]["compile_ok"] and row["audit"]["trap_pass"]
            print(f"DONE rep={rep} arm={arm} pass={ok} fresh={row['freshness']['fresh']} failure={row['failure_classification']['primary']}", flush=True)
            out={"schema":"mutation_freshness_v6","model":MODEL,"preflight":preflight,"rows":rows,"summary":summarize(rows)}
            (results/f"{args.tag}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    out={"schema":"mutation_freshness_v6","model":MODEL,"preflight":preflight,"rows":rows,"summary":summarize(rows)}
    json_path=results/f"{args.tag}.json"; report_path=results/f"{args.tag.upper()}_REPORT.md"
    json_path.write_text(json.dumps(out, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    write_report(out, report_path)
    print("WROTE", json_path, report_path)
    print(json.dumps(out["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
