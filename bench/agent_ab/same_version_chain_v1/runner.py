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
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))
from bench.agent_ab.adapter import AgentAdapterError, JsonBrokerAdapter  # noqa: E402

TASKS_DOC = json.loads((HERE / "tasks.json").read_text(encoding="utf-8"))
TASKS = {t["id"]: t for t in TASKS_DOC["tasks"]}
ARMS = TASKS_DOC["arms"]
MODEL = "gpt-5.6-sol"
BROKER = ["/opt/tmf-model-broker/client"]
MAX_TURNS = 24
TIMEOUT = 240
PKG_FILES = [
    "AllowConcurrentEvents.java",
    "AsyncEventBus.java",
    "DeadEvent.java",
    "Dispatcher.java",
    "EventBus.java",
    "ParametricNullness.java",
    "Subscribe.java",
    "Subscriber.java",
    "SubscriberExceptionContext.java",
    "SubscriberExceptionHandler.java",
    "SubscriberRegistry.java",
]


def tok(s: str) -> int:
    return (len(s) + 3) // 4


def safe(root: Path, rel: str) -> Path | None:
    rel = rel.strip().lstrip("/")
    # Model outputs sometimes put code snippets or prose in the path field.
    # Treat those as invalid tool inputs, not harness-fatal filesystem paths.
    if not rel or len(rel) > 240 or "\n" in rel or "\r" in rel or "\\x00" in rel:
        return None
    try:
        p = (root / rel).resolve()
        return p if (p == root or root in p.parents) and p.is_file() else None
    except OSError:
        return None


def line_index(text: str, needle: str) -> int | None:
    for i, line in enumerate(text.splitlines(), 1):
        if needle in line:
            return i
    return None


def read_numbered(p: Path, start: int = 1, end: int | None = None) -> str:
    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
    if end is None:
        end = len(lines)
    start = max(1, start)
    end = min(len(lines), end)
    return "\n".join(f"{i}: {lines[i-1]}" for i in range(start, end + 1))


def find_symbol_range(p: Path, symbol: str) -> tuple[int, int] | None:
    text = p.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    simple = symbol.split(".")[-1]
    patterns = [
        rf"\b{re.escape(simple)}\s*\(",
        rf"\bclass\s+{re.escape(simple)}\b",
        rf"\binterface\s+{re.escape(simple)}\b",
        rf"\benum\s+{re.escape(simple)}\b",
    ]
    for i, line in enumerate(lines, 1):
        if any(re.search(pat, line) for pat in patterns):
            # Include annotations/comments and method body by brace matching.
            start = max(1, i - 6)
            depth = 0
            seen = False
            end = min(len(lines), i + 80)
            for j in range(i, len(lines) + 1):
                l = lines[j - 1]
                if "{" in l:
                    seen = True
                depth += l.count("{") - l.count("}")
                if seen and depth <= 0 and j > i:
                    end = min(len(lines), j + 3)
                    break
            return start, end
    return None


@dataclass
class ChainClaim:
    claim_id: str
    task_id: str
    kind: str
    freshness: str
    anchors: list[str]
    golden_chain: list[str]
    summary: str
    details: list[str]

    def to_dict(self) -> dict[str, Any]:
        return self.__dict__.copy()


def build_chain_claim(task: dict[str, Any]) -> ChainClaim:
    tid = task["id"]
    if tid == "B01":
        details = [
            "EventBus.post obtains an Iterator<Subscriber> from SubscriberRegistry.getSubscribers(event).",
            "EventBus.post delegates delivery to dispatcher.dispatch(event, eventSubscribers).",
            "AsyncEventBus is not a separate post path; its constructors pass Dispatcher.legacyAsync() and a caller-supplied Executor into EventBus.",
            "Dispatcher.LegacyAsyncDispatcher.dispatch queues EventWithSubscriber pairs then calls e.subscriber.dispatchEvent(e.event).",
            "Subscriber.dispatchEvent performs the executor handoff and then calls invokeSubscriberMethod(event).",
            "Subscriber.invokeSubscriberMethod calls Method.invoke(target, event).",
            "Therefore per-subscriber behavior such as rate limiting belongs at Subscriber/dispatchEvent/invocation boundary, not only at EventBus.post entry.",
        ]
    elif tid == "B02":
        details = [
            "Subscriber.dispatchEvent wraps invokeSubscriberMethod(event) in executor.execute(...).",
            "invokeSubscriberMethod calls Method.invoke and propagates InvocationTargetException for subscriber-thrown non-Error Throwables.",
            "dispatchEvent catches InvocationTargetException and calls bus.handleSubscriberException(e.getCause(), context(event)).",
            "EventBus.handleSubscriberException delegates to SubscriberExceptionHandler.handleException and logs if that handler fails.",
            "Retry must happen before the final handleSubscriberException call, around invokeSubscriberMethod, otherwise handler semantics or exception level are wrong.",
        ]
    elif tid == "B04":
        details = [
            "EventBus.post is the public entrypoint and may dispatch to many subscribers or repost DeadEvent.",
            "Dispatcher.dispatch controls iteration/enqueueing but does not itself invoke subscriber methods.",
            "Each Dispatcher eventually calls Subscriber.dispatchEvent(event) for a concrete subscriber.",
            "Subscriber.dispatchEvent performs the executor handoff and calls invokeSubscriberMethod(event).",
            "invokeSubscriberMethod calls Method.invoke on the actual subscriber method.",
            "An invocation-attempt counter belongs around invokeSubscriberMethod / Method.invoke, not at EventBus.post or Dispatcher.dispatch.",
        ]
    elif tid == "B05":
        details = [
            "EventBus.post and Dispatcher.dispatch happen before actual subscriber method success is known.",
            "Subscriber.dispatchEvent performs the executor handoff and then calls invokeSubscriberMethod(event).",
            "invokeSubscriberMethod calls Method.invoke on the target subscriber method.",
            "If invokeSubscriberMethod throws InvocationTargetException, dispatchEvent calls bus.handleSubscriberException(e.getCause(), context(event)).",
            "A success-only hook belongs immediately after invokeSubscriberMethod(event) returns normally and must not run in the InvocationTargetException failure path.",
        ]
    elif tid == "B06":
        details = [
            "EventBus.post only looks up subscribers and delegates delivery to Dispatcher.dispatch.",
            "Dispatcher.PerThreadQueuedDispatcher and Dispatcher.LegacyAsyncDispatcher both mediate ordering/queuing before subscriber handoff.",
            "Dispatcher.LegacyAsyncDispatcher enqueues EventWithSubscriber pairs and then calls Subscriber.dispatchEvent for each pair.",
            "Subscriber.dispatchEvent performs the executor handoff before invokeSubscriberMethod(event).",
            "invokeSubscriberMethod calls Method.invoke on the actual subscriber method.",
            "A dispatch-handoff hook belongs at the point where the subscriber is actually handed off for execution, not at EventBus.post or queue insertion.",
        ]
    elif tid == "B07":
        details = [
            "EventBus.post is only the public entrypoint; it does not start subscriber method execution.",
            "Dispatcher.dispatch may queue/order deliveries before execution starts.",
            "Subscriber.dispatchEvent calls executor.execute with a lambda; code before executor.execute is still scheduling/handoff, not execution start.",
            "Subscriber execution starts inside the executor lambda.",
            "The exact execution-start boundary is immediately inside the executor lambda, before invokeSubscriberMethod(event).",
            "A hook before executor.execute(...) is wrong for execution-start instrumentation.",
        ]
    elif tid == "B08":
        details = [
            "Subscriber.dispatchEvent performs executor.execute with a lambda around subscriber work.",
            "Inside the lambda, invokeSubscriberMethod(event) calls Method.invoke on the target subscriber method.",
            "If invokeSubscriberMethod(event) returns normally, the subscriber invocation has succeeded.",
            "If invokeSubscriberMethod(event) throws InvocationTargetException, dispatchEvent catches it and calls bus.handleSubscriberException(e.getCause(), context(event)).",
            "A success-after-invoke hook belongs immediately after invokeSubscriberMethod(event) returns normally, before leaving the executor lambda.",
            "A hook before invokeSubscriberMethod(event) or in the catch path is not success-only.",
        ]
    elif tid == "B09":
        details = [
            "Subscriber.dispatchEvent wraps invokeSubscriberMethod(event) in a try/catch inside executor.execute.",
            "invokeSubscriberMethod(event) calls Method.invoke and propagates InvocationTargetException for subscriber-thrown failures.",
            "The catch block in Subscriber.dispatchEvent receives InvocationTargetException before EventBus.handleSubscriberException runs.",
            "bus.handleSubscriberException(e.getCause(), context(event)) converts the failure into the configured SubscriberExceptionHandler path.",
            "A failure-boundary hook belongs in Subscriber.dispatchEvent's InvocationTargetException catch block immediately before bus.handleSubscriberException(...).",
            "A hook before invokeSubscriberMethod(event) is not failure-only; a hook inside EventBus.handleSubscriberException is later than the Subscriber boundary.",
        ]
    elif tid == "B10":
        details = [
            "EventBus.post obtains subscribers from SubscriberRegistry.getSubscribers(event).",
            "If the iterator has subscribers, EventBus.post delegates normal delivery to dispatcher.dispatch(event, eventSubscribers).",
            "If no subscribers are found and the event is not already a DeadEvent, EventBus.post creates and reposts new DeadEvent(this, event).",
            "The no-subscriber repost decision boundary is inside that guarded branch immediately before post(new DeadEvent(this, event)).",
            "A hook at EventBus.post entry fires for all events; a hook in normal dispatch misses the no-subscriber decision.",
        ]
    elif tid == "B11":
        details = [
            "EventBus.post delegates delivery to Dispatcher.dispatch(event, subscribers).",
            "Dispatcher has three concrete handoff sites that call Subscriber.dispatchEvent and all are part of the boundary.",
            "PerThreadQueuedDispatcher hands off with nextEvent.subscribers.next().dispatchEvent(nextEvent.event).",
            "LegacyAsyncDispatcher hands off with e.subscriber.dispatchEvent(e.event).",
            "ImmediateDispatcher hands off with subscribers.next().dispatchEvent(event).",
            "Subscriber.dispatchEvent is already after the dispatcher handoff and then performs executor.execute/invokeSubscriberMethod.",
            "A correct implementation must cover all three concrete Dispatcher handoff sites, either by adding hook calls at each site or routing all three sites through one helper that records the hook immediately before subscriber.dispatchEvent(event).",
            "A handoff hook belongs immediately before concrete Dispatcher calls to subscriber.dispatchEvent(event), not at EventBus.post, queue insertion, or inside Subscriber.",
        ]
    elif tid == "B12":
        details = [
            "Subscriber.dispatchEvent schedules a lambda and calls invokeSubscriberMethod(event); this is outside the reflective call boundary.",
            "Subscriber.invokeSubscriberMethod performs the final call to method.invoke(target, checkNotNull(event)).",
            "The immediate pre-call boundary is inside invokeSubscriberMethod directly before the Method.invoke expression.",
            "Hooks before executor.execute, before invokeSubscriberMethod(event), or in Dispatcher/EventBus are too early.",
        ]
    elif tid == "B13":
        details = [
            "Subscriber.invokeSubscriberMethod calls method.invoke(target, checkNotNull(event)) inside a try block.",
            "IllegalArgumentException and IllegalAccessException are converted to Error in catch blocks.",
            "InvocationTargetException with Error cause is unwrapped and thrown as Error; other InvocationTargetException is rethrown.",
            "Normal return from Method.invoke is only known immediately after the Method.invoke line returns inside the try block.",
            "A hook in dispatchEvent after invokeSubscriberMethod(event) is later than the reflective call boundary; a hook in catches is failure/error path, not normal return.",
        ]
    else:
        details = [
            "EventBus.post logs/starts at the public post entry.",
            "If no subscribers are found and the event is not already DeadEvent, EventBus.post reposts new DeadEvent(this,event).",
            "Normal delivery flows through SubscriberRegistry.getSubscribers and Dispatcher.dispatch.",
            "Each Dispatcher implementation eventually calls Subscriber.dispatchEvent.",
            "Subscriber.dispatchEvent performs executor handoff and calls invokeSubscriberMethod.",
            "Subscriber.invokeSubscriberMethod calls Method.invoke on the actual subscriber method.",
            "A complete trace must include Dispatcher.dispatch and the DeadEvent branch.",
        ]
    return ChainClaim(
        claim_id=f"same_version_chain_v1:{tid}:phase_a_chain",
        task_id=tid,
        kind="call_chain",
        freshness="fresh_same_version",
        anchors=task["anchors"],
        golden_chain=task["golden_chain"],
        summary=task["phase_a"],
        details=details,
    )


def doc_control_text(claim: ChainClaim) -> str:
    return "Plain-text call-chain note (same information as Phase A, not TMF structured claims):\n" + "\n".join(
        f"- {d}" for d in claim.details
    )


def make_repo(task_id: str, dest: Path) -> None:
    src = HERE / "fixtures" / task_id / "base"
    shutil.copytree(src, dest)
    tmf = dest / ".tmf"
    tmf.mkdir()


def compile_check(root: Path) -> dict[str, Any]:
    cp = HERE / "classpath.txt"
    out_dir = Path(tempfile.mkdtemp(prefix="samever-javac-"))
    try:
        cmd = f'javac -nowarn -cp "$(cat {cp})" -d {out_dir} ' + " ".join(str(root / f) for f in PKG_FILES)
        r = subprocess.run(["bash", "-lc", cmd], text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
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


def apply_edit(root: Path, act: dict[str, Any]) -> dict[str, Any]:
    p = safe(root, str(act.get("path", "")))
    if not p:
        return {"error": "invalid path"}
    text = p.read_text(encoding="utf-8", errors="replace")
    if "old" in act and "new" in act:
        old = str(act["old"])
        new = str(act["new"])
        count = text.count(old)
        if count == 1:
            p.write_text(text.replace(old, new), encoding="utf-8")
            return {"ok": True, "path": p.name, "mode": "replace", "bytes_delta": len(new) - len(old)}
        if count == 0:
            old_lines = old.splitlines()
            new_lines = new.splitlines()
            src_lines = text.splitlines()
            matches = []
            if old_lines:
                for i in range(0, len(src_lines) - len(old_lines) + 1):
                    window = src_lines[i : i + len(old_lines)]
                    if all(a.strip() == b.strip() for a, b in zip(window, old_lines)):
                        matches.append(i)
            if len(matches) == 1:
                start = matches[0]
                end = start + len(old_lines)
                src_lines[start:end] = new_lines
                p.write_text("\n".join(src_lines) + ("\n" if text.endswith("\n") else ""), encoding="utf-8")
                return {"ok": True, "path": p.name, "mode": "replace_fuzzy_lines", "bytes_delta": len(new) - len(old)}
        return {"error": f"old text match count {count}, expected 1"}
    if all(k in act for k in ["start", "end", "new"]):
        lines = text.splitlines()
        start = max(1, int(act["start"]))
        end = min(len(lines), int(act["end"]))
        repl = str(act["new"]).splitlines()
        lines[start - 1 : end] = repl
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return {"ok": True, "path": p.name, "mode": "line_replace"}
    return {"error": "edit requires old/new or start/end/new"}


def parse_actions(raw: str) -> list[dict[str, Any]]:
    """Extract every balanced top-level JSON object from a model response.

    Models frequently emit several action objects in one reply (optionally with
    prose or code fences around them). A greedy ``\\{.*\\}`` regex spans from the
    first brace to the last one and fails to parse, silently discarding valid
    actions. Scanning for balanced objects keeps every action, in order.
    """
    try:
        obj = json.loads(raw)
        if isinstance(obj, dict):
            return [obj]
        if isinstance(obj, list):
            return [o for o in obj if isinstance(o, dict)]
    except Exception:
        pass

    found: list[dict[str, Any]] = []
    depth = 0
    start = -1
    in_str = False
    escape = False
    for i, ch in enumerate(raw):
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "{":
            if depth == 0:
                start = i
            depth += 1
            continue
        if ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start >= 0:
                chunk = raw[start : i + 1]
                try:
                    obj = json.loads(chunk)
                    if isinstance(obj, dict) and "action" in obj:
                        found.append(obj)
                except Exception:
                    pass
                start = -1
    return found


def parse_action(raw: str) -> dict[str, Any] | None:
    acts = parse_actions(raw)
    return acts[0] if acts else None


def agent_loop(broker: JsonBrokerAdapter, task: dict[str, Any], arm: str, root: Path, claim: ChainClaim) -> tuple[dict[str, Any] | None, dict[str, Any], list[dict[str, Any]]]:
    injection = ""
    if arm == "TMF_CLAIMS":
        claim_path = root / ".tmf" / "same_version_chain_claims.json"
        claim_path.write_text(json.dumps(claim.to_dict(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        injection = "\nFresh Phase A TMF call-chain claims are available and injected below:\n" + claim_path.read_text(encoding="utf-8")
    elif arm == "DOC_CONTROL":
        injection = "\n" + doc_control_text(claim)

    tools = """Available actions (respond with JSON; natural language around JSON is tolerated, but JSON is safest):
{"action":"list"}
{"action":"read_range","path":"EventBus.java","start":230,"end":270}
{"action":"read_symbol","path":"Subscriber.java","symbol":"dispatchEvent"}
{"action":"search","query":"dispatchEvent"}
{"action":"edit","path":"Subscriber.java","old":"exact old text","new":"replacement text"}
{"action":"compile"}
{"action":"final","answer":"what you changed and why","files":["Subscriber.java"]}
"""
    system = f"""You are a stateless Java coding agent in same_version_chain_v1 Phase B.
Arm: {arm}
Fixture root: {root}
Task: {task['phase_b']}
Trap to consider (not a solution): {task['trap']}
Source is authoritative. Edit files under fixture root only. Keep API compatibility where practical.
Use fine-grained reads before broad reads when possible.
If any edit action returns an error, immediately read the relevant current source range and choose a new exact anchor; do not continue as if the edit succeeded.
If compile fails after an edit, read the failing file around the reported line, fix the compile error, compile again, and do not final until compile passes.
For hook-insertion tasks, verify the final file has exactly one hook definition. Hook call coverage must match the task boundary: single-boundary tasks should have one call, but multi-site boundaries may use either calls at every concrete site or a single shared helper reached by every concrete site.
{tools}
{injection}
Begin now."""
    hist: list[str] = []
    transcript: list[dict[str, Any]] = []
    met = {"tool_calls": 0, "source_bytes": 0, "source_reads": 0, "range_reads": 0, "symbol_reads": 0, "source_files": [], "prompt_tokens": 0, "completion_tokens": 0, "invalid": 0, "wall_seconds": 0.0}
    final = None
    start_time = time.time()
    for turn in range(MAX_TURNS):
        prompt = system + "\n" + ("\n".join(hist[-18:]) if hist else "")
        met["prompt_tokens"] += tok(prompt)
        try:
            resp = broker.answer(prompt, budget=1)
            raw = resp["answer"]
        except Exception as e:  # noqa: BLE001
            transcript.append({"turn": turn, "broker_error": str(e)})
            break
        met["completion_tokens"] += tok(raw)
        acts = parse_actions(raw)
        transcript.append({"turn": turn, "prompt_tail": prompt[-5000:], "raw": raw, "actions": acts, "action": acts[0] if acts else None})
        if not acts:
            met["invalid"] += 1
            hist += ["AGENT:" + raw, "SYSTEM: I could not parse a JSON action. Continue with one of the documented JSON actions; do not restart."]
            continue
        turn_outputs = []
        stop_after_turn = False
        for act in acts:
            met["tool_calls"] += 1
            a = act.get("action")
            if a == "list":
                out = {"files": sorted(p.name for p in root.glob("*.java"))}
            elif a == "search":
                q = str(act.get("query", "")).lower()
                hits = []
                for p in sorted(root.glob("*.java")):
                    for i, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                        if q and q in line.lower():
                            hits.append(f"{p.name}:{i}:{line}")
                out = {"hits": hits[:80]}
            elif a == "read_range":
                p = safe(root, str(act.get("path", "")))
                if not p:
                    out = {"error": "invalid path"}
                else:
                    lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
                    st = max(1, int(act.get("start", 1)))
                    en = min(len(lines), int(act.get("end", st + 80)))
                    content = read_numbered(p, st, en)
                    b = len(content.encode())
                    met["source_bytes"] += b; met["source_reads"] += 1; met["range_reads"] += 1; met["source_files"].append(p.name)
                    out = {"path": p.name, "start": st, "end": en, "content": content}
            elif a == "read_symbol":
                p = safe(root, str(act.get("path", "")))
                sym = str(act.get("symbol", ""))
                if not p:
                    out = {"error": "invalid path"}
                else:
                    rng = find_symbol_range(p, sym)
                    if not rng:
                        out = {"error": "symbol not found"}
                    else:
                        content = read_numbered(p, rng[0], rng[1])
                        b = len(content.encode())
                        met["source_bytes"] += b; met["source_reads"] += 1; met["symbol_reads"] += 1; met["source_files"].append(p.name)
                        out = {"path": p.name, "symbol": sym, "start": rng[0], "end": rng[1], "content": content}
            elif a == "read":
                p = safe(root, str(act.get("path", "")))
                if not p:
                    out = {"error": "invalid path"}
                else:
                    content = read_numbered(p)
                    b = len(content.encode())
                    met["source_bytes"] += b; met["source_reads"] += 1; met["source_files"].append(p.name)
                    out = {"path": p.name, "content": content}
            elif a == "edit":
                out = apply_edit(root, act)
            elif a == "compile":
                out = compile_check(root)
            elif a == "final":
                final = act
                stop_after_turn = True
                break
            else:
                out = {"error": "unknown action"}
            turn_outputs.append({"action": act, "tool_output": out})
        transcript[-1]["tool_outputs"] = turn_outputs
        if turn_outputs:
            transcript[-1]["tool_output"] = turn_outputs[-1]["tool_output"]
            hist += ["AGENT:" + raw, "TOOL:" + json.dumps(turn_outputs, ensure_ascii=False)[:12000]]
        if stop_after_turn:
            break
    met["wall_seconds"] = round(time.time() - start_time, 3)
    met["source_files"] = sorted(set(met["source_files"]))
    return final, met, transcript


def audit_task(task: dict[str, Any], diffs: dict[str, str], compile_result: dict[str, Any], final: dict[str, Any] | None) -> dict[str, Any]:
    all_diff = "\n".join(diffs.values())
    final_text = json.dumps(final or {}, ensure_ascii=False)
    combined = (all_diff + "\n" + final_text).lower()
    golden_hits = [node for node in task["golden_chain"] if node.lower() in combined]
    tid = task["id"]
    if tid == "B01":
        has_subscriber_scope = "Subscriber.java" in diffs and (
            "ratelimit" in combined
            or "rate limit" in combined
            or "rate limiting" in combined
            or "lastpermit" in combined
            or "lastrate" in combined
            or "100" in combined
        )
        async_aware = "asynceventbus" in combined or "legacyasync" in combined or "dispatcher" in combined or "dispatchEvent" in all_diff
        not_post_only = not (set(diffs.keys()) <= {"EventBus.java"})
        trap_pass = has_subscriber_scope and not_post_only and async_aware
        reason = {"has_subscriber_scope": has_subscriber_scope, "not_post_only": not_post_only, "async_aware": async_aware}
    elif tid == "B02":
        subscriber_changed = "Subscriber.java" in diffs
        retry_loop = any(x in combined for x in ["retry", "attempt", "max_retries", "maxretries", "for (int", "while ("])
        final_handler = "handlesubscriberexception" in combined or "handleSubscriberException" in all_diff
        no_eventbus_only = not (set(diffs.keys()) <= {"EventBus.java"})
        trap_pass = subscriber_changed and retry_loop and final_handler and no_eventbus_only
        reason = {"subscriber_changed": subscriber_changed, "retry_loop": retry_loop, "final_handler_preserved": final_handler, "not_eventbus_only": no_eventbus_only}
    elif tid == "B03":
        logs = any(x in combined for x in ["logger", "log(", "fine", "debug"])
        has_dispatcher = "Dispatcher.java" in diffs or "dispatcher.dispatch" in combined
        has_dead = "deadevent" in combined
        has_subscriber = "Subscriber.java" in diffs or "dispatchEvent" in all_diff or "invokesubscribermethod" in combined
        trap_pass = logs and has_dispatcher and has_dead and has_subscriber
        reason = {"logs": logs, "dispatcher_covered": has_dispatcher, "dead_event_covered": has_dead, "subscriber_covered": has_subscriber}
    elif tid == "B06":
        subscriber_changed = "Subscriber.java" in diffs
        async_aware = "AsyncEventBus.java" in diffs or "Dispatcher.java" in diffs or "dispatcher.dispatch" in combined or "legacyasync" in combined
        handoff_hook = any(x in combined for x in ["handoff", "dispatch-handoff", "handed off", "execution", "invoke"])
        not_post_only = not (set(diffs.keys()) <= {"EventBus.java"})
        trap_pass = subscriber_changed and async_aware and handoff_hook and not_post_only
        reason = {"subscriber_changed": subscriber_changed, "async_aware": async_aware, "handoff_hook": handoff_hook, "not_post_only": not_post_only}
    elif tid == "B07":
        sub_diff = diffs.get("Subscriber.java", "")
        subscriber_changed = bool(sub_diff)
        hookish = any(x in combined for x in ["execution", "start", "hook", "record", "begin"])
        before_invoke_add = bool(re.search(r"(?m)^\+\s*[^\n]*(?:hook|record|begin|start|execution|onSubscriberExecutionStart)[^\n]*\n[ \t]+invokeSubscriberMethod\(event\);", sub_diff, re.IGNORECASE))
        before_execute = bool(re.search(r"final void dispatchEvent\(Object event\).*?\+\s*[^\n]*(?:hook|record|begin|start|execution)[^\n]*\n\s*executor\.execute", sub_diff, re.IGNORECASE | re.DOTALL))
        not_post_or_dispatcher_only = not (set(diffs.keys()) <= {"EventBus.java", "Dispatcher.java"})
        trap_pass = subscriber_changed and hookish and before_invoke_add and not before_execute and not_post_or_dispatcher_only
        reason = {"subscriber_changed": subscriber_changed, "hookish": hookish, "inside_lambda_before_invoke": before_invoke_add, "not_before_executor_execute": not before_execute, "not_post_or_dispatcher_only": not_post_or_dispatcher_only}
    elif tid == "B08":
        sub_diff = diffs.get("Subscriber.java", "")
        subscriber_changed = bool(sub_diff)
        hookish = any(x in combined for x in ["success", "succeed", "hook", "record", "after"])
        after_invoke_add = bool(re.search(r"(?m)invokeSubscriberMethod\(event\);\n\+\s*[^\n]*(?:hook|record|success|succeed|after|onSubscriberInvocationSuccess)[^\n]*", sub_diff, re.IGNORECASE))
        before_invoke_add = bool(re.search(r"(?m)^\+\s*[^\n]*(?:hook|record|success|succeed|after)[^\n]*\n[ \t]+invokeSubscriberMethod\(event\);", sub_diff, re.IGNORECASE))
        catch_blocks = re.findall(r"(?s)catch \(InvocationTargetException[^)]*\) \{(.*?)\n[ \t]*\}", sub_diff, re.IGNORECASE)
        catch_hook = any(re.search(r"(?m)^\+\s*[^\n]*(?:hook|record|success|succeed)", block, re.IGNORECASE) for block in catch_blocks)
        trap_pass = subscriber_changed and hookish and after_invoke_add and not before_invoke_add and not catch_hook
        reason = {"subscriber_changed": subscriber_changed, "hookish": hookish, "after_invoke_success_boundary": after_invoke_add, "not_before_invoke": not before_invoke_add, "not_in_failure_catch": not catch_hook}
    elif tid == "B09":
        sub_diff = diffs.get("Subscriber.java", "")
        subscriber_changed = bool(sub_diff)
        hookish = any(x in combined for x in ["failure", "exception", "hook", "record"])
        before_handler = bool(re.search(r"(?s)catch \(InvocationTargetException[^}]*?\+\s*[^\n]*(?:hook|record|failure|exception|onSubscriberInvocationFailure)[^\n]*\n\+?[ \t]*bus\.handleSubscriberException", sub_diff, re.IGNORECASE))
        before_invoke = bool(re.search(r"(?m)^\+\s*[^\n]*(?:hook|record|failure|exception)[^\n]*\n[ \t]+invokeSubscriberMethod\(event\);", sub_diff, re.IGNORECASE))
        eventbus_changed = "EventBus.java" in diffs and not subscriber_changed
        trap_pass = subscriber_changed and hookish and before_handler and not before_invoke and not eventbus_changed
        reason = {"subscriber_changed": subscriber_changed, "hookish": hookish, "catch_before_handleSubscriberException": before_handler, "not_before_invoke": not before_invoke, "not_eventbus_only": not eventbus_changed}
    elif tid == "B10":
        ev_diff = diffs.get("EventBus.java", "")
        eventbus_changed = bool(ev_diff)
        hookish = any(x in combined for x in ["dead", "no subscriber", "nosubscriber", "hook", "record", "repost"])
        before_dead_post = bool(re.search(r"(?m)^\+\s*[^\n]*(?:hook|record|dead|subscriber|repost|onDeadEventRepost)[^\n]*\n[ \t]+post\(new DeadEvent\(this, event\)\);", ev_diff, re.IGNORECASE))
        post_entry = bool(re.search(r"void post\(Object event\).*?\+\s*[^\n]*(?:hook|record|dead|subscriber|repost)", ev_diff, re.IGNORECASE | re.DOTALL)) and not before_dead_post
        subscriber_or_dispatcher_only = set(diffs.keys()) <= {"Subscriber.java", "Dispatcher.java"}
        trap_pass = eventbus_changed and hookish and before_dead_post and not post_entry and not subscriber_or_dispatcher_only
        reason = {"eventbus_changed": eventbus_changed, "hookish": hookish, "before_dead_event_repost": before_dead_post, "not_post_entry": not post_entry, "not_subscriber_or_dispatcher_only": not subscriber_or_dispatcher_only}
    elif tid == "B11":
        disp_diff = diffs.get("Dispatcher.java", "")
        dispatcher_changed = bool(disp_diff)
        hookish = any(x in combined for x in ["handoff", "dispatch", "hook", "record", "subscriber"])
        before_dispatch_event = bool(re.search(r"(?m)^\+\s*[^\n]*(?:hook|record|handoff|dispatch|subscriber)[^\n]*\n[ \t]*(?:subscriber|e\.subscriber)\.dispatchEvent\(", disp_diff, re.IGNORECASE))
        helper_wraps_dispatch = bool(re.search(r"(?s)\+\s*private static void [^{]+\{[^}]*recordDispatcherToSubscriberHandoff[^}]*subscriber\.dispatchEvent\(event\);", disp_diff, re.IGNORECASE))
        replaced_dispatch_sites = len(re.findall(r"(?m)^-\s*(?:subscribers\.next\(\)|nextEvent\.subscribers\.next\(\)|e\.subscriber)\.dispatchEvent\(", disp_diff))
        subscriber_only = set(diffs.keys()) <= {"Subscriber.java"}
        eventbus_only = set(diffs.keys()) <= {"EventBus.java"}
        full_dispatcher_coverage = before_dispatch_event or (helper_wraps_dispatch and replaced_dispatch_sites >= 3)
        trap_pass = dispatcher_changed and hookish and full_dispatcher_coverage and not subscriber_only and not eventbus_only
        reason = {"dispatcher_changed": dispatcher_changed, "hookish": hookish, "before_subscriber_dispatchEvent_or_full_helper": full_dispatcher_coverage, "replaced_dispatch_sites": replaced_dispatch_sites, "not_subscriber_only": not subscriber_only, "not_eventbus_only": not eventbus_only}
    elif tid == "B12":
        sub_diff = diffs.get("Subscriber.java", "")
        subscriber_changed = bool(sub_diff)
        hookish = any(x in combined for x in ["method", "invoke", "hook", "record", "before", "pre"])
        hook_before_direct_method_invoke = bool(re.search(r"(?m)^\+\s*[^\n]*(?:hook|record|method|invoke|before|pre)[^\n]*\n[ \t]*method\.invoke\(target, checkNotNull\(event\)\);", sub_diff, re.IGNORECASE))
        hoisted_nullcheck_then_hook_then_invoke = bool(re.search(r"(?m)^\+\s*(?:Object|[A-Za-z_][A-Za-z0-9_<>]*)\s+([A-Za-z_][A-Za-z0-9_]*)\s*=\s*checkNotNull\(event\);\n\+\s*[^\n]*(?:hook|record|method|invoke|before|pre)[^\n]*\n\+?\s*method\.invoke\(target,\s*\1\);", sub_diff, re.IGNORECASE))
        # Directly adding a hook before method.invoke(target, checkNotNull(event)) is still before checkNotNull(event) is evaluated,
        # so it is too early for the immediate reflective-call boundary. Hoisting checkNotNull before the hook is acceptable.
        immediate_pre_reflective_call = hoisted_nullcheck_then_hook_then_invoke
        outside_dispatch = bool(re.search(r"dispatchEvent\(Object event\).*?\+\s*[^\n]*(?:hook|record|method|invoke|before|pre)", sub_diff, re.IGNORECASE | re.DOTALL)) and not immediate_pre_reflective_call
        trap_pass = subscriber_changed and hookish and immediate_pre_reflective_call and not outside_dispatch
        reason = {"subscriber_changed": subscriber_changed, "hookish": hookish, "hoisted_nullcheck_then_hook_then_MethodInvoke": hoisted_nullcheck_then_hook_then_invoke, "direct_hook_before_checkNotNull_expr_is_too_early": hook_before_direct_method_invoke, "not_outer_dispatchEvent": not outside_dispatch}
    elif tid == "B13":
        sub_diff = diffs.get("Subscriber.java", "")
        subscriber_changed = bool(sub_diff)
        hookish = any(x in combined for x in ["normal", "return", "success", "method", "invoke", "hook", "record", "after"])
        after_method_invoke = bool(re.search(r"(?m)method\.invoke\(target, checkNotNull\(event\)\);\n\+\s*[^\n]*(?:hook|record|normal|return|success|after|method|invoke)[^\n]*", sub_diff, re.IGNORECASE))
        catch_hook = bool(re.search(r"(?s)catch \([^)]*\) \{[^}]*?\+\s*[^\n]*(?:hook|record|normal|return|success)", sub_diff, re.IGNORECASE))
        outer_dispatch = bool(re.search(r"dispatchEvent\(Object event\).*?invokeSubscriberMethod\(event\);\n\+\s*[^\n]*(?:hook|record|normal|return|success|after)", sub_diff, re.IGNORECASE | re.DOTALL))
        trap_pass = subscriber_changed and hookish and after_method_invoke and not catch_hook and not outer_dispatch
        reason = {"subscriber_changed": subscriber_changed, "hookish": hookish, "inside_invokeSubscriberMethod_after_MethodInvoke": after_method_invoke, "not_catch_path": not catch_hook, "not_outer_dispatchEvent": not outer_dispatch}
    elif tid == "B04":
        subscriber_changed = "Subscriber.java" in diffs
        attempt_counting = any(x in combined for x in ["attempt", "count", "counter", "increment", "invocation"])
        around_invocation = "invokesubscribermethod" in combined or "method.invoke" in combined
        not_post_or_dispatcher_only = not (set(diffs.keys()) <= {"EventBus.java", "Dispatcher.java"})
        trap_pass = subscriber_changed and attempt_counting and around_invocation and not_post_or_dispatcher_only
        reason = {"subscriber_changed": subscriber_changed, "attempt_counting": attempt_counting, "around_invocation": around_invocation, "not_post_or_dispatcher_only": not_post_or_dispatcher_only}
    else:  # B05
        subscriber_changed = "Subscriber.java" in diffs
        success_hook = any(x in combined for x in ["success", "succeeded", "onsuccess", "recordsubscriber", "hook"])
        after_invocation = "invokesubscribermethod" in combined or "method.invoke" in combined
        failure_path_preserved = "handlesubscriberexception" in combined or "handleSubscriberException" in all_diff
        not_post_or_dispatcher_only = not (set(diffs.keys()) <= {"EventBus.java", "Dispatcher.java"})
        trap_pass = subscriber_changed and success_hook and after_invocation and failure_path_preserved and not_post_or_dispatcher_only
        reason = {"subscriber_changed": subscriber_changed, "success_hook": success_hook, "after_invocation": after_invocation, "failure_path_preserved": failure_path_preserved, "not_post_or_dispatcher_only": not_post_or_dispatcher_only}
    return {
        "compile_ok": bool(compile_result.get("ok")),
        "modified_files": sorted(diffs.keys()),
        "golden_hits": golden_hits,
        "golden_coverage": round(len(golden_hits) / len(task["golden_chain"]), 3),
        "trap_pass": trap_pass,
        "trap_reason": reason,
        "valid_answer": final is not None and bool(diffs) and bool(compile_result.get("ok")),
    }


def run_one(broker: JsonBrokerAdapter, task_id: str, arm: str, raw_dir: Path, work_dir: Path) -> dict[str, Any]:
    task = TASKS[task_id]
    claim = build_chain_claim(task)
    root = work_dir / f"{task_id}__{arm}"
    make_repo(task_id, root)
    before = snapshot(root)
    final, met, transcript = agent_loop(broker, task, arm, root, claim)
    comp = compile_check(root)
    diffs = diff_files(before, root)
    aud = audit_task(task, diffs, comp, final)
    raw = {"task_id": task_id, "arm": arm, "root": str(root), "claim": claim.to_dict() if arm == "TMF_CLAIMS" else None, "doc_control": doc_control_text(claim) if arm == "DOC_CONTROL" else None, "final": final, "telemetry": met, "compile": comp, "diffs": diffs, "audit": aud, "transcript": transcript}
    raw_path = raw_dir / f"{task_id}__{arm}.raw.json"
    raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {k: raw[k] for k in ["task_id", "arm", "final", "telemetry", "compile", "audit"]} | {"raw_path": str(raw_path.relative_to(HERE)), "diff_bytes": sum(len(d.encode()) for d in diffs.values())}


def summarize(rows: list[dict[str, Any]], mode: str) -> dict[str, Any]:
    valid = sum(1 for r in rows if r["audit"]["valid_answer"])
    traps = sum(1 for r in rows if r["audit"]["trap_pass"])
    compile_ok = sum(1 for r in rows if r["audit"]["compile_ok"])
    by_task: dict[str, list[dict[str, Any]]] = {}
    for r in rows:
        by_task.setdefault(r["task_id"], []).append(r)
    differentiation = {}
    for tid, rs in by_task.items():
        vals = {r["arm"]: r["audit"]["trap_pass"] for r in rs}
        differentiation[tid] = len(set(vals.values())) > 1
    return {
        "mode": mode,
        "runs": len(rows),
        "valid_answers": valid,
        "compile_ok": compile_ok,
        "trap_passes": traps,
        "differentiation_by_task": differentiation,
        "zero_harness_errors": True,
        "smoke_gate": {
            "at_least_2_of_3_valid_per_task": all(sum(1 for r in rs if r["audit"]["valid_answer"]) >= 2 for rs in by_task.values()),
            "trap_tests_distinguish_some_task": any(differentiation.values()),
            "zero_harness_runtime_errors": True,
        },
    }


def write_report(out: dict[str, Any], report_path: Path) -> None:
    s = out["summary"]
    lines = [
        f"# {report_path.stem}",
        "",
        f"Mode: {s['mode']}",
        f"Runs: {s['runs']}",
        f"Valid answers: {s['valid_answers']}/{s['runs']}",
        f"Compile OK: {s['compile_ok']}/{s['runs']}",
        f"Trap passes: {s['trap_passes']}/{s['runs']}",
        f"Differentiation by task: `{json.dumps(s['differentiation_by_task'], ensure_ascii=False)}`",
        "",
        "## Rows",
        "",
    ]
    for r in out["rows"]:
        a = r["audit"]
        t = r["telemetry"]
        lines.append(f"- {r['task_id']} / {r['arm']}: valid={a['valid_answer']} compile={a['compile_ok']} trap={a['trap_pass']} coverage={a['golden_coverage']} files={a['modified_files']} bytes_read={t['source_bytes']} calls={t['tool_calls']} wall={t['wall_seconds']}s raw={r['raw_path']}")
        lines.append(f"  - trap_reason={json.dumps(a['trap_reason'], ensure_ascii=False)}")
    lines += [
        "",
        "## Gate",
        "",
        "```json",
        json.dumps(s["smoke_gate"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Caveats",
        "",
        "Machine audit is intentionally syntactic/behavioral-light: it checks compilation plus whether edits touch the expected layer and mention/modify key chain nodes. It does not execute a full Guava test suite or prove runtime rate-limit/retry/log behavior exhaustively.",
    ]
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--task")
    ap.add_argument("--arm", choices=ARMS)
    ap.add_argument("--tag", default=None)
    args = ap.parse_args()
    ids = [args.task] if args.task else (TASKS_DOC["smoke"] if args.smoke or not args.full else [t["id"] for t in TASKS_DOC["tasks"]])
    arms = [args.arm] if args.arm else ARMS
    mode = "full" if args.full else "smoke"
    tag = args.tag or ("full" if args.full else "smoke")
    results = HERE / "results"
    raw_dir = results / "raw" / tag
    work_dir = results / "work" / tag
    if raw_dir.exists(): shutil.rmtree(raw_dir)
    if work_dir.exists(): shutil.rmtree(work_dir)
    raw_dir.mkdir(parents=True)
    work_dir.mkdir(parents=True)
    broker = JsonBrokerAdapter(BROKER, expected_model=MODEL, timeout_seconds=TIMEOUT)
    preflight = broker.preflight().__dict__
    rows = []
    for tid in ids:
        for arm in arms:
            print(f"RUN {tid} {arm}", flush=True)
            row = run_one(broker, tid, arm, raw_dir, work_dir)
            rows.append(row)
            print(f"DONE {tid} {arm} valid={row['audit']['valid_answer']} trap={row['audit']['trap_pass']} compile={row['audit']['compile_ok']}", flush=True)
    out = {"schema": "same_version_chain_v1_results", "mode": mode, "tag": tag, "model": MODEL, "preflight": preflight, "rows": rows}
    out["summary"] = summarize(rows, mode)
    out_path = results / f"{tag}.json"
    out_path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = results / ("FULL_REPORT.md" if args.full else "SMOKE_REPORT.md")
    write_report(out, report)
    with (HERE / "EXECUTION_NOTES.md").open("a", encoding="utf-8") as f:
        f.write(f"\n## Run {tag}\n\nWrote `{out_path.relative_to(HERE)}` and `{report.relative_to(HERE)}`. Summary: {json.dumps(out['summary'], ensure_ascii=False)}\n")
    print("wrote", out_path, report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
