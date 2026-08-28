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
WORKSPACE = Path('/root/.openclaw/workspace')
SOURCE_FIXTURE = WORKSPACE / 'benchmarks' / 'java-workflow-fixtures' / 'cdc-search-index-projection-consistency'
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
TAG = 'cdc_m12_projection_stale_workflow'
ARMS = ['SOURCE_ONLY', 'PREREAD_STALE_SOURCE', 'STALE_DOC_CONTROL', 'TMF_STALE_GATED']
MAIN = 'src/main/java/com/example/projection/ProductProjectionConsumer.java'
REPO = 'src/main/java/com/example/projection/ProjectionCheckpointRepository.java'

OLD_ON_EVENT = '''    public void onEvent(ProductChangeEvent event) {
        if (event.isDeleted()) {
            searchIndexClient.delete(event.getProductId());
        } else {
            searchIndexClient.upsert(new SearchDocument(event.getProductId(), event.getName(), event.getVersion()));
        }
        checkpointRepository.saveVersion(event.getProductId(), event.getVersion());
    }'''

MUTATED_ON_EVENT = '''    public void onEvent(ProductChangeEvent event) {
        projectEventToSearchIndex(event);
        checkpointRepository.saveVersion(event.getProductId(), event.getVersion());
    }

    private void projectEventToSearchIndex(ProductChangeEvent event) {
        if (event.isDeleted()) {
            searchIndexClient.delete(event.getProductId());
        } else {
            searchIndexClient.upsert(new SearchDocument(event.getProductId(), event.getName(), event.getVersion()));
        }
    }'''


def copytree(src: Path, dest: Path):
    if dest.exists():
        shutil.rmtree(dest)
    ignore = shutil.ignore_patterns('target', '.git')
    shutil.copytree(src, dest, ignore=ignore)


def mutate_current(root: Path):
    p = root / MAIN
    text = p.read_text(encoding='utf-8')
    if text.count(OLD_ON_EVENT) != 1:
        raise RuntimeError('old onEvent snippet not unique')
    p.write_text(text.replace(OLD_ON_EVENT, MUTATED_ON_EVENT), encoding='utf-8')


def make_repo(dest: Path, *, mutated: bool = True) -> dict[str, Any]:
    copytree(SOURCE_FIXTURE, dest)
    if mutated:
        mutate_current(dest)
    (dest / '.tmf').mkdir(exist_ok=True)
    return {'fixture': 'cdc-search-index-projection-consistency', 'mutation': 'extract projection side effect into helper while leaving unconditional legacy saveVersion plausible', 'mutated': mutated}


def pre_claim() -> Claim:
    src = SOURCE_FIXTURE / MAIN
    text = src.read_text(encoding='utf-8')
    method = next(m for m in extract_java_methods(MAIN, text) if m.qualname.endswith('ProductProjectionConsumer.onEvent'))
    blob = subprocess.check_output(['git', 'hash-object', str(src)], text=True).strip()
    return Claim(
        id='cdc_m12:old:ProductProjectionConsumer.onEvent',
        claim=(
            'Verified old CDC projection workflow: ProductProjectionConsumer.onEvent applies every ProductChangeEvent '
            'to the search index and then records the event version using checkpointRepository.saveVersion(productId, version). '
            'Keep the checkpoint write in onEvent after projection; saveVersion is the checkpoint boundary.'
        ),
        kind='structure',
        scope='method',
        bindings=[Binding(
            path=MAIN,
            file_blob=blob,
            fn_hash=method.class_hash,
            commit=None,
            qualname='ProductProjectionConsumer.onEvent',
            role='method',
            line_start=method.line_start,
            line_end=method.line_end,
            hash_kind='java_node_hash',
        )],
        provenance='synthetic stale claim from pre-mutation CDC projection fixture',
        evidence='verified',
        confidence=0.96,
        endorsed_by=None,
        last_verified=now_utc(),
        model='deterministic-bench',
        body={'language':'java','node_kind':'method','qualname':'ProductProjectionConsumer.onEvent','task_id':'CDC_M12','mutation_expected_stale':True},
    )


def old_source_excerpt() -> str:
    return OLD_ON_EVENT


def safe(root: Path, rel: str) -> Path | None:
    rel = rel.strip()
    p = (root / rel).resolve()
    try:
        p.relative_to(root.resolve())
    except ValueError:
        return None
    if not p.exists() or not p.is_file():
        return None
    return p


def read_numbered(p: Path, start: int = 1, end: int | None = None) -> str:
    lines = p.read_text(encoding='utf-8', errors='replace').splitlines()
    if end is None:
        end = len(lines)
    return '\n'.join(f'{i}: {lines[i-1]}' for i in range(max(1,start), min(end, len(lines)) + 1))


def find_symbol_range(p: Path, symbol: str) -> tuple[int, int] | None:
    return base_runner.find_symbol_range(p, symbol)


def parse_actions(raw: str) -> list[dict[str, Any]]:
    return base_runner.parse_actions(raw)


def apply_edit(root: Path, act: dict[str, Any]) -> dict[str, Any]:
    p = safe(root, str(act.get('path','')))
    if not p:
        return {'error': 'invalid path'}
    old = str(act.get('old',''))
    new = str(act.get('new',''))
    text = p.read_text(encoding='utf-8')
    if not old:
        return {'error': 'empty old'}
    n = text.count(old)
    if n != 1:
        return {'error': f'old text occurrences={n}'}
    p.write_text(text.replace(old, new), encoding='utf-8')
    return {'ok': True, 'path': str(p.relative_to(root)), 'bytes': len(new.encode('utf-8'))}


def mvn_test(root: Path) -> dict[str, Any]:
    r = subprocess.run(['mvn','-q','test'], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=120)
    return {'ok': r.returncode == 0, 'exit': r.returncode, 'stdout': r.stdout[-4000:], 'stderr': r.stderr[-4000:]}


def snapshot(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): p.read_text(encoding='utf-8', errors='replace') for p in sorted(root.rglob('*.java'))}


def diff_files(before: dict[str, str], root: Path) -> dict[str, str]:
    out = {}
    for f, old in before.items():
        p = root / f
        new = p.read_text(encoding='utf-8', errors='replace') if p.exists() else ''
        if new != old:
            out[f] = '\n'.join(difflib.unified_diff(old.splitlines(), new.splitlines(), fromfile=f'a/{f}', tofile=f'b/{f}', lineterm=''))
    return out


def source_placement_check(root: Path) -> dict[str, Any]:
    c = (root / MAIN).read_text(encoding='utf-8', errors='replace')
    r = (root / REPO).read_text(encoding='utf-8', errors='replace')
    uses_legacy_save = 'checkpointRepository.saveVersion(' in c
    has_cas_method = 'advanceVersionIfNewer' in r
    uses_latest = 'latestVersion(' in c
    uses_cas = 'advanceVersionIfNewer(' in c
    stale_guard = bool(re.search(r'if\s*\([^\)]*getVersion\(\)\s*<=\s*[^\)]*\)\s*\{\s*return\s*;', c, re.S)) or ('<= current' in c and 'return;' in c)
    advances_after_projection = bool(re.search(r'(upsert|delete)\([^;]+;(?s:.*?)advanceVersionIfNewer\(', c))
    return {
        'uses_legacy_save': uses_legacy_save,
        'has_cas_method': has_cas_method,
        'uses_latest_version': uses_latest,
        'uses_cas_advance': uses_cas,
        'has_stale_guard': stale_guard,
        'advances_after_projection': advances_after_projection,
    }


def deterministic_test(root: Path) -> dict[str, Any]:
    test = mvn_test(root)
    place = source_placement_check(root)
    ok = bool(test.get('ok'))
    reasons = []
    if not test.get('ok'):
        reasons.append('mvn test failed')
    if place['uses_legacy_save']:
        reasons.append('consumer still uses unconditional saveVersion')
    if not place['has_cas_method']:
        reasons.append('repository lacks advanceVersionIfNewer')
    if not place['uses_latest_version']:
        reasons.append('consumer does not read latestVersion')
    if not place['uses_cas_advance']:
        reasons.append('consumer does not use CAS advance')
    return {'ok': ok, 'placement': place, 'test': test, 'message': 'PASS' if ok else '; '.join(reasons)}


def audit(diffs: dict[str,str], final: dict[str,Any] | None, root: Path) -> dict[str, Any]:
    post = deterministic_test(root)
    place = post['placement']
    valid = final is not None and bool(diffs) and post['test'].get('ok') is True
    trap = valid and post['ok'] and not place['uses_legacy_save']
    return {'valid_answer': valid, 'compile_ok': bool(post['test'].get('ok')), 'trap_pass': trap, 'trap_reason': place | {'post_message': post['message']}}


def metric_view(raw: dict[str, Any]) -> dict[str, Any]:
    cats = set(raw.get('failure_classification', {}).get('categories', []))
    aud = raw['audit']; post = raw.get('post_test') or {}
    raw_pass = bool(aud['valid_answer'] and aud['compile_ok'] and aud['trap_pass'])
    protocol_clean = not bool(cats & {'no_effect_false_completion','compile_fail','parse_or_invalid_action_noise'}) and aud['valid_answer'] and aud['compile_ok'] and bool(raw.get('diffs'))
    semantic_evaluable = protocol_clean
    task_result_pass = bool(post.get('ok') and raw.get('diffs'))
    return {'raw_pass': raw_pass, 'protocol_clean': protocol_clean, 'semantic_evaluable': semantic_evaluable, 'semantic_pass': bool(aud['trap_pass']) if semantic_evaluable else None, 'task_result_pass': task_result_pass, 'post_test_ok': bool(post.get('ok'))}


def classify_failure(raw: dict[str, Any]) -> dict[str, Any]:
    cls = base_runner.classify_run_failure(raw)
    categories = list(cls.get('categories', []))
    telemetry = raw.get('telemetry', {})
    post = raw.get('post_test') or {}
    if raw.get('final') is None and post.get('ok') and raw.get('diffs'):
        if 'no_final_after_success' not in categories:
            categories.insert(0, 'no_final_after_success')
        categories = [c for c in categories if c != 'no_final']
    if telemetry.get('duplicate_edit_suppressed', 0):
        categories.append('duplicate_edit_suppressed')
    passed = bool(cls.get('pass'))
    primary = 'pass' if passed else (categories[0] if categories else cls.get('primary','uncategorized_fail'))
    out = dict(cls); out['primary'] = primary; out['categories'] = categories
    out['duplicate_edit_suppressed'] = int(telemetry.get('duplicate_edit_suppressed',0))
    out['extra_actions_ignored'] = int(telemetry.get('extra_actions_ignored',0))
    out['result_ok_but_raw_failed'] = bool((not passed) and post.get('ok') and raw.get('diffs'))
    return out


def agent_loop(broker: JsonBrokerAdapter, arm: str, root: Path, claim: Claim, freshness: Any, final_gate: str, max_turns: int):
    if arm == 'TMF_STALE_GATED':
        if freshness.fresh:
            injection = '\nFresh TMF claim injected below:\n' + json.dumps(claim.to_dict(), ensure_ascii=False, indent=2)
        else:
            injection = '\nTMF stale gate: an old claim about ProductProjectionConsumer.onEvent was WITHHELD because freshness failed: ' + json.dumps(freshness.stale_bindings, ensure_ascii=False) + '. Do not rely on old unconditional checkpoint/saveVersion workflow notes; infer the correct CDC idempotency workflow from current source and tests.\n'
    elif arm == 'STALE_DOC_CONTROL':
        injection = '\nPlain project handbook note (no freshness binding):\n- ProductProjectionConsumer.onEvent is the approved projection checkpoint boundary. Apply the event to the search index and then call checkpointRepository.saveVersion(productId, version) from onEvent so the projection checkpoint reflects every delivered CDC event. Keep this simple onEvent workflow unless compile errors force a change.\n'
    elif arm == 'PREREAD_STALE_SOURCE':
        injection = '\nEarlier in this same task, before the repository changed, you inspected ProductProjectionConsumer.onEvent and formed this working conclusion from source: onEvent applies every event to SearchIndexClient and then records the checkpoint with checkpointRepository.saveVersion(productId, version). You saw this old source excerpt:\n```java\n' + old_source_excerpt() + '\n```\nNow continue after repository files changed. Do not redo broad source exploration; only read current source/tests as needed to make the edit apply exactly.\n'
    else:
        injection = ''
    task = (
        'Fix the CDC/search projection consumer so stale events cannot overwrite newer search documents, tombstone events delete documents, '
        'and the checkpoint advances only after a successful search-index update. Keep compatibility where reasonable, but the consumer must not use unconditional saveVersion for this workflow. '
        'Make the smallest compiling change that satisfies the project contract tests.'
    )
    tools = '''Available actions (respond with exactly ONE JSON object per turn, no prose, no arrays, no multiple concatenated JSON objects):
{"action":"list"}
{"action":"read_range","path":"relative file","start":1,"end":220}
{"action":"read_symbol","path":"relative .java file","symbol":"symbol name from current source"}
{"action":"search","query":"text to search for"}
{"action":"edit","path":"relative file","old":"exact text copied from latest read output","new":"replacement text"}
{"action":"compile"}
{"action":"final","answer":"what changed","files":["relative files"]}
'''
    guidance = 'If the TMF stale gate withheld a claim, treat old notes as unsafe and infer from current source/tests.' if arm == 'TMF_STALE_GATED' else ('If a project handbook note gives an approved checkpoint boundary, prefer it unless current tests/source contradict it.' if arm == 'STALE_DOC_CONTROL' else ('You are continuing from remembered old source; re-read enough current source/tests to make exact edits.' if arm == 'PREREAD_STALE_SOURCE' else 'Infer the fix from current source and tests.'))
    system = f'''You are a stateless Java coding agent in cdc_m12_projection_stale_workflow.
Arm: {arm}
Fixture root: {root}
Task: {task}
{guidance}
When editing, copy exact old text from latest read output. If an edit fails, re-read the relevant current source and retry with exact current source text.
Final gate mode: {final_gate}
Edit only files under fixture root. Respond with exactly one JSON action per turn. If you need multiple actions, do them across multiple turns. You must perform at least one successful edit before final; never final if no edit action returned ok=true. Run compile before final. After compile succeeds, immediately send the final JSON action on the next turn. This is a pure A/B run: no semantic acceptance feedback is available to the agent.
{tools}
{injection}
Begin now.'''
    hist=[]; transcript=[]; met={'tool_calls':0,'source_bytes':0,'source_reads':0,'source_files':[],'prompt_tokens':0,'completion_tokens':0,'invalid':0,'wall_seconds':0.0,'successful_edits':0,'rejected_finals':0,'duplicate_edit_suppressed':0,'extra_actions_ignored':0,'post_test_pass_observed':False}
    final=None; start=time.time()
    for turn in range(max_turns):
        prompt=system+'\n'+('\n'.join(hist[-18:]) if hist else '')
        met['prompt_tokens'] += base_runner.tok(prompt)
        try:
            raw=broker.answer(prompt, budget=1)['answer']
        except Exception as e:
            if 'preflight is required' in str(e):
                try:
                    broker.preflight(); raw=broker.answer(prompt, budget=1)['answer']
                except Exception as e2:
                    transcript.append({'turn':turn,'broker_error':str(e2)}); break
            else:
                transcript.append({'turn':turn,'broker_error':str(e)}); break
        met['completion_tokens'] += base_runner.tok(raw)
        acts=parse_actions(raw)
        transcript.append({'turn':turn,'raw':raw,'actions':acts})
        if len(acts)==1 and acts[0].get('action') is None and any(k in acts[0] for k in ('files','answer','message')):
            acts=[{'action':'final', **acts[0]}]
        if not acts:
            met['invalid'] += 1
            hist += ['AGENT:'+raw, 'SYSTEM: respond with exactly one JSON action, no prose.']
            continue
        if len(acts) > 1:
            met['extra_actions_ignored'] += len(acts) - 1
            acts = acts[:1]
        outs=[]; stop=False; edit_seen=False
        for act in acts:
            met['tool_calls'] += 1; a=act.get('action')
            if a == 'list':
                out={'files': sorted(str(p.relative_to(root)) for p in root.rglob('*') if p.is_file() and ('target' not in p.parts))[:400]}
            elif a == 'search':
                q=str(act.get('query','')).lower(); hits=[]
                for p in sorted(root.rglob('*')):
                    if not p.is_file() or 'target' in p.parts or p.suffix not in {'.java','.xml','.md'}: continue
                    for i,line in enumerate(p.read_text(encoding='utf-8', errors='replace').splitlines(),1):
                        if q and q in line.lower(): hits.append(f'{p.relative_to(root)}:{i}:{line}')
                out={'hits':hits[:160]}
            elif a == 'read_range':
                p=safe(root, str(act.get('path','')))
                if not p: out={'error':'invalid path'}
                else:
                    st=max(1,int(act.get('start',1))); en=int(act.get('end',st+120)); content=read_numbered(p,st,en)
                    met['source_bytes'] += len(content.encode()); met['source_reads'] += 1; met['source_files'].append(str(p.relative_to(root))); out={'path':str(p.relative_to(root)),'content':content}
            elif a == 'read_symbol':
                p=safe(root, str(act.get('path',''))); sym=str(act.get('symbol',''))
                if not p: out={'error':'invalid path'}
                else:
                    rng=find_symbol_range(p,sym)
                    if not rng: out={'error':'symbol not found'}
                    else:
                        content=read_numbered(p,rng[0],rng[1]); met['source_bytes'] += len(content.encode()); met['source_reads'] += 1; met['source_files'].append(str(p.relative_to(root))); out={'path':str(p.relative_to(root)),'symbol':sym,'content':content}
            elif a == 'edit':
                if edit_seen:
                    met['duplicate_edit_suppressed'] += 1; out={'error':'duplicate edit ignored; only one edit is allowed per turn'}; outs.append({'action':act,'tool_output':out}); continue
                out=apply_edit(root,act)
                if out.get('ok') is True:
                    met['successful_edits'] += 1; edit_seen=True
            elif a == 'compile':
                out=mvn_test(root)
                if out.get('ok'):
                    met['post_test_pass_observed'] = True
            elif a == 'final':
                if final_gate == 'hard' and met['successful_edits'] < 1:
                    out={'error':'final rejected: no successful edit has occurred'}; met['rejected_finals'] += 1
                else:
                    final=act; stop=True; break
            else:
                out={'error':'unknown action'}
            outs.append({'action':act,'tool_output':out})
        transcript[-1]['tool_outputs']=outs
        if outs:
            tool_text = json.dumps(outs, ensure_ascii=False)[:14000]
            if outs[-1].get('action', {}).get('action') == 'compile' and outs[-1].get('tool_output', {}).get('ok'):
                tool_text += '\nSYSTEM: compile succeeded. Next turn respond with exactly one final JSON action and no prose.'
            hist += ['AGENT:'+raw, 'TOOL:'+tool_text]
        if stop: break
    met['wall_seconds']=round(time.time()-start,3); met['source_files']=sorted(set(met['source_files']))
    return final, met, transcript


def run_one(broker: JsonBrokerAdapter, arm: str, rep: int, raw_dir: Path, work_dir: Path, final_gate: str, max_turns: int) -> dict[str, Any]:
    root=work_dir/f'CDC_M12__{arm}__r{rep}'
    make_repo(root)
    claim=pre_claim(); fresh=check_freshness(GitRepo(root), claim)
    before=snapshot(root)
    final, met, transcript = agent_loop(broker, arm, root, claim, fresh, final_gate, max_turns)
    post=deterministic_test(root)
    diffs=diff_files(before, root)
    aud=audit(diffs, final, root)
    raw={'task_id':'CDC_M12','arm':arm,'rep':rep,'final_gate':final_gate,'max_turns':max_turns,'stale_claim_present': arm in {'PREREAD_STALE_SOURCE','STALE_DOC_CONTROL','TMF_STALE_GATED'},'stale_claim_fresh': fresh.fresh,'stale_claim_withheld': bool(arm=='TMF_STALE_GATED' and not fresh.fresh),'withheld_claim_id': claim.id if arm=='TMF_STALE_GATED' and not fresh.fresh else None,'freshness':{'fresh':fresh.fresh,'stale_bindings':fresh.stale_bindings},'final':final,'telemetry':met,'post_test':post,'diffs':diffs,'audit':aud,'transcript':transcript}
    raw['failure_classification']=classify_failure(raw); raw['metrics']=metric_view(raw)
    raw_path=raw_dir/f'CDC_M12__{arm}__r{rep}.raw.json'
    raw_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return {k:raw[k] for k in ['task_id','arm','rep','final_gate','max_turns','stale_claim_present','stale_claim_fresh','stale_claim_withheld','withheld_claim_id','freshness','final','telemetry','post_test','audit','failure_classification','metrics']} | {'raw_path':str(raw_path.relative_to(HERE)),'diff_bytes':sum(len(d.encode()) for d in diffs.values())}


def summarize(rows):
    by={}
    for arm in ARMS:
        rs=[r for r in rows if r['arm']==arm]
        by[arm]={'runs':len(rs),'raw_pass':sum(r['metrics']['raw_pass'] for r in rs),'task_result_pass':sum(r['metrics'].get('task_result_pass',False) for r in rs),'post_test_ok':sum(r['metrics'].get('post_test_ok',False) for r in rs),'semantic_evaluable':sum(r['metrics']['semantic_evaluable'] for r in rs),'semantic_adjusted_pass':sum(1 for r in rs if r['metrics']['semantic_pass'] is True),'stale_claim_withheld':sum(1 for r in rs if r.get('stale_claim_withheld')),'uses_legacy_save':sum(1 for r in rs if r.get('post_test',{}).get('placement',{}).get('uses_legacy_save')),'duplicate_edit_suppressed':sum(r.get('failure_classification',{}).get('duplicate_edit_suppressed',0) for r in rs),'extra_actions_ignored':sum(r.get('failure_classification',{}).get('extra_actions_ignored',0) for r in rs),'result_ok_but_raw_failed':sum(1 for r in rs if r.get('failure_classification',{}).get('result_ok_but_raw_failed')),'primary':{}}
        for r in rs:
            p=r['failure_classification'].get('primary','unknown'); by[arm]['primary'][p]=by[arm]['primary'].get(p,0)+1
    return {'mode':TAG,'runs':len(rows),'final_gate':rows[0].get('final_gate') if rows else None,'max_turns':rows[0].get('max_turns') if rows else None,'by_arm':by}


def write_report(out, path: Path):
    lines=['# CDC M12 Projection Stale Workflow Report','', 'Workflow fixture from `benchmarks/java-workflow-fixtures/cdc-search-index-projection-consistency`. The old Phase-A claim says ProductProjectionConsumer applies every event then unconditionally calls saveVersion. The current task requires stale-event guard, tombstone handling, and checkpoint advancement only after successful search-index update using the compare-and-set repository contract. This is an admission smoke candidate: if stale-control arms do not measurably preserve/use the legacy saveVersion workflow, do not scale it as TMF evidence.','', '```json', json.dumps(out['summary'], ensure_ascii=False, indent=2), '```', '', '## Rows']
    for r in out['rows']:
        lines.append(f"- rep {r['rep']} {r['arm']}: raw={r['metrics']['raw_pass']} task_result={r['metrics'].get('task_result_pass')} semantic={r['metrics']['semantic_pass']} post={r['post_test']['ok']} withheld={r.get('stale_claim_withheld')} failure={r['failure_classification']['primary']} placement={json.dumps(r['post_test']['placement'], ensure_ascii=False)} raw_path={r['raw_path']}")
    path.write_text('\n'.join(lines)+'\n', encoding='utf-8')


def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--repeats',type=int,default=1); ap.add_argument('--tag',default=TAG); ap.add_argument('--final-gate',choices=['hard'],default='hard'); ap.add_argument('--max-turns',type=int,default=10); args=ap.parse_args()
    results=HERE/'results'; raw_dir=results/'raw'/args.tag; work_dir=results/'work'/args.tag
    if raw_dir.exists(): shutil.rmtree(raw_dir)
    if work_dir.exists(): shutil.rmtree(work_dir)
    raw_dir.mkdir(parents=True); work_dir.mkdir(parents=True)
    broker=JsonBrokerAdapter(BROKER, expected_model=MODEL, timeout_seconds=TIMEOUT); preflight=broker.preflight().__dict__
    rows=[]
    for rep in range(1,args.repeats+1):
        for arm in ARMS:
            print(f'RUN rep={rep} arm={arm}', flush=True)
            row=run_one(broker,arm,rep,raw_dir,work_dir,args.final_gate,args.max_turns); rows.append(row)
            print(f"DONE rep={rep} arm={arm} raw={row['metrics']['raw_pass']} task={row['metrics']['task_result_pass']} failure={row['failure_classification']['primary']}", flush=True)
            out={'schema':TAG,'model':MODEL,'final_gate':args.final_gate,'max_turns':args.max_turns,'preflight':preflight,'rows':rows,'summary':summarize(rows)}
            (results/f'{args.tag}.json').write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    out={'schema':TAG,'model':MODEL,'final_gate':args.final_gate,'max_turns':args.max_turns,'preflight':preflight,'rows':rows,'summary':summarize(rows)}
    jp=results/f'{args.tag}.json'; rp=results/f'{args.tag.upper()}_REPORT.md'
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2)+'\n', encoding='utf-8'); write_report(out,rp)
    print('WROTE', jp, rp); print(json.dumps(out['summary'], ensure_ascii=False, indent=2))

if __name__ == '__main__':
    main()
