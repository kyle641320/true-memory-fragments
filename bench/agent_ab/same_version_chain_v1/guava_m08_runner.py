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
GUAVA = ROOT / "bench" / "agent_ab" / "guava_cognitive_v1"
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
TAG = "guava_m08_feature_stale"
ARMS = ["SOURCE_ONLY", "STALE_DOC_CONTROL", "TMF_STALE_GATED"]
PKG_FILES = base_runner.PKG_FILES
FILE = "Subscriber.java"

OLD_SNIPPET = """  void invokeSubscriberMethod(Object event) throws InvocationTargetException {
    try {
      method.invoke(target, checkNotNull(event));
    } catch (IllegalArgumentException e) {"""

NEW_SNIPPET = """  void invokeSubscriberMethod(Object event) throws InvocationTargetException {
    try {
      invokeMethodReflectively(event);
    } catch (IllegalArgumentException e) {"""

HELPER_INSERT_AFTER = """  }

  /** Gets the context for the given event. */"""

HELPER_BLOCK = """  }

  private void invokeMethodReflectively(Object event) throws InvocationTargetException, IllegalAccessException {
    Object checkedEvent = checkNotNull(event);
    method.invoke(target, checkedEvent);
  }

  /** Gets the context for the given event. */"""


def source_base() -> Path:
    return GUAVA / "fixtures" / "B03" / "base"


def mutate_subscriber(text: str) -> str:
    if text.count(OLD_SNIPPET) != 1:
        raise RuntimeError("old reflective invocation snippet not unique")
    text = text.replace(OLD_SNIPPET, NEW_SNIPPET)
    if text.count(HELPER_INSERT_AFTER) != 1:
        raise RuntimeError("helper insertion anchor not unique")
    return text.replace(HELPER_INSERT_AFTER, HELPER_BLOCK)


def make_repo(dest: Path) -> dict[str, Any]:
    src = source_base()
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for f in PKG_FILES:
        shutil.copy2(src / f, dest / f)
    (dest / FILE).write_text(mutate_subscriber((src / FILE).read_text(encoding="utf-8")), encoding="utf-8")
    (dest / ".tmf").mkdir()
    return {"fixture": "guava EventBus bounded package", "mutation": "move reflective call from Subscriber.invokeSubscriberMethod into helper invokeMethodReflectively while wrapper remains compilable"}


def pre_claim() -> Claim:
    src = source_base() / FILE
    text = src.read_text(encoding="utf-8")
    method = next(m for m in extract_java_methods(FILE, text) if m.qualname.endswith("Subscriber.invokeSubscriberMethod"))
    blob = subprocess.check_output(["git", "hash-object", str(src)], text=True).strip()
    return Claim(
        id="guava_m08:old:Subscriber.invokeSubscriberMethod",
        claim=(
            "Verified old reflective boundary: Subscriber.invokeSubscriberMethod directly calls "
            "method.invoke(target, checkNotNull(event)); insert pre-invocation instrumentation in "
            "Subscriber.invokeSubscriberMethod immediately before method.invoke."
        ),
        kind="structure",
        scope="class",
        bindings=[Binding(
            path=FILE,
            file_blob=blob,
            fn_hash=method.class_hash,
            commit=None,
            qualname="Subscriber.invokeSubscriberMethod",
            role="method",
            line_start=method.line_start,
            line_end=method.line_end,
            hash_kind="java_node_hash",
        )],
        provenance="synthetic stale claim from pre-mutation Guava Subscriber.java",
        evidence="verified",
        confidence=0.96,
        endorsed_by=None,
        last_verified=now_utc(),
        model="deterministic-bench",
        body={"language":"java","node_kind":"method","qualname":"Subscriber.invokeSubscriberMethod","task_id":"GUAVA_M08","mutation_expected_stale":True},
    )


def compile_check(root: Path) -> dict[str, Any]:
    cp = GUAVA / "classpath.txt"
    out_dir = Path(tempfile.mkdtemp(prefix="guava-m08-javac-"))
    try:
        cmd = f'javac -nowarn -cp "$(cat {cp})" -d {out_dir} ' + " ".join(str(root / f) for f in PKG_FILES)
        r = subprocess.run(["bash", "-lc", cmd], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90)
        return {"ok": r.returncode == 0, "exit": r.returncode, "stderr": r.stderr[-4000:], "stdout": r.stdout[-1000:]}
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)


def snapshot(root: Path) -> dict[str, str]:
    return {f: (root / f).read_text(encoding="utf-8", errors="replace") for f in PKG_FILES if (root / f).exists()}


def diff_files(before: dict[str, str], root: Path) -> dict[str, str]:
    out = {}
    for f, old in before.items():
        p = root / f
        new = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
        if new != old:
            out[f] = "\n".join(difflib.unified_diff(old.splitlines(), new.splitlines(), fromfile=f"a/{f}", tofile=f"b/{f}", lineterm=""))
    return out


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
    helper_block = re.search(r"(?s)private void invokeMethodReflectively\(Object event\).*?\n  \}", text)
    helper = helper_block.group(0) if helper_block else ""
    wrapper_block = re.search(r"(?s)void invokeSubscriberMethod\(Object event\).*?catch \(InvocationTargetException e\)", text)
    wrapper = wrapper_block.group(0) if wrapper_block else ""
    correct = bool(re.search(r"Object checkedEvent = checkNotNull\(event\);\s*hook\(\);\s*method\.invoke\(target, checkedEvent\);", helper))
    wrong_wrapper = "hook();" in wrapper
    hook_defs = len(re.findall(r"(?:static\s+)?void\s+hook\s*\(", text))
    hook_calls = len(re.findall(r"(?<!void\s)hook\s*\(\s*\)\s*;", text))
    return {"correct_helper_site": correct, "wrong_wrapper_site": wrong_wrapper, "hook_defs": hook_defs, "hook_calls": hook_calls}


def deterministic_test(root: Path) -> dict[str, Any]:
    comp = compile_check(root)
    place = source_placement_check(root)
    ok = bool(comp.get("ok") and place["correct_helper_site"] and not place["wrong_wrapper_site"] and place["hook_defs"] == 1 and place["hook_calls"] == 1)
    reasons = []
    if not comp.get("ok"): reasons.append("compile failed")
    if not place["correct_helper_site"]: reasons.append("missing hook after checkNotNull(event) and immediately before method.invoke(target, checkedEvent) inside invokeMethodReflectively")
    if place["wrong_wrapper_site"]: reasons.append("hook is at stale wrapper site in invokeSubscriberMethod")
    if place["hook_defs"] != 1: reasons.append(f"expected one hook definition, found {place['hook_defs']}")
    if place["hook_calls"] != 1: reasons.append(f"expected one hook() call, found {place['hook_calls']}")
    return {"ok": ok, "placement": place, "compile": comp, "message": "PASS" if ok else "; ".join(reasons)}


def audit(diffs: dict[str,str], comp: dict[str,Any], final: dict[str,Any] | None, root: Path) -> dict[str, Any]:
    place = source_placement_check(root)
    diff = "\n".join(diffs.values())
    hook_defs_added = len(re.findall(r"\+\s*(?:static\s+)?void\s+hook\s*\(", diff))
    hook_calls_added = len(re.findall(r"\+\s*hook\s*\(\s*\)\s*;", diff))
    valid = final is not None and bool(diffs) and comp.get("ok") is True
    trap = valid and place["correct_helper_site"] and not place["wrong_wrapper_site"] and place["hook_defs"] == 1 and place["hook_calls"] == 1
    return {"valid_answer": valid, "compile_ok": bool(comp.get("ok")), "trap_pass": trap, "trap_reason": {**place, "hook_defs_added": hook_defs_added, "hook_calls_added": hook_calls_added}}


def metric_view(raw: dict[str, Any]) -> dict[str, Any]:
    cats = set(raw.get("failure_classification", {}).get("categories", []))
    aud = raw["audit"]
    post = raw.get("post_test") or {}
    raw_pass = bool(aud["valid_answer"] and aud["compile_ok"] and aud["trap_pass"])
    protocol_clean = not bool(cats & {"no_effect_false_completion", "compile_fail", "parse_or_invalid_action_noise"}) and aud["valid_answer"] and aud["compile_ok"] and bool(raw.get("diffs"))
    semantic_evaluable = protocol_clean
    task_result_pass = bool(post.get("ok") and raw.get("diffs"))
    return {"raw_pass": raw_pass, "protocol_clean": protocol_clean, "semantic_evaluable": semantic_evaluable, "semantic_pass": bool(aud["trap_pass"]) if semantic_evaluable else None, "task_result_pass": task_result_pass, "post_test_ok": bool(post.get("ok"))}


def classify_failure(raw: dict[str, Any]) -> dict[str, Any]:
    cls = base_runner.classify_run_failure(raw)
    categories = list(cls.get("categories", []))
    telemetry = raw.get("telemetry", {})
    post = raw.get("post_test") or {}
    if raw.get("final") is None and post.get("ok") and raw.get("diffs"):
        if "no_final_after_success" not in categories:
            categories.insert(0, "no_final_after_success")
        categories = [c for c in categories if c != "no_final"]
    if telemetry.get("duplicate_edit_suppressed", 0):
        categories.append("duplicate_edit_suppressed")
    passed = bool(cls.get("pass"))
    primary = "pass" if passed else (categories[0] if categories else cls.get("primary", "uncategorized_fail"))
    out = dict(cls)
    out["primary"] = primary
    out["categories"] = categories
    out["duplicate_edit_suppressed"] = int(telemetry.get("duplicate_edit_suppressed", 0))
    out["result_ok_but_raw_failed"] = bool((not passed) and post.get("ok") and raw.get("diffs"))
    return out


def agent_loop(broker: JsonBrokerAdapter, arm: str, root: Path, claim: Claim, freshness: Any, final_gate: str, max_turns: int):
    if arm == "TMF_STALE_GATED":
        if freshness.fresh:
            injection = "\nFresh TMF claim injected below:\n" + json.dumps(claim.to_dict(), ensure_ascii=False, indent=2)
        else:
            injection = "\nTMF stale gate: an old claim about Subscriber.invokeSubscriberMethod was WITHHELD because freshness failed: " + json.dumps(freshness.stale_bindings, ensure_ascii=False) + ". Do not rely on old reflective-boundary notes; infer the correct boundary from current Guava source behavior.\n"
    elif arm == "STALE_DOC_CONTROL":
        injection = "\nPlain project handbook note (no freshness binding):\n- REQUIRED PATCH SITE: Subscriber.invokeSubscriberMethod is the approved reflective invocation boundary; insert hook() inside Subscriber.invokeSubscriberMethod immediately before the invocation helper/call. Do not move the hook into lower-level helper methods.\n"
    else:
        injection = ""
    task = (
        "Add instrumentation so hook() runs exactly once immediately before the actual subscriber method reflective invocation, "
        "after the invocation argument has been validated/prepared, and not during executor scheduling, wrapper dispatch, or exception handling. "
        "Infer the correct boundary from the current Guava source. Keep the patch minimal and compiling."
    )
    tools = """Available actions (respond with JSON objects):
{"action":"list"}
{"action":"read_range","path":"Subscriber.java","start":1,"end":180}
{"action":"read_symbol","path":"Subscriber.java","symbol":"symbol name from the current source"}
{"action":"search","query":"text to search for"}
{"action":"edit","path":"Subscriber.java","old":"the exact line block copied verbatim from the latest read output","new":"replacement text"}
{"action":"compile"}
{"action":"final","answer":"what changed","files":["Subscriber.java"]}
"""
    doc_line = "If a project handbook note gives a REQUIRED PATCH SITE and that anchor exists, prefer that site unless current source behavior contradicts it."
    gate_line = "If the TMF stale gate withheld a claim, treat old notes as unsafe and infer the correct boundary from current source behavior."
    normal_line = "Infer the correct boundary from current source behavior rather than assumptions."
    guidance = gate_line if arm == "TMF_STALE_GATED" else (doc_line if arm == "STALE_DOC_CONTROL" else normal_line)
    system = f"""You are a stateless Java coding agent in guava_m08_feature_stale.
Arm: {arm}
Fixture root: {root}
Task: {task}
{guidance}
When editing, copy exact old text from the latest read output. If an edit fails, re-read the relevant current source and retry with the exact current source text.
Final gate mode: {final_gate}
Edit only files under fixture root. You must perform at least one successful edit before final; never final if no edit action returned ok=true. Compile before final. This is a pure A/B run: no in-loop acceptance feedback is available to the agent.
{tools}
{injection}
Begin now."""
    hist=[]; transcript=[]; met={"tool_calls":0,"source_bytes":0,"source_reads":0,"source_files":[],"prompt_tokens":0,"completion_tokens":0,"invalid":0,"wall_seconds":0.0,"successful_edits":0,"rejected_finals":0,"duplicate_edit_suppressed":0}
    final=None; start=time.time()
    for turn in range(max_turns):
        prompt=system+"\n"+("\n".join(hist[-18:]) if hist else "")
        met["prompt_tokens"] += base_runner.tok(prompt)
        try:
            raw=broker.answer(prompt, budget=1)["answer"]
        except Exception as e:
            if "preflight is required" in str(e):
                try:
                    broker.preflight(); raw=broker.answer(prompt, budget=1)["answer"]
                except Exception as e2:
                    transcript.append({"turn":turn,"broker_error":str(e2)}); break
            else:
                transcript.append({"turn":turn,"broker_error":str(e)}); break
        met["completion_tokens"] += base_runner.tok(raw)
        acts=parse_actions(raw)
        transcript.append({"turn":turn,"raw":raw,"actions":acts})
        if len(acts) == 1 and acts[0].get("action") is None and any(k in acts[0] for k in ("files", "answer", "message")):
            acts = [{"action":"final", **acts[0]}]
        if not acts:
            met["invalid"] += 1
            hist += ["AGENT:"+raw, "SYSTEM: respond with one JSON action."]
            continue
        outs=[]; stop=False; edit_seen=False
        for act in acts:
            met["tool_calls"] += 1; a=act.get("action")
            if a == "list":
                out={"files": sorted(p.name for p in root.glob("*.java"))}
            elif a == "search":
                q=str(act.get("query","")).lower(); hits=[]
                for p in sorted(root.glob("*.java")):
                    for i,line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(),1):
                        if q and q in line.lower(): hits.append(f"{p.name}:{i}:{line}")
                out={"hits":hits[:120]}
            elif a == "read_range":
                p=safe(root, str(act.get("path","")))
                if not p: out={"error":"invalid path"}
                else:
                    st=max(1,int(act.get("start",1))); en=int(act.get("end",st+120)); content=read_numbered(p,st,en)
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
                if edit_seen:
                    met["duplicate_edit_suppressed"] += 1; out={"error":"duplicate edit ignored; only one edit is allowed per turn"}; outs.append({"action":act,"tool_output":out}); continue
                out=apply_edit(root, act)
                if out.get("ok") is True:
                    met["successful_edits"] += 1; edit_seen=True
            elif a == "compile":
                out=compile_check(root)
            elif a == "final":
                if final_gate == "hard" and met["successful_edits"] < 1:
                    out={"error":"final rejected: no successful edit has occurred"}; met["rejected_finals"] += 1
                else:
                    final=act; stop=True; break
            else:
                out={"error":"unknown action"}
            outs.append({"action":act,"tool_output":out})
        transcript[-1]["tool_outputs"] = outs
        if outs: hist += ["AGENT:"+raw, "TOOL:"+json.dumps(outs, ensure_ascii=False)[:12000]]
        if stop: break
    met["wall_seconds"] = round(time.time()-start,3); met["source_files"] = sorted(set(met["source_files"]))
    return final, met, transcript


def run_one(broker: JsonBrokerAdapter, arm: str, rep: int, raw_dir: Path, work_dir: Path, final_gate: str, max_turns: int) -> dict[str, Any]:
    root = work_dir / f"GUAVA_M08__{arm}__r{rep}"
    make_repo(root)
    claim = pre_claim()
    fresh = check_freshness(GitRepo(root), claim)
    before = snapshot(root)
    final, met, transcript = agent_loop(broker, arm, root, claim, fresh, final_gate, max_turns)
    comp = compile_check(root)
    post_test = deterministic_test(root)
    diffs = diff_files(before, root)
    aud = audit(diffs, comp, final, root)
    raw={"task_id":"GUAVA_M08","arm":arm,"rep":rep,"final_gate":final_gate,"max_turns":max_turns,"freshness":{"fresh":fresh.fresh,"stale_bindings":fresh.stale_bindings},"final":final,"telemetry":met,"compile":comp,"post_test":post_test,"diffs":diffs,"audit":aud,"transcript":transcript}
    raw["failure_classification"] = classify_failure(raw)
    raw["metrics"] = metric_view(raw)
    raw_path=raw_dir/f"GUAVA_M08__{arm}__r{rep}.raw.json"
    raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    return {k:raw[k] for k in ["task_id","arm","rep","final_gate","max_turns","freshness","final","telemetry","compile","post_test","audit","failure_classification","metrics"]} | {"raw_path":str(raw_path.relative_to(HERE)),"diff_bytes":sum(len(d.encode()) for d in diffs.values())}


def summarize(rows):
    by={}
    for arm in ARMS:
        rs=[r for r in rows if r["arm"]==arm]
        by[arm]={"runs":len(rs),"raw_pass":sum(r["metrics"]["raw_pass"] for r in rs),"task_result_pass":sum(r["metrics"].get("task_result_pass", False) for r in rs),"post_test_ok":sum(r["metrics"].get("post_test_ok", False) for r in rs),"semantic_evaluable":sum(r["metrics"]["semantic_evaluable"] for r in rs),"semantic_adjusted_pass":sum(1 for r in rs if r["metrics"]["semantic_pass"] is True),"compile_ok":sum(r["audit"]["compile_ok"] for r in rs),"stale_claim_withheld":sum(1 for r in rs if arm=="TMF_STALE_GATED" and r["freshness"]["fresh"] is False),"wrong_wrapper_site":sum(1 for r in rs if r.get("post_test",{}).get("placement",{}).get("wrong_wrapper_site")),"duplicate_edit_suppressed":sum(r.get("failure_classification",{}).get("duplicate_edit_suppressed",0) for r in rs),"result_ok_but_raw_failed":sum(1 for r in rs if r.get("failure_classification",{}).get("result_ok_but_raw_failed")),"primary":{}}
        for r in rs:
            p=r["failure_classification"].get("primary","unknown"); by[arm]["primary"][p]=by[arm]["primary"].get(p,0)+1
    return {"mode":TAG,"runs":len(rows),"final_gate": rows[0].get("final_gate") if rows else None,"max_turns": rows[0].get("max_turns") if rows else None,"by_arm":by}


def write_report(out, path: Path):
    lines=["# Guava M08 Feature Stale Report","","Bounded real-Guava EventBus fixture. Source mutation moves the reflective `method.invoke` from `Subscriber.invokeSubscriberMethod` into a helper `invokeMethodReflectively`, while the wrapper remains live and compilable. The task is feature intent only; the stale doc arm points at the old wrapper boundary; TMF stale-gated arm withholds the stale bound claim.","","```json",json.dumps(out["summary"],ensure_ascii=False,indent=2),"```","","## Rows"]
    for r in out["rows"]:
        lines.append(f"- rep {r['rep']} {r['arm']}: raw={r['metrics']['raw_pass']} task_result={r['metrics'].get('task_result_pass')} semantic={r['metrics']['semantic_pass']} compile={r['audit']['compile_ok']} fresh={r['freshness']['fresh']} failure={r['failure_classification']['primary']} reason={json.dumps(r['audit']['trap_reason'], ensure_ascii=False)} raw_path={r['raw_path']}")
    path.write_text("\n".join(lines)+"\n", encoding="utf-8")


def main():
    ap=argparse.ArgumentParser(); ap.add_argument("--repeats",type=int,default=3); ap.add_argument("--tag",default=TAG); ap.add_argument("--final-gate", choices=["hard"], default="hard"); ap.add_argument("--max-turns", type=int, default=8); args=ap.parse_args()
    results=HERE/"results"; raw_dir=results/"raw"/args.tag; work_dir=results/"work"/args.tag
    if raw_dir.exists(): shutil.rmtree(raw_dir)
    if work_dir.exists(): shutil.rmtree(work_dir)
    raw_dir.mkdir(parents=True); work_dir.mkdir(parents=True)
    broker=JsonBrokerAdapter(BROKER, expected_model=MODEL, timeout_seconds=TIMEOUT); preflight=broker.preflight().__dict__
    rows=[]
    for rep in range(1,args.repeats+1):
        for arm in ARMS:
            print(f"RUN rep={rep} arm={arm}", flush=True)
            row=run_one(broker,arm,rep,raw_dir,work_dir,args.final_gate,args.max_turns); rows.append(row)
            print(f"DONE rep={rep} arm={arm} raw={row['metrics']['raw_pass']} task={row['metrics']['task_result_pass']} failure={row['failure_classification']['primary']}", flush=True)
            out={"schema":TAG,"model":MODEL,"final_gate":args.final_gate,"max_turns":args.max_turns,"preflight":preflight,"rows":rows,"summary":summarize(rows)}
            (results/f"{args.tag}.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n", encoding="utf-8")
    out={"schema":TAG,"model":MODEL,"final_gate":args.final_gate,"max_turns":args.max_turns,"preflight":preflight,"rows":rows,"summary":summarize(rows)}
    jp=results/f"{args.tag}.json"; rp=results/f"{args.tag.upper()}_REPORT.md"
    jp.write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n", encoding="utf-8"); write_report(out,rp)
    print("WROTE", jp, rp); print(json.dumps(out["summary"], ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
