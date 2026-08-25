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
ARMS = ["SOURCE_ONLY", "STALE_DOC_CONTROL", "TMF_STALE_GATED"]
TAG = "mutation_freshness_m07"
FILE = "HookFixture.java"

PRE = r'''final class HookFixture {
  private static int phase = 0;
  private static int hookCount = 0;

  static void reset() {
    phase = 0;
    hookCount = 0;
  }

  static void hook() {
    hookCount++;
    if (phase != 1) {
      throw new AssertionError("hook must run after argument prep and immediately before methodInvoke");
    }
  }

  static void invokeSubscriberMethod(Object event) {
    phase = 1;
    methodInvoke(event);
    phase = 2;
  }

  static void methodInvoke(Object event) {
    if (phase != 1) {
      throw new AssertionError("methodInvoke requires prepared phase");
    }
  }
}
'''

POST = r'''final class HookFixture {
  private static int phase = 0;
  private static int hookCount = 0;

  static void reset() {
    phase = 0;
    hookCount = 0;
  }

  static void hook() {
    hookCount++;
    if (phase != 1) {
      throw new AssertionError("hook must run after argument prep and immediately before methodInvoke");
    }
  }

  static void invokeSubscriberMethod(Object event) {
    invokeReflectively(event);
  }

  static void invokeReflectively(Object event) {
    phase = 1;
    // CURRENT INVARIANT: the hook call belongs below this line and immediately before methodInvoke(event).
    methodInvoke(event);
    phase = 2;
  }

  static void methodInvoke(Object event) {
    if (phase != 1) {
      throw new AssertionError("methodInvoke requires prepared phase");
    }
  }
}
'''


def make_repo(dest: Path) -> dict[str, Any]:
    dest.mkdir(parents=True, exist_ok=True)
    (dest / ".tmf").mkdir()
    (dest / FILE).write_text(POST, encoding="utf-8")
    return {"mutation": "move methodInvoke/event prep from invokeSubscriberMethod into invokeReflectively while leaving old wrapper anchor", "file": FILE}


def pre_claim() -> Claim:
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / FILE
        p.write_text(PRE, encoding="utf-8")
        source = PRE
        method = next(m for m in extract_java_methods(FILE, source) if m.qualname == "HookFixture.invokeSubscriberMethod")
        blob = subprocess.check_output(["git", "hash-object", str(p)], text=True).strip()
    return Claim(
        id="mutation_freshness_m07:old:HookFixture.invokeSubscriberMethod",
        claim=(
            "Verified old boundary: HookFixture.invokeSubscriberMethod prepares phase and directly calls "
            "methodInvoke(event); insert the hook in HookFixture.invokeSubscriberMethod immediately before methodInvoke(event)."
        ),
        kind="structure",
        scope="class",
        bindings=[Binding(
            path=FILE,
            file_blob=blob,
            fn_hash=method.class_hash,
            commit=None,
            qualname="HookFixture.invokeSubscriberMethod",
            role="method",
            line_start=method.line_start,
            line_end=method.line_end,
            hash_kind="java_node_hash",
        )],
        provenance="synthetic M07 pre-mutation claim",
        evidence="verified",
        confidence=0.96,
        endorsed_by=None,
        last_verified=now_utc(),
        model="deterministic-bench",
        body={"language":"java","node_kind":"method","qualname":"HookFixture.invokeSubscriberMethod","task_id":"M07","mutation_expected_stale":True},
    )


def compile_check(root: Path) -> dict[str, Any]:
    out_dir = Path(tempfile.mkdtemp(prefix="m07-javac-"))
    try:
        r = subprocess.run(["javac", "-nowarn", "-d", str(out_dir), str(root / FILE)], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)
        return {"ok": r.returncode == 0, "exit": r.returncode, "stderr": r.stderr[-4000:], "stdout": r.stdout[-1000:]}
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def snapshot(root: Path) -> dict[str, str]:
    return {FILE: (root / FILE).read_text(encoding="utf-8", errors="replace")}


def diff_files(before: dict[str, str], root: Path) -> dict[str, str]:
    new = (root / FILE).read_text(encoding="utf-8", errors="replace")
    old = before[FILE]
    if old == new:
        return {}
    return {FILE: "\n".join(difflib.unified_diff(old.splitlines(), new.splitlines(), fromfile=f"a/{FILE}", tofile=f"b/{FILE}", lineterm=""))}


def safe(root: Path, rel: str) -> Path | None:
    return base_runner.safe(root, rel)


def read_numbered(p: Path, start: int=1, end: int|None=None) -> str:
    return base_runner.read_numbered(p, start, end)


def find_symbol_range(p: Path, symbol: str) -> tuple[int,int] | None:
    return base_runner.find_symbol_range(p, symbol)


def parse_actions(raw: str) -> list[dict[str, Any]]:
    return base_runner.parse_actions(raw)


def apply_edit(root: Path, act: dict[str, Any]) -> dict[str, Any]:
    return base_runner.apply_edit(root, act)


def source_placement_check(root: Path) -> dict[str, Any]:
    text = (root / FILE).read_text(encoding="utf-8", errors="replace")
    correct = bool(re.search(r"(?s)invokeReflectively\(Object event\).*?phase\s*=\s*1;\s*(?://[^\n]*\n\s*)?hook\(\);\s*methodInvoke\(event\);", text))
    wrong_wrapper = bool(re.search(r"(?s)invokeSubscriberMethod\(Object event\)\s*\{\s*hook\(\);\s*invokeReflectively\(event\);", text))
    hook_defs = len(re.findall(r"(?:static\s+)?void\s+hook\s*\(", text))
    hook_calls = len(re.findall(r"(?<!void\s)hook\s*\(\s*\)\s*;", text))
    return {"correct_helper_site": correct, "wrong_wrapper_site": wrong_wrapper, "hook_defs": hook_defs, "hook_calls": hook_calls}


def deterministic_test(root: Path) -> dict[str, Any]:
    comp = compile_check(root)
    place = source_placement_check(root)
    ok = bool(comp.get("ok") and place["correct_helper_site"] and not place["wrong_wrapper_site"] and place["hook_defs"] == 1 and place["hook_calls"] == 1)
    reasons = []
    if not comp.get("ok"): reasons.append("compile failed")
    if not place["correct_helper_site"]: reasons.append("missing hook inside invokeReflectively immediately before methodInvoke(event)")
    if place["wrong_wrapper_site"]: reasons.append("hook is at stale wrapper site before invokeReflectively(event)")
    if place["hook_defs"] != 1: reasons.append(f"expected existing single hook definition, found {place['hook_defs']}")
    if place["hook_calls"] != 1: reasons.append(f"expected exactly one hook() call, found {place['hook_calls']}")
    return {"ok": ok, "placement": place, "compile": comp, "message": "PASS" if ok else "; ".join(reasons)}


def audit(diffs: dict[str,str], comp: dict[str,Any], final: dict[str,Any] | None) -> dict[str, Any]:
    diff = diffs.get(FILE, "")
    current = "" if not diff else diff
    correct = bool(re.search(r"(?s)invokeReflectively\(Object event\).*?phase\s*=\s*1;.*?\+\s*hook\(\);\n\+?\s*methodInvoke\(event\);", current))
    wrong_wrapper = bool(re.search(r"(?s)invokeSubscriberMethod\(Object event\).*?\+\s*hook\(\);\n\+?\s*invokeReflectively\(event\);", current))
    hook_defs_added = len(re.findall(r"\+\s*(?:static\s+)?void\s+hook\s*\(", diff))
    hook_calls_added = len(re.findall(r"\+\s*hook\s*\(\s*\)\s*;", diff))
    # Existing hook definition is already present; the task is to add exactly one call, not define hook.
    valid = final is not None and comp.get("ok") is True
    trap = valid and correct and not wrong_wrapper and hook_defs_added == 0 and hook_calls_added == 1
    return {"valid_answer": valid, "compile_ok": bool(comp.get("ok")), "trap_pass": trap, "trap_reason": {"correct_helper_site": correct, "wrong_wrapper_site": wrong_wrapper, "hook_defs_added": hook_defs_added, "hook_calls_added": hook_calls_added}}


def metric_view(raw: dict[str, Any]) -> dict[str, Any]:
    cats = set(raw.get("failure_classification", {}).get("categories", []))
    aud = raw["audit"]
    raw_pass = bool(aud["valid_answer"] and aud["compile_ok"] and aud["trap_pass"])
    protocol_clean = not bool(cats & {"no_effect_false_completion", "compile_fail", "parse_or_invalid"}) and aud["valid_answer"] and aud["compile_ok"] and bool(raw.get("diffs"))
    semantic_evaluable = protocol_clean
    return {"raw_pass": raw_pass, "protocol_clean": protocol_clean, "semantic_evaluable": semantic_evaluable, "semantic_pass": bool(aud["trap_pass"]) if semantic_evaluable else None}


def agent_loop(broker: JsonBrokerAdapter, arm: str, root: Path, claim: Claim, freshness: Any, final_gate: str):
    if arm == "TMF_STALE_GATED":
        if freshness.fresh:
            injection = "\nFresh TMF claim injected below:\n" + json.dumps(claim.to_dict(), ensure_ascii=False, indent=2)
        else:
            injection = "\nTMF stale gate: a matching old claim was WITHHELD because freshness failed: " + json.dumps(freshness.stale_bindings, ensure_ascii=False) + ". Do not rely on old wrapper-boundary notes; use current source invariants.\n"
    elif arm == "STALE_DOC_CONTROL":
        injection = "\nPlain project handbook note (no freshness binding):\n- REQUIRED PATCH SITE: HookFixture.invokeSubscriberMethod still calls invokeReflectively(event); insert hook() immediately before invokeReflectively(event).\n- The wrapper entry is the approved subscriber reflective invocation boundary; do not move the hook into invokeReflectively.\n"
    else:
        injection = ""
    task = (
        "Add exactly one call to the existing hook() for the subscriber reflective invocation boundary in HookFixture.java. "
        "Read HookFixture.invokeSubscriberMethod and HookFixture.invokeReflectively before editing. "
        "Follow current in-source invariant comments and keep the patch minimal and compiling."
    )
    test_tool = '\n{"action":"test"}' if final_gate in {"advisory", "hard"} else ""
    tools = f"""Available actions (respond with JSON objects):
{{"action":"read_range","path":"HookFixture.java","start":1,"end":80}}
{{"action":"read_symbol","path":"HookFixture.java","symbol":"invokeSubscriberMethod"}}
{{"action":"read_symbol","path":"HookFixture.java","symbol":"invokeReflectively"}}
{{"action":"search","query":"CURRENT INVARIANT"}}
{{"action":"search","query":"methodInvoke"}}
{{"action":"edit","path":"HookFixture.java","old":"exact old text","new":"replacement text"}}
{{"action":"compile"}}{test_tool}
{{"action":"final","answer":"what changed","files":["HookFixture.java"]}}
"""
    doc_line = "If a project handbook note gives a REQUIRED PATCH SITE and that anchor exists, prefer that site unless current source has an explicit invariant that contradicts it."
    gate_line = "If the TMF stale gate withheld a claim, treat old notes as unsafe and prefer current in-source invariants."
    normal_line = "Prefer current in-source invariants over assumptions."
    guidance = gate_line if arm == "TMF_STALE_GATED" else (doc_line if arm == "STALE_DOC_CONTROL" else normal_line)
    if final_gate == "hard":
        final_policy = 'Edit only files under fixture root. You must perform at least one successful edit before final; never final if no edit action returned ok=true. Run {{"action":"test"}} before final; if test fails, fix the placement and rerun test. If an edit fails, read current source and retry with an exact anchor. Compile before final.'
    elif final_gate == "advisory":
        final_policy = 'Edit only files under fixture root. You must perform at least one successful edit before final; never final if no edit action returned ok=true. Run {{"action":"test"}} before final; if test fails, fix the placement and rerun test. If an edit fails, read current source and retry with an exact anchor. Compile before final.'
    elif final_gate == "off":
        final_policy = 'Edit only files under fixture root. You must perform at least one successful edit before final; never final if no edit action returned ok=true. If an edit fails, read current source and retry with an exact anchor. Compile before final.'
    else:
        raise ValueError(f"unknown final_gate: {final_gate}")
    system = f"""You are a stateless Java coding agent in mutation_freshness_m07.
Arm: {arm}
Fixture root: {root}
Task: {task}
{guidance}
Final gate mode: {final_gate}
{final_policy}
{tools}
{injection}
Begin now."""
    hist=[]; transcript=[]; met={"tool_calls":0,"source_bytes":0,"source_reads":0,"source_files":[],"prompt_tokens":0,"completion_tokens":0,"invalid":0,"wall_seconds":0.0,"successful_edits":0,"passed_tests":0,"rejected_finals":0}
    final=None; latest_test_ok=False; start=time.time()
    for turn in range(MAX_TURNS):
        prompt=system+"\n"+("\n".join(hist[-18:]) if hist else "")
        met["prompt_tokens"] += base_runner.tok(prompt)
        try:
            raw=broker.answer(prompt, budget=1)["answer"]
        except Exception as e:
            transcript.append({"turn":turn,"broker_error":str(e)}); break
        met["completion_tokens"] += base_runner.tok(raw)
        acts=parse_actions(raw)
        transcript.append({"turn":turn,"raw":raw,"actions":acts})
        if not acts:
            met["invalid"] += 1; hist += ["AGENT:"+raw, "SYSTEM: respond with one JSON action."]; continue
        outs=[]; stop=False
        for act in acts:
            met["tool_calls"] += 1; a=act.get("action")
            if a == "search":
                q=str(act.get("query","")).lower(); hits=[]
                for i,line in enumerate((root/FILE).read_text().splitlines(),1):
                    if q and q in line.lower(): hits.append(f"{FILE}:{i}:{line}")
                out={"hits":hits}
            elif a == "read_range":
                p=safe(root, str(act.get("path","")))
                if not p: out={"error":"invalid path"}
                else:
                    st=max(1,int(act.get("start",1))); en=int(act.get("end",st+80)); content=read_numbered(p,st,en)
                    met["source_bytes"] += len(content.encode()); met["source_reads"] += 1; met["source_files"].append(p.name); out={"path":p.name,"content":content}
            elif a == "read_symbol":
                p=safe(root, str(act.get("path",""))); sym=str(act.get("symbol",""))
                if not p: out={"error":"invalid path"}
                else:
                    rng=find_symbol_range(p,sym)
                    if not rng: out={"error":"symbol not found"}
                    else:
                        content=read_numbered(p,rng[0],rng[1]); met["source_bytes"] += len(content.encode()); met["source_reads"] += 1; met["source_files"].append(p.name); out={"path":p.name,"symbol":sym,"content":content}
            elif a == "edit":
                out=apply_edit(root, act)
                if out.get("ok") is True:
                    met["successful_edits"] += 1
                    latest_test_ok = False
            elif a == "compile": out=compile_check(root)
            elif a == "test":
                out=deterministic_test(root)
                latest_test_ok = bool(out.get("ok"))
                if latest_test_ok:
                    met["passed_tests"] += 1
            elif a == "final":
                if final_gate == "hard" and met["successful_edits"] < 1:
                    out={"error":"final rejected: no successful edit has occurred; edit HookFixture.java first"}
                    met["rejected_finals"] += 1
                elif final_gate == "hard" and not latest_test_ok:
                    out={"error":"final rejected: deterministic test has not passed after the latest edit; run test, fix any placement errors, rerun test"}
                    met["rejected_finals"] += 1
                else:
                    final=act; stop=True; break
            else: out={"error":"unknown action"}
            outs.append({"action":act,"tool_output":out})
        transcript[-1]["tool_outputs"] = outs
        if outs: hist += ["AGENT:"+raw, "TOOL:"+json.dumps(outs, ensure_ascii=False)[:12000]]
        if stop: break
    met["wall_seconds"] = round(time.time()-start,3); met["source_files"] = sorted(set(met["source_files"]))
    return final, met, transcript


def run_one(broker: JsonBrokerAdapter, arm: str, rep: int, raw_dir: Path, work_dir: Path, final_gate: str) -> dict[str, Any]:
    root = work_dir / f"M07__{arm}__r{rep}"
    make_repo(root)
    claim = pre_claim()
    fresh = check_freshness(GitRepo(root), claim)
    before = snapshot(root)
    final, met, transcript = agent_loop(broker, arm, root, claim, fresh, final_gate)
    comp = compile_check(root)
    diffs = diff_files(before, root)
    aud = audit(diffs, comp, final)
    raw={"task_id":"M07","arm":arm,"rep":rep,"final_gate":final_gate,"freshness":{"fresh":fresh.fresh,"stale_bindings":fresh.stale_bindings},"final":final,"telemetry":met,"compile":comp,"diffs":diffs,"audit":aud,"transcript":transcript}
    raw["failure_classification"] = base_runner.classify_run_failure(raw)
    raw["metrics"] = metric_view(raw)
    raw_path=raw_dir/f"M07__{arm}__r{rep}.raw.json"
    raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return {k:raw[k] for k in ["task_id","arm","rep","final_gate","freshness","final","telemetry","compile","audit","failure_classification","metrics"]} | {"raw_path":str(raw_path.relative_to(HERE)),"diff_bytes":sum(len(d.encode()) for d in diffs.values())}


def summarize(rows):
    by={}
    for arm in ARMS:
        rs=[r for r in rows if r["arm"]==arm]
        by[arm]={"runs":len(rs),"raw_pass":sum(r["metrics"]["raw_pass"] for r in rs),"semantic_evaluable":sum(r["metrics"]["semantic_evaluable"] for r in rs),"semantic_adjusted_pass":sum(1 for r in rs if r["metrics"]["semantic_pass"] is True),"compile_ok":sum(r["audit"]["compile_ok"] for r in rs),"stale_claim_withheld":sum(1 for r in rs if arm=="TMF_STALE_GATED" and r["freshness"]["fresh"] is False),"wrong_wrapper_site":sum(1 for r in rs if r["audit"]["trap_reason"].get("wrong_wrapper_site")),"primary":{}}
        for r in rs:
            p=r["failure_classification"].get("primary","unknown"); by[arm]["primary"][p]=by[arm]["primary"].get(p,0)+1
    return {"mode":TAG,"runs":len(rows),"final_gate": rows[0].get("final_gate") if rows else None,"by_arm":by}


def write_report(out, path: Path):
    lines=["# Mutation Freshness M07 Report","","Deterministic synthetic fixture: old claim binds to pre-mutation wrapper; mutation moves prepared reflective boundary into helper while stale wrapper anchor remains compilable.","","```json",json.dumps(out["summary"],ensure_ascii=False,indent=2),"```","","## Rows"]
    for r in out["rows"]:
        lines.append(f"- rep {r['rep']} {r['arm']}: raw={r['metrics']['raw_pass']} semantic={r['metrics']['semantic_pass']} compile={r['audit']['compile_ok']} fresh={r['freshness']['fresh']} failure={r['failure_classification']['primary']} reason={json.dumps(r['audit']['trap_reason'], ensure_ascii=False)} raw_path={r['raw_path']}")
    path.write_text("\n".join(lines)+"\n", encoding="utf-8")


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--repeats",type=int,default=5); ap.add_argument("--tag",default=TAG); ap.add_argument("--final-gate", choices=["off", "advisory", "hard"], default="hard", help="off=M07b-style no test/hard rejection; advisory=show test action but accept final; hard=reject final unless latest test passed"); args=ap.parse_args()
    results=HERE/"results"; raw_dir=results/"raw"/args.tag; work_dir=results/"work"/args.tag
    if raw_dir.exists(): shutil.rmtree(raw_dir)
    if work_dir.exists(): shutil.rmtree(work_dir)
    raw_dir.mkdir(parents=True); work_dir.mkdir(parents=True)
    broker=JsonBrokerAdapter(BROKER, expected_model=MODEL, timeout_seconds=TIMEOUT); preflight=broker.preflight().__dict__
    rows=[]
    for rep in range(1,args.repeats+1):
        for arm in ARMS:
            print(f"RUN rep={rep} arm={arm}", flush=True)
            row=run_one(broker,arm,rep,raw_dir,work_dir,args.final_gate); rows.append(row)
            print(f"DONE rep={rep} arm={arm} pass={row['metrics']['raw_pass']} fresh={row['freshness']['fresh']} failure={row['failure_classification']['primary']}", flush=True)
            out={"schema":TAG,"model":MODEL,"final_gate":args.final_gate,"preflight":preflight,"rows":rows,"summary":summarize(rows)}
            (results/f"{args.tag}.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n", encoding="utf-8")
    out={"schema":TAG,"model":MODEL,"final_gate":args.final_gate,"preflight":preflight,"rows":rows,"summary":summarize(rows)}
    jp=results/f"{args.tag}.json"; rp=results/f"{args.tag.upper()}_REPORT.md"
    jp.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n", encoding="utf-8"); write_report(out,rp)
    print("WROTE", jp, rp); print(json.dumps(out["summary"], ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
