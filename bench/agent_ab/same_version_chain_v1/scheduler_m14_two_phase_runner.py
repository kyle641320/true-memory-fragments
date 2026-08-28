#!/usr/bin/env python3
from __future__ import annotations

import argparse
import difflib
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WORKSPACE = Path('/root/.openclaw/workspace')
SOURCE_FIXTURE = WORKSPACE / 'benchmarks' / 'java-workflow-fixtures' / 'scheduler-partial-failure-idempotency'
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
TAG = 'scheduler_m14_two_phase_stale_context'
ARMS = ['SOURCE_ONLY', 'PREREAD_STALE_SOURCE', 'STALE_DOC_CONTROL', 'TMF_STALE_GATED']
SERVICE = 'src/main/java/com/example/scheduler/NotificationScheduler.java'
TEST = 'src/test/java/com/example/scheduler/NotificationSchedulerContractTest.java'
HIDDEN_TEST = '.m14_post_contracts/NotificationSchedulerContractTest.java'

OLD_SERVICE = '''package com.example.scheduler;

public class NotificationScheduler {
    private final NotificationTaskRepository repository;
    private final NotificationSender sender;

    public NotificationScheduler(NotificationTaskRepository repository, NotificationSender sender) {
        this.repository = repository;
        this.sender = sender;
    }

    public int runOnce(int limit) {
        int processed = 0;
        for (NotificationTask task : repository.findPendingBatch(limit)) {
            repository.markSent(task.getId());
            sender.send(task.getId());
            processed++;
        }
        return processed;
    }
}
'''


POST_MUTATED_SERVICE = '''package com.example.scheduler;

public class NotificationScheduler {
    private final NotificationTaskRepository repository;
    private final NotificationSender sender;

    public NotificationScheduler(NotificationTaskRepository repository, NotificationSender sender) {
        this.repository = repository;
        this.sender = sender;
    }

    public int runOnce(int limit) {
        int processed = 0;
        for (NotificationTask task : repository.findPendingBatch(limit)) {
            if (deliverLegacy(task)) {
                processed++;
            }
        }
        return processed;
    }

    private boolean deliverLegacy(NotificationTask task) {
        repository.markSent(task.getId());
        sender.send(task.getId());
        return true;
    }
}
'''



def copytree(src: Path, dest: Path) -> None:
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(src, dest, ignore=shutil.ignore_patterns('target', '.git'))


def hide_post_contracts(root: Path) -> None:
    src = root / TEST
    dst = root / HIDDEN_TEST
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.exists():
        dst.write_text(src.read_text(encoding='utf-8'), encoding='utf-8')
        src.unlink()


def restore_post_contracts(root: Path) -> None:
    src = root / HIDDEN_TEST
    dst = root / TEST
    dst.parent.mkdir(parents=True, exist_ok=True)
    if src.exists():
        dst.write_text(src.read_text(encoding='utf-8'), encoding='utf-8')


def mutate_to_phase_b(root: Path) -> None:
    p = root / SERVICE
    text = p.read_text(encoding='utf-8')
    if text != OLD_SERVICE:
        raise RuntimeError('pre-mutation NotificationScheduler.java did not match expected old fixture')
    p.write_text(POST_MUTATED_SERVICE, encoding='utf-8')
    restore_post_contracts(root)


def make_repo(dest: Path) -> dict[str, Any]:
    copytree(SOURCE_FIXTURE, dest)
    service = dest / SERVICE
    if service.read_text(encoding='utf-8') != OLD_SERVICE:
        raise RuntimeError('source fixture NotificationScheduler.java does not match expected pre-mutation text')
    hide_post_contracts(dest)
    (dest / '.tmf').mkdir(exist_ok=True)
    return {
        'fixture': 'scheduler-partial-failure-idempotency',
        'phase_a': 'old source visible; post contract test hidden',
        'phase_b_mutation': 'source refactored to a transactional writer boundary and post contract test restored',
    }


def build_phase_a_claim(root: Path, orientation: dict[str, Any] | None) -> Claim:
    src = root / SERVICE
    text = src.read_text(encoding='utf-8')
    method = next(m for m in extract_java_methods(SERVICE, text) if m.qualname.endswith('NotificationScheduler.runOnce'))
    blob = subprocess.check_output(['git', 'hash-object', str(src)], text=True).strip()
    summary = (orientation or {}).get('summary') or 'runOnce finds pending tasks, marks each task sent, then sends the notification and counts it as processed.'
    return Claim(
        id='scheduler_m14:old:NotificationScheduler.runOnce',
        claim=(
            'Verified old notification scheduling workflow: NotificationScheduler.runOnce is the dispatch boundary. '
            'It loads repository.findPendingBatch(limit), calls repository.markSent(taskId) before sender.send(taskId), '
            'and counts each iterated pending task as processed. Phase-A agent orientation: ' + str(summary)
        ),
        kind='structure',
        scope='method',
        bindings=[Binding(
            path=SERVICE,
            file_blob=blob,
            fn_hash=method.class_hash,
            commit=None,
            qualname='NotificationScheduler.runOnce',
            role='method',
            line_start=method.line_start,
            line_end=method.line_end,
            hash_kind='java_node_hash',
        )],
        provenance='synthetic Phase-A claim from pre-mutation scheduler-partial-failure-idempotency fixture',
        evidence='verified',
        confidence=0.96,
        endorsed_by=None,
        last_verified=now_utc(),
        model='deterministic-bench',
        body={'language': 'java', 'node_kind': 'method', 'qualname': 'NotificationScheduler.runOnce', 'task_id': 'SCHEDULER_M14', 'mutation_expected_stale': True},
    )


def old_source_excerpt(root: Path) -> str:
    return (root / SERVICE).read_text(encoding='utf-8')


def safe(root: Path, rel: str) -> Path | None:
    return base_runner.safe(root, rel)


def read_numbered(p: Path, start: int = 1, end: int | None = None) -> str:
    return base_runner.read_numbered(p, start, end)


def find_symbol_range(p: Path, symbol: str) -> tuple[int, int] | None:
    return base_runner.find_symbol_range(p, symbol)


def parse_actions(raw: str) -> list[dict[str, Any]]:
    return base_runner.parse_actions(raw)


def apply_edit(root: Path, act: dict[str, Any]) -> dict[str, Any]:
    p = safe(root, str(act.get('path', '')))
    if not p:
        return {'error': 'invalid path'}
    old = str(act.get('old', ''))
    new = str(act.get('new', ''))
    text = p.read_text(encoding='utf-8')
    if not old:
        return {'error': 'empty old'}
    n = text.count(old)
    if n != 1:
        return {'error': f'old text occurrences={n}'}
    p.write_text(text.replace(old, new), encoding='utf-8')
    return {'ok': True, 'path': str(p.relative_to(root)), 'bytes': len(new.encode('utf-8'))}


def mvn(root: Path, args: list[str], timeout: int = 120) -> dict[str, Any]:
    r = subprocess.run(['mvn', '-q', *args], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return {'ok': r.returncode == 0, 'exit': r.returncode, 'stdout': r.stdout[-4000:], 'stderr': r.stderr[-4000:]}


def mvn_compile(root: Path) -> dict[str, Any]:
    return mvn(root, ['-DskipTests', 'compile'], timeout=90)


def mvn_test(root: Path) -> dict[str, Any]:
    return mvn(root, ['test'], timeout=120)


def snapshot(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): p.read_text(encoding='utf-8', errors='replace') for p in sorted(root.rglob('*.java')) if 'target' not in p.parts and '.m14_post_contracts' not in p.parts}


def diff_files(before: dict[str, str], root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    all_files = set(before)
    all_files.update(str(p.relative_to(root)) for p in root.rglob('*.java') if 'target' not in p.parts and '.m14_post_contracts' not in p.parts)
    for f in sorted(all_files):
        old = before.get(f, '')
        p = root / f
        new = p.read_text(encoding='utf-8', errors='replace') if p.exists() else ''
        if new != old:
            out[f] = '\n'.join(difflib.unified_diff(old.splitlines(), new.splitlines(), fromfile=f'a/{f}', tofile=f'b/{f}', lineterm=''))
    return out


def list_visible_files(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and 'target' not in p.parts and '.m14_post_contracts' not in p.parts)[:400]


def search_visible(root: Path, query: str) -> list[str]:
    q = query.lower()
    hits: list[str] = []
    for p in sorted(root.rglob('*')):
        if not p.is_file() or 'target' in p.parts or '.m14_post_contracts' in p.parts or p.suffix not in {'.java', '.xml', '.md'}:
            continue
        for i, line in enumerate(p.read_text(encoding='utf-8', errors='replace').splitlines(), 1):
            if q and q in line.lower():
                hits.append(f'{p.relative_to(root)}:{i}:{line}')
    return hits[:160]


def placement_check(root: Path) -> dict[str, Any]:
    sched = (root / SERVICE).read_text(encoding='utf-8', errors='replace')
    repo = (root / 'src/main/java/com/example/scheduler/NotificationTaskRepository.java').read_text(encoding='utf-8', errors='replace')
    has_claim_api = 'claimPendingBatch' in repo
    uses_claim = 'claimPendingBatch(' in sched
    uses_find_pending = 'findPendingBatch(' in sched
    mark_before_send = bool(re.search(r'markSent\([^;]+;(?s:.*?)sender\.send\(', sched))
    send_before_mark = bool(re.search(r'sender\.send\([^;]+;(?s:.*?)markSent\(', sched))
    catches_runtime = bool(re.search(r'catch\s*\(\s*(?:RuntimeException|Exception)\b', sched))
    legacy_helper = 'deliverLegacy' in sched
    return {
        'has_claim_api': has_claim_api,
        'uses_claim': uses_claim,
        'uses_find_pending': uses_find_pending,
        'mark_before_send': mark_before_send,
        'send_before_mark': send_before_mark,
        'catches_runtime': catches_runtime,
        'legacy_helper': legacy_helper,
    }


def deterministic_test(root: Path) -> dict[str, Any]:
    test = mvn_test(root)
    place = placement_check(root)
    reasons: list[str] = []
    if not test.get('ok'):
        reasons.append('mvn test failed')
    if not place['has_claim_api']:
        reasons.append('repository lacks claimPendingBatch')
    if not place['uses_claim']:
        reasons.append('scheduler does not claim pending batch')
    if place['mark_before_send']:
        reasons.append('scheduler marks SENT before send')
    return {'ok': bool(test.get('ok')), 'placement': place, 'test': test, 'message': 'PASS' if test.get('ok') else '; '.join(reasons)}


def run_phase_a(broker: JsonBrokerAdapter, root: Path, max_turns: int) -> tuple[dict[str, Any] | None, dict[str, Any], list[dict[str, Any]]]:
    tools = '''Available actions (respond with exactly ONE JSON object per turn, no prose):
{"action":"list"}
{"action":"read_range","path":"relative file","start":1,"end":220}
{"action":"read_symbol","path":"relative .java file","symbol":"symbol name from current source"}
{"action":"search","query":"text to search for"}
{"action":"compile"}
{"action":"orientation","summary":"brief source-derived understanding of the notification scheduling workflow"}
'''
    system = f'''You are orienting on a Java service before any implementation work.
Fixture root: {root}
Task: Take a quick look at the notification scheduling workflow and understand how notification dispatch currently works. Do not edit yet.
Edits and finals are not allowed in this phase. Read enough source to form a concrete orientation, then return the orientation action.
{tools}
Begin now.'''
    hist: list[str] = []
    transcript: list[dict[str, Any]] = []
    met = {'tool_calls': 0, 'source_reads': 0, 'source_bytes': 0, 'source_files': [], 'prompt_tokens': 0, 'completion_tokens': 0, 'invalid': 0, 'edits_rejected': 0, 'compile_calls': 0}
    orientation = None
    for turn in range(max_turns):
        prompt = system + '\n' + ('\n'.join(hist[-12:]) if hist else '')
        met['prompt_tokens'] += base_runner.tok(prompt)
        try:
            raw = broker.answer(prompt, budget=1)['answer']
        except Exception as e:
            if 'preflight is required' in str(e):
                try:
                    broker.preflight(); raw = broker.answer(prompt, budget=1)['answer']
                except Exception as e2:
                    transcript.append({'turn': turn, 'broker_error': str(e2)}); break
            else:
                transcript.append({'turn': turn, 'broker_error': str(e)}); break
        met['completion_tokens'] += base_runner.tok(raw)
        acts = parse_actions(raw)
        transcript.append({'turn': turn, 'raw': raw, 'actions': acts})
        if not acts:
            met['invalid'] += 1
            hist += ['AGENT:' + raw, 'SYSTEM: respond with exactly one JSON action, no prose.']
            continue
        if len(acts) > 1:
            acts = acts[:1]
        act = acts[0]; a = act.get('action'); met['tool_calls'] += 1
        if a == 'list':
            out = {'files': list_visible_files(root)}
        elif a == 'search':
            out = {'hits': search_visible(root, str(act.get('query', '')))}
        elif a == 'read_range':
            p = safe(root, str(act.get('path', '')))
            if not p:
                out = {'error': 'invalid path'}
            else:
                st = max(1, int(act.get('start', 1))); en = int(act.get('end', st + 120)); content = read_numbered(p, st, en)
                met['source_reads'] += 1; met['source_bytes'] += len(content.encode()); met['source_files'].append(str(p.relative_to(root)))
                out = {'path': str(p.relative_to(root)), 'content': content}
        elif a == 'read_symbol':
            p = safe(root, str(act.get('path', ''))); sym = str(act.get('symbol', ''))
            if not p:
                out = {'error': 'invalid path'}
            else:
                rng = find_symbol_range(p, sym)
                if not rng:
                    out = {'error': 'symbol not found'}
                else:
                    content = read_numbered(p, rng[0], rng[1])
                    met['source_reads'] += 1; met['source_bytes'] += len(content.encode()); met['source_files'].append(str(p.relative_to(root)))
                    out = {'path': str(p.relative_to(root)), 'symbol': sym, 'content': content}
        elif a == 'compile':
            met['compile_calls'] += 1; out = mvn_compile(root)
        elif a == 'orientation':
            if met['source_reads'] < 1:
                out = {'error': 'orientation rejected: read source first'}
            else:
                orientation = act; out = {'ok': True}; transcript[-1]['tool_outputs'] = [{'action': act, 'tool_output': out}]; break
        elif a in {'edit', 'final'}:
            met['edits_rejected'] += 1; out = {'error': f'{a} rejected: Phase A is orientation/read-only'}
        else:
            out = {'error': 'unknown action'}
        transcript[-1]['tool_outputs'] = [{'action': act, 'tool_output': out}]
        hist += ['AGENT:' + raw, 'TOOL:' + json.dumps([{'action': act, 'tool_output': out}], ensure_ascii=False)[:12000]]
    met['source_files'] = sorted(set(met['source_files']))
    return orientation, met, transcript


def phase_b_injection(arm: str, phase_a_transcript: list[dict[str, Any]], claim: Claim, freshness: Any) -> str:
    if arm == 'PREREAD_STALE_SOURCE':
        compact = []
        for t in phase_a_transcript:
            compact.append({'turn': t.get('turn'), 'action': (t.get('actions') or [{}])[0], 'tool_outputs': t.get('tool_outputs')})
        return '\nEarlier in this same task you already oriented on the source. Continue with that remembered Phase-A context; do not assume a full restart. Your Phase-A transcript was:\n```json\n' + json.dumps(compact, ensure_ascii=False, indent=2)[:9000] + '\n```\n'
    if arm == 'STALE_DOC_CONTROL':
        return '\nMaintenance note from the scheduler handbook (not freshness-bound): notification dispatch intentionally marks tasks as sent before calling the external sender so retry scans do not resend the same task. `runOnce` should continue to use the pending-batch scan and preserve that mark-before-send ordering unless a small local compile fix is needed.\n'
    if arm == 'TMF_STALE_GATED':
        if freshness.fresh:
            return '\nFresh TMF claim injected below:\n' + json.dumps(claim.to_dict(), ensure_ascii=False, indent=2)
        return '\nTMF freshness warning: a previously verified claim about the old `NotificationScheduler.runOnce` workflow was WITHHELD because its source binding is stale. Withheld claim id: ' + claim.id + '. Stale bindings: ' + json.dumps(freshness.stale_bindings, ensure_ascii=False) + '. Do not rely on hidden old workflow notes; solve from the current task/source/contracts.\n'
    return ''


def run_phase_b(broker: JsonBrokerAdapter, arm: str, root: Path, phase_a_transcript: list[dict[str, Any]], claim: Claim, freshness: Any, final_gate: str, max_turns: int):
    task = '线上通知任务偶尔会丢、偶尔又重复发。帮我把这块调度逻辑修稳一点，失败时不要把状态搞乱，后续重跑也别重复打扰用户。'
    tools = '''Available actions (respond with exactly ONE JSON object per turn, no prose, no arrays, no multiple concatenated JSON objects):
{"action":"list"}
{"action":"read_range","path":"relative file","start":1,"end":220}
{"action":"read_symbol","path":"relative .java file","symbol":"symbol name from current source"}
{"action":"search","query":"text to search for"}
{"action":"edit","path":"relative file","old":"exact text copied from latest read output","new":"replacement text"}
{"action":"compile"}
{"action":"final","answer":"what changed","files":["relative files"]}
'''
    system = f'''You are a stateless Java coding agent in scheduler_m14_two_phase_stale_context.
Arm: {arm}
Fixture root: {root}
Task from user: {task}
Make the smallest compiling change that satisfies the current project contracts.
When editing, copy exact old text from latest read output. If an edit fails, re-read the relevant current source and retry with exact current source text.
Final gate mode: {final_gate}
Edit only files under fixture root. Respond with exactly one JSON action per turn. If you need multiple actions, do them across multiple turns. You must perform at least one successful edit before final; never final if no edit action returned ok=true. Run compile before final. After compile succeeds, immediately send the final JSON action on the next turn. This is a pure A/B run: no semantic acceptance feedback is available to the agent.
{tools}
{phase_b_injection(arm, phase_a_transcript, claim, freshness)}
Begin now.'''
    hist: list[str] = []
    transcript: list[dict[str, Any]] = []
    met = {'tool_calls': 0, 'source_bytes': 0, 'source_reads': 0, 'source_files': [], 'prompt_tokens': 0, 'completion_tokens': 0, 'invalid': 0, 'wall_seconds': 0.0, 'successful_edits': 0, 'rejected_finals': 0, 'duplicate_edit_suppressed': 0, 'extra_actions_ignored': 0, 'post_test_pass_observed': False}
    final = None; start = time.time()
    for turn in range(max_turns):
        prompt = system + '\n' + ('\n'.join(hist[-18:]) if hist else '')
        met['prompt_tokens'] += base_runner.tok(prompt)
        try:
            raw = broker.answer(prompt, budget=1)['answer']
        except Exception as e:
            if 'preflight is required' in str(e):
                try:
                    broker.preflight(); raw = broker.answer(prompt, budget=1)['answer']
                except Exception as e2:
                    transcript.append({'turn': turn, 'broker_error': str(e2)}); break
            else:
                transcript.append({'turn': turn, 'broker_error': str(e)}); break
        met['completion_tokens'] += base_runner.tok(raw)
        acts = parse_actions(raw)
        transcript.append({'turn': turn, 'raw': raw, 'actions': acts})
        if len(acts) == 1 and acts[0].get('action') is None and any(k in acts[0] for k in ('files', 'answer', 'message')):
            acts = [{'action': 'final', **acts[0]}]
        if not acts:
            met['invalid'] += 1; hist += ['AGENT:' + raw, 'SYSTEM: respond with exactly one JSON action, no prose.']; continue
        if len(acts) > 1:
            met['extra_actions_ignored'] += len(acts) - 1; acts = acts[:1]
        outs: list[dict[str, Any]] = []
        stop = False
        act = acts[0]; met['tool_calls'] += 1; a = act.get('action')
        if a == 'list':
            out = {'files': list_visible_files(root)}
        elif a == 'search':
            out = {'hits': search_visible(root, str(act.get('query', '')))}
        elif a == 'read_range':
            p = safe(root, str(act.get('path', '')))
            if not p:
                out = {'error': 'invalid path'}
            else:
                st = max(1, int(act.get('start', 1))); en = int(act.get('end', st + 120)); content = read_numbered(p, st, en)
                met['source_bytes'] += len(content.encode()); met['source_reads'] += 1; met['source_files'].append(str(p.relative_to(root))); out = {'path': str(p.relative_to(root)), 'content': content}
        elif a == 'read_symbol':
            p = safe(root, str(act.get('path', ''))); sym = str(act.get('symbol', ''))
            if not p:
                out = {'error': 'invalid path'}
            else:
                rng = find_symbol_range(p, sym)
                if not rng:
                    out = {'error': 'symbol not found'}
                else:
                    content = read_numbered(p, rng[0], rng[1]); met['source_bytes'] += len(content.encode()); met['source_reads'] += 1; met['source_files'].append(str(p.relative_to(root))); out = {'path': str(p.relative_to(root)), 'symbol': sym, 'content': content}
        elif a == 'edit':
            out = apply_edit(root, act)
            if out.get('ok') is True:
                met['successful_edits'] += 1
        elif a == 'compile':
            out = mvn_test(root)
            if out.get('ok'):
                met['post_test_pass_observed'] = True
        elif a == 'final':
            if final_gate == 'hard' and met['successful_edits'] < 1:
                out = {'error': 'final rejected: no successful edit has occurred'}; met['rejected_finals'] += 1
            else:
                final = act; stop = True; break
        else:
            out = {'error': 'unknown action'}
        outs.append({'action': act, 'tool_output': out})
        transcript[-1]['tool_outputs'] = outs
        if outs:
            tool_text = json.dumps(outs, ensure_ascii=False)[:14000]
            if a == 'compile' and out.get('ok'):
                tool_text += '\nSYSTEM: compile succeeded. Next turn respond with exactly one final JSON action and no prose.'
            hist += ['AGENT:' + raw, 'TOOL:' + tool_text]
        if stop:
            break
    met['wall_seconds'] = round(time.time() - start, 3); met['source_files'] = sorted(set(met['source_files']))
    return final, met, transcript


def audit(diffs: dict[str, str], final: dict[str, Any] | None, root: Path) -> dict[str, Any]:
    post = deterministic_test(root)
    valid = final is not None and bool(diffs) and post['test'].get('ok') is True
    semantic_pass = valid and post['ok']
    return {'valid_answer': valid, 'compile_ok': bool(post['test'].get('ok')), 'trap_pass': semantic_pass, 'semantic_pass': semantic_pass, 'trap_reason': post['placement'] | {'post_message': post['message']}}


def classify_failure(raw: dict[str, Any]) -> dict[str, Any]:
    cls = base_runner.classify_run_failure(raw)
    categories = list(cls.get('categories', []))
    telemetry = raw.get('telemetry', {})
    post = raw.get('post_test') or {}
    if raw.get('final') is None and post.get('ok') and raw.get('diffs'):
        if 'no_final_after_success' not in categories:
            categories.insert(0, 'no_final_after_success')
        categories = [c for c in categories if c != 'no_final']
    if telemetry.get('extra_actions_ignored', 0):
        categories.append('extra_actions_ignored')
    passed = bool(cls.get('pass'))
    primary = 'pass' if passed else (categories[0] if categories else cls.get('primary', 'uncategorized_fail'))
    out = dict(cls); out['primary'] = primary; out['categories'] = categories
    out['extra_actions_ignored'] = int(telemetry.get('extra_actions_ignored', 0))
    out['result_ok_but_raw_failed'] = bool((not passed) and post.get('ok') and raw.get('diffs'))
    return out


def metric_view(raw: dict[str, Any]) -> dict[str, Any]:
    cats = set(raw.get('failure_classification', {}).get('categories', []))
    aud = raw['audit']; post = raw.get('post_test') or {}
    raw_pass = bool(aud['valid_answer'] and aud['compile_ok'] and aud['semantic_pass'])
    protocol_clean = not bool(cats & {'no_effect_false_completion', 'compile_fail', 'parse_or_invalid_action_noise'}) and aud['valid_answer'] and aud['compile_ok'] and bool(raw.get('diffs'))
    semantic_evaluable = protocol_clean
    task_result_pass = bool(post.get('ok') and raw.get('diffs'))
    return {'raw_pass': raw_pass, 'protocol_clean': protocol_clean, 'semantic_evaluable': semantic_evaluable, 'semantic_pass': bool(aud['semantic_pass']) if semantic_evaluable else None, 'task_result_pass': task_result_pass, 'post_test_ok': bool(post.get('ok'))}


def run_one(broker: JsonBrokerAdapter, arm: str, rep: int, raw_dir: Path, work_dir: Path, final_gate: str, phase_a_turns: int, phase_b_turns: int) -> dict[str, Any]:
    root = work_dir / f'RPC_M14__{arm}__r{rep}'
    fixture_meta = make_repo(root)
    orientation, phase_a_met, phase_a_transcript = run_phase_a(broker, root, phase_a_turns)
    claim = build_phase_a_claim(root, orientation)
    pre_excerpt = old_source_excerpt(root)
    mutate_to_phase_b(root)
    fresh = check_freshness(GitRepo(root), claim)
    before = snapshot(root)
    final, met, transcript = run_phase_b(broker, arm, root, phase_a_transcript, claim, fresh, final_gate, phase_b_turns)
    post = deterministic_test(root)
    diffs = diff_files(before, root)
    aud = audit(diffs, final, root)
    raw = {
        'task_id': 'RPC_M14', 'arm': arm, 'rep': rep, 'final_gate': final_gate, 'phase_a_max_turns': phase_a_turns, 'phase_b_max_turns': phase_b_turns,
        'fixture_meta': fixture_meta, 'phase_a_orientation': orientation, 'phase_a_telemetry': phase_a_met, 'phase_a_transcript': phase_a_transcript,
        'phase_a_old_source_excerpt': pre_excerpt,
        'stale_claim_present': arm in {'PREREAD_STALE_SOURCE', 'STALE_DOC_CONTROL', 'TMF_STALE_GATED'},
        'stale_claim_fresh': fresh.fresh,
        'stale_claim_withheld': bool(arm == 'TMF_STALE_GATED' and not fresh.fresh),
        'withheld_claim_id': claim.id if arm == 'TMF_STALE_GATED' and not fresh.fresh else None,
        'freshness': {'fresh': fresh.fresh, 'stale_bindings': fresh.stale_bindings},
        'final': final, 'telemetry': met, 'post_test': post, 'diffs': diffs, 'audit': aud, 'transcript': transcript,
    }
    raw['failure_classification'] = classify_failure(raw); raw['metrics'] = metric_view(raw)
    raw_path = raw_dir / f'SCHEDULER_M14__{arm}__r{rep}.raw.json'
    raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    keep = ['task_id', 'arm', 'rep', 'final_gate', 'phase_a_max_turns', 'phase_b_max_turns', 'phase_a_orientation', 'phase_a_telemetry', 'stale_claim_present', 'stale_claim_fresh', 'stale_claim_withheld', 'withheld_claim_id', 'freshness', 'final', 'telemetry', 'post_test', 'audit', 'failure_classification', 'metrics']
    return {k: raw[k] for k in keep} | {'raw_path': str(raw_path.relative_to(HERE)), 'diff_bytes': sum(len(d.encode()) for d in diffs.values())}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by: dict[str, Any] = {}
    for arm in ARMS:
        rs = [r for r in rows if r['arm'] == arm]
        by[arm] = {
            'runs': len(rs),
            'raw_pass': sum(r['metrics']['raw_pass'] for r in rs),
            'task_result_pass': sum(r['metrics']['task_result_pass'] for r in rs),
            'post_test_ok': sum(r['metrics']['post_test_ok'] for r in rs),
            'semantic_evaluable': sum(r['metrics']['semantic_evaluable'] for r in rs),
            'semantic_adjusted_pass': sum(1 for r in rs if r['metrics']['semantic_pass'] is True),
            'stale_claim_withheld': sum(1 for r in rs if r.get('stale_claim_withheld')),
            'uses_claim': sum(1 for r in rs if r.get('post_test', {}).get('placement', {}).get('uses_claim')),
            'mark_before_send': sum(1 for r in rs if r.get('post_test', {}).get('placement', {}).get('mark_before_send')),
            'uses_find_pending': sum(1 for r in rs if r.get('post_test', {}).get('placement', {}).get('uses_find_pending')),
            'extra_actions_ignored': sum(r.get('failure_classification', {}).get('extra_actions_ignored', 0) for r in rs),
            'result_ok_but_raw_failed': sum(1 for r in rs if r.get('failure_classification', {}).get('result_ok_but_raw_failed')),
            'primary': {},
        }
        for r in rs:
            p = r['failure_classification'].get('primary', 'unknown')
            by[arm]['primary'][p] = by[arm]['primary'].get(p, 0) + 1
    return {'mode': TAG, 'runs': len(rows), 'by_arm': by}


def write_report(out: dict[str, Any], path: Path) -> None:
    lines = [
        '# Scheduler M14 Two-Phase Stale Context Report',
        '',
        'Fixture: `benchmarks/java-workflow-fixtures/scheduler-partial-failure-idempotency`.',
        '',
        'This runner implements the corrected two-phase human-task design: Phase A is old-source orientation only, then the runner mutates/restores post contracts and Phase B receives a deliberately vague human-style notification-loss/duplicate bug report rather than file/method instructions.',
        '',
        '```json', json.dumps(out['summary'], ensure_ascii=False, indent=2), '```', '', '## Rows',
    ]
    for r in out['rows']:
        lines.append(f"- rep {r['rep']} {r['arm']}: raw={r['metrics']['raw_pass']} task_result={r['metrics']['task_result_pass']} semantic={r['metrics']['semantic_pass']} post={r['post_test']['ok']} withheld={r.get('stale_claim_withheld')} failure={r['failure_classification']['primary']} placement={json.dumps(r['post_test']['placement'], ensure_ascii=False)} raw_path={r['raw_path']}")
    path.write_text('\n'.join(lines) + '\n', encoding='utf-8')


def setup_check() -> dict[str, Any]:
    tmp = HERE / 'results' / 'work' / '_scheduler_m14_setup_check'
    if tmp.exists():
        shutil.rmtree(tmp)
    make_repo(tmp)
    pre_compile = mvn_compile(tmp)
    claim = build_phase_a_claim(tmp, {'summary': 'deterministic setup check'})
    mutate_to_phase_b(tmp)
    freshness = check_freshness(GitRepo(tmp), claim)
    post_test = mvn_test(tmp)
    out = {
        'pre_compile_ok': pre_compile.get('ok'),
        'freshness_after_mutation': {'fresh': freshness.fresh, 'stale_bindings': freshness.stale_bindings},
        'post_baseline_tests_ok_expected_false': post_test.get('ok'),
        'post_placement': placement_check(tmp),
    }
    out['ok'] = bool(pre_compile.get('ok') and freshness.fresh is False and post_test.get('ok') is False)
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument('--repeats', type=int, default=1)
    ap.add_argument('--tag', default=TAG)
    ap.add_argument('--final-gate', choices=['hard'], default='hard')
    ap.add_argument('--phase-a-turns', type=int, default=4)
    ap.add_argument('--phase-b-turns', type=int, default=12)
    ap.add_argument('--setup-check', action='store_true')
    args = ap.parse_args()
    if args.setup_check:
        ok = setup_check().get('ok')
        raise SystemExit(0 if ok else 1)
    results = HERE / 'results'; raw_dir = results / 'raw' / args.tag; work_dir = results / 'work' / args.tag
    if raw_dir.exists():
        shutil.rmtree(raw_dir)
    if work_dir.exists():
        shutil.rmtree(work_dir)
    raw_dir.mkdir(parents=True); work_dir.mkdir(parents=True)
    broker = JsonBrokerAdapter(BROKER, expected_model=MODEL, timeout_seconds=TIMEOUT); preflight = broker.preflight().__dict__
    rows: list[dict[str, Any]] = []
    for rep in range(1, args.repeats + 1):
        for arm in ARMS:
            print(f'RUN rep={rep} arm={arm}', flush=True)
            row = run_one(broker, arm, rep, raw_dir, work_dir, args.final_gate, args.phase_a_turns, args.phase_b_turns); rows.append(row)
            print(f"DONE rep={rep} arm={arm} raw={row['metrics']['raw_pass']} task={row['metrics']['task_result_pass']} failure={row['failure_classification']['primary']}", flush=True)
            out = {'schema': TAG, 'model': MODEL, 'final_gate': args.final_gate, 'phase_a_turns': args.phase_a_turns, 'phase_b_turns': args.phase_b_turns, 'preflight': preflight, 'rows': rows, 'summary': summarize(rows)}
            (results / f'{args.tag}.json').write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    out = {'schema': TAG, 'model': MODEL, 'final_gate': args.final_gate, 'phase_a_turns': args.phase_a_turns, 'phase_b_turns': args.phase_b_turns, 'preflight': preflight, 'rows': rows, 'summary': summarize(rows)}
    jp = results / f'{args.tag}.json'; rp = results / f'{args.tag.upper()}_REPORT.md'
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + '\n', encoding='utf-8'); write_report(out, rp)
    print('WROTE', jp, rp); print(json.dumps(out['summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
