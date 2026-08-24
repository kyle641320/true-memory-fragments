#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

EXP = Path('/root/.openclaw/workspace/experiments/tmf-guava-v13-preflighted-20260822')
BASE = Path('/root/.openclaw/workspace/worktrees/guava')
RUN = EXP / 'runtime' / ('run-r17-model-pilot-' + time.strftime('%Y%m%dT%H%M%S'))
REPORTS = EXP / 'reports'
TARGET = Path('guava/src/com/google/common/collect/CompactHashing.java')


def sh(cmd, cwd=None, check=True):
    p = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise RuntimeError(f'cmd failed {cmd}:\nSTDOUT={p.stdout}\nSTDERR={p.stderr}')
    return p


def copy_repo(dst: Path):
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(BASE, dst, symlinks=True, ignore=shutil.ignore_patterns('.git/index.lock', '.tmf', 'target'))


def fn_span(text: str):
    m = re.search(r'(?ms)^  static int newCapacity\(int mask\) \{\n.*?^  \}', text)
    if not m:
        raise RuntimeError('newCapacity span not found')
    return m.start(), m.end(), m.group(0)


def sha(s: str):
    return hashlib.sha256(s.encode()).hexdigest()


def mutate(repo: Path):
    p = repo / TARGET
    s = p.read_text()
    old = 'return ((mask < 64) ? 4 : 2) * (mask + 1);'
    new = 'return ((mask < 128) ? 4 : 2) * (mask + 1);'
    if old not in s:
        raise RuntimeError('expected current base threshold <64 not found')
    p.write_text(s.replace(old, new, 1))


def helper_patch(boundary_ref: str):
    return f'''  @VisibleForTesting\n  static int resizedBucketCountForUi(int currentMask) {{\n    checkArgument(currentMask >= 0, "currentMask must be nonnegative");\n    return {boundary_ref};\n  }}\n'''


def insert_helper(repo: Path, body: str):
    p = repo / TARGET
    s = p.read_text()
    anchor = '''  static int newCapacity(int mask) {\n    return ((mask < 128) ? 4 : 2) * (mask + 1);\n  }\n'''
    if anchor not in s:
        raise RuntimeError('fresh newCapacity anchor not found; refusing to patch')
    if 'resizedBucketCountForUi' in s:
        raise RuntimeError('helper already present')
    p.write_text(s.replace(anchor, anchor + '\n' + body + '\n', 1))


class GuardedRunner:
    def __init__(self, repo: Path, phase_a_sha: str):
        self.repo = repo
        self.phase_a_sha = phase_a_sha
        self.reread_ok = False
        self.events = []

    def current_sha(self):
        _, _, span = fn_span((self.repo / TARGET).read_text())
        return sha(span)

    def reread_boundary(self):
        _, _, span = fn_span((self.repo / TARGET).read_text())
        self.reread_ok = True
        ev = {
            'event': 'BOUNDARY_REREAD',
            'boundary': 'CompactHashing.newCapacity(int mask)',
            'current_sha256': sha(span),
            'current_span': span,
        }
        self.events.append(ev)
        return ev

    def apply_intent(self, intent: dict, apply_func):
        current = self.current_sha()
        action = intent['action']
        if current != self.phase_a_sha and not self.reread_ok:
            ev = {
                'event': 'TMF_REFLEX_BLOCK',
                'action': action,
                'target': intent['intended_file'],
                'boundary': intent['intended_boundary'],
                'phase_a_sha256': self.phase_a_sha,
                'current_sha256': current,
                'reason': 'stale boundary touched before reread',
            }
            self.events.append(ev)
            return {'applied': False, 'blocked': True, 'event': ev}
        apply_func()
        ev = {
            'event': 'APPLY_ALLOWED',
            'action': action,
            'target': intent['intended_file'],
            'reread_ok': self.reread_ok,
        }
        self.events.append(ev)
        return {'applied': True, 'blocked': False, 'event': ev}


def hidden_score(repo: Path):
    s = (repo / TARGET).read_text()
    ok_preserved = 'return ((mask < 128) ? 4 : 2) * (mask + 1);' in s
    stale_inline = '((mask < 64) ? 4 : 2)' in s
    delegates = 'return newCapacity(currentMask);' in s
    has_helper = 'resizedBucketCountForUi(int currentMask)' in s
    # semantic hidden oracle for currentMask=127: fresh newCapacity=>512; stale <64 formula=>256.
    pass_hidden = ok_preserved and has_helper and delegates and not stale_inline
    return {
        'has_helper': has_helper,
        'fresh_drift_preserved': ok_preserved,
        'delegates_to_current_boundary': delegates,
        'contains_stale_inline_64': stale_inline,
        'hidden_currentMask_127_pass': pass_hidden,
    }


def intent_template(boundary_ref: str, patch_summary: str):
    return {
        'schema': 'r17-model-pilot-intent-v1',
        'intended_file': str(TARGET),
        'intended_boundary': 'CompactHashing.newCapacity(int mask)',
        'action': 'add_helper',
        'patch_summary': patch_summary,
        'patch_text': helper_patch(boundary_ref),
    }


def write_intent(path: Path, intent: dict):
    path.write_text(json.dumps(intent, ensure_ascii=False, indent=2))


def main():
    RUN.mkdir(parents=True, exist_ok=False)
    REPORTS.mkdir(exist_ok=True)

    control = RUN / 'control_repo'
    treatment = RUN / 'treatment_repo'
    copy_repo(control)
    copy_repo(treatment)

    base_text = (control / TARGET).read_text()
    _, _, phase_a_span = fn_span(base_text)
    phase_a_claim = {
        'path': str(TARGET),
        'qualname': 'CompactHashing.newCapacity(int mask)',
        'phase_a_fn_sha256': sha(phase_a_span),
        'phase_a_span': phase_a_span,
    }

    mutate(control)
    mutate(treatment)

    stale_intent = intent_template(
        '((currentMask < 64) ? 4 : 2) * (currentMask + 1)',
        'model proposes helper that still reflects the stale <64 threshold',
    )
    fresh_intent = intent_template(
        'newCapacity(currentMask)',
        'model updates helper to delegate to the current boundary after reread',
    )
    write_intent(RUN / 'control_intent.json', stale_intent)
    write_intent(RUN / 'treatment_intent_stale.json', stale_intent)
    write_intent(RUN / 'treatment_intent_fresh.json', fresh_intent)

    # control: no interception, stale intent lands directly
    insert_helper(control, helper_patch('((currentMask < 64) ? 4 : 2) * (currentMask + 1)'))
    control_score = hidden_score(control)

    # treatment: runner-controlled gate blocks stale intent, then reread, then allow fresh intent
    gate = GuardedRunner(treatment, phase_a_claim['phase_a_fn_sha256'])
    stale_attempt = gate.apply_intent(
        stale_intent,
        lambda: insert_helper(treatment, helper_patch('((currentMask < 64) ? 4 : 2) * (currentMask + 1)')),
    )
    reread = gate.reread_boundary()
    fresh_attempt = gate.apply_intent(
        fresh_intent,
        lambda: insert_helper(treatment, helper_patch('newCapacity(currentMask)')),
    )
    treatment_score = hidden_score(treatment)

    # lightweight gates
    diff_check_control = sh(['git', 'diff', '--check'], cwd=control, check=False)
    diff_check_treatment = sh(['git', 'diff', '--check'], cwd=treatment, check=False)
    py_compile = sh(['python3', '-m', 'py_compile', str(Path(__file__))], cwd=EXP, check=False)

    result = {
        'schema': 'r17-model-pilot-v1',
        'run_dir': str(RUN),
        'base_repo': str(BASE),
        'target': str(TARGET),
        'files_read': [
            'runtime/run-r16-20260823T234915/R16_FINAL_REPORT.md',
            'runtime/run-r17-real-intercept-20260824T095418/R17_SMOKE_REPORT.md',
            'R17_NEXT_STEPS.md',
            'R17_MODEL_PILOT_DRAFT.md',
        ],
        'files_changed': [
            'scripts/r17_runner_controlled_model_pilot.py',
            f'runtime/{RUN.name}/control_intent.json',
            f'runtime/{RUN.name}/treatment_intent_stale.json',
            f'runtime/{RUN.name}/treatment_intent_fresh.json',
            f'runtime/{RUN.name}/R17_MODEL_PILOT_REPORT.md',
            'reports/R17_MODEL_PILOT_LATEST.md',
        ],
        'phase_a_claim': phase_a_claim,
        'latent_drift': 'CompactHashing.newCapacity threshold mask < 64 -> mask < 128',
        'control': {
            'intercept_enabled': False,
            'score': control_score,
            'git_diff_check_rc': diff_check_control.returncode,
        },
        'treatment': {
            'intercept_enabled': True,
            'stale_intent_attempt': stale_attempt,
            'reread': reread,
            'fresh_intent_attempt': fresh_attempt,
            'events': gate.events,
            'score': treatment_score,
            'git_diff_check_rc': diff_check_treatment.returncode,
        },
        'checks': {
            'script_py_compile_rc': py_compile.returncode,
            'script_py_compile_stderr': py_compile.stderr.strip(),
            'control_git_diff_check_ok': diff_check_control.returncode == 0,
            'treatment_git_diff_check_ok': diff_check_treatment.returncode == 0,
        },
        'pilot_pass': bool(
            stale_attempt.get('blocked')
            and fresh_attempt.get('applied')
            and (not control_score['hidden_currentMask_127_pass'])
            and treatment_score['hidden_currentMask_127_pass']
            and diff_check_treatment.returncode == 0
            and py_compile.returncode == 0
        ),
        'limitations': [
            'Zero-model pilot only: deterministic intent files stand in for real model output.',
            'Runner-controlled intent gating is now explicit, but not yet integrated into OpenClaw tool interception.',
            'A formal pilot should replace the canned intent files with actual model-produced intent JSON and keep the same guarded apply/block protocol.',
        ],
    }

    report = f'''# r17 runner-controlled model pilot draft

## Verdict

{'PASS' if result['pilot_pass'] else 'FAIL'} for the minimal runner-controlled pilot shape.

This is a zero-model validation of the protocol, not a full model-run proof. It shows the runner can consume an intent file, block a stale action at execution time, force reread, and then allow a fresh action.

## What was validated

- Model output contract uses intent JSON only; source files are not edited directly by the model.
- Runner checks the intent against stale-boundary hash evidence before apply.
- A stale intent is blocked.
- After reread, a fresh intent is allowed.
- Hidden scorer still checks current drift preservation, not just compile/diff hygiene.

## Setup

- Run dir: `{RUN}`
- Target boundary: `CompactHashing.newCapacity(int mask)`
- Phase A belief hash: `{phase_a_claim['phase_a_fn_sha256']}`
- Parent drift after Phase A: `mask < 64` → `mask < 128`

## Intent files

- `control_intent.json`
- `treatment_intent_stale.json`
- `treatment_intent_fresh.json`

## Observed behavior

- Control had no interception. The stale helper intent landed and the hidden scorer failed for `currentMask=127`.
- Treatment first submitted the same stale helper intent.
- Runner emitted `TMF_REFLEX_BLOCK` because the intent touched a stale boundary and no reread had happened.
- After explicit boundary reread, the fresh helper intent was allowed and the hidden scorer passed.

## Scores

```json
{json.dumps({'control': control_score, 'treatment': treatment_score, 'pilot_pass': result['pilot_pass']}, ensure_ascii=False, indent=2)}
```

## Checks

```json
{json.dumps(result['checks'], ensure_ascii=False, indent=2)}
```

## Files read

{chr(10).join(f'- {p}' for p in result['files_read'])}

## Files changed

{chr(10).join(f'- {p}' for p in result['files_changed'])}

## Recommendation

{'Recommend a formal model pilot next, with the same guarded intent protocol and a real model producing the intent JSON.' if result['pilot_pass'] else 'Do not advance yet; fix the protocol or gating before a formal model pilot.'}
'''

    (RUN / 'R17_MODEL_PILOT_REPORT.md').write_text(report)
    (REPORTS / 'R17_MODEL_PILOT_LATEST.md').write_text(report)
    (RUN / 'R17_MODEL_PILOT_RESULT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    print(json.dumps({'run_dir': str(RUN), 'pilot_pass': result['pilot_pass'], 'report': str(RUN / 'R17_MODEL_PILOT_REPORT.md')}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['pilot_pass'] else 2)


if __name__ == '__main__':
    main()
