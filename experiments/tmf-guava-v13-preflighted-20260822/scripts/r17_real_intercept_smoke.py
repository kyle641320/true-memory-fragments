#!/usr/bin/env python3
from __future__ import annotations
import hashlib, json, os, re, shutil, subprocess, time
from pathlib import Path

EXP = Path('/root/.openclaw/workspace/experiments/tmf-guava-v13-preflighted-20260822')
BASE = Path('/root/.openclaw/workspace/worktrees/guava')
RUN = EXP / 'runtime' / ('run-r17-real-intercept-' + time.strftime('%Y%m%dT%H%M%S'))
TARGET = Path('guava/src/com/google/common/collect/CompactHashing.java')


def sh(cmd, cwd=None, check=True):
    p = subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and p.returncode != 0:
        raise RuntimeError(f'cmd failed {cmd}:\nSTDOUT={p.stdout}\nSTDERR={p.stderr}')
    return p


def copy_repo(dst: Path):
    if dst.exists(): shutil.rmtree(dst)
    shutil.copytree(BASE, dst, symlinks=True, ignore=shutil.ignore_patterns('.git/index.lock','.tmf','target'))


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
    if 'return ((mask < 64) ? 4 : 2) * (mask + 1);' not in s:
        raise RuntimeError('expected current base threshold <64 not found')
    p.write_text(s.replace('return ((mask < 64) ? 4 : 2) * (mask + 1);','return ((mask < 128) ? 4 : 2) * (mask + 1);',1))


def insert_helper(repo: Path, body: str):
    p = repo / TARGET
    s = p.read_text()
    anchor = '''  static int newCapacity(int mask) {\n    return ((mask < 128) ? 4 : 2) * (mask + 1);\n  }\n'''
    if anchor not in s:
        raise RuntimeError('fresh newCapacity anchor not found; refusing to patch')
    if 'resizedBucketCountForUi' in s:
        raise RuntimeError('helper already present')
    p.write_text(s.replace(anchor, anchor + '\n' + body + '\n', 1))


def hidden_score(repo: Path):
    s = (repo / TARGET).read_text()
    ok_preserved = 'return ((mask < 128) ? 4 : 2) * (mask + 1);' in s
    stale_inline = '((mask < 64) ? 4 : 2)' in s
    delegates = 'return newCapacity(currentMask);' in s
    has_helper = 'resizedBucketCountForUi(int currentMask)' in s
    # semantic hidden oracle for currentMask=127: fresh newCapacity=>512; stale <64 formula=>256.
    pass_hidden = ok_preserved and has_helper and delegates and not stale_inline
    return {'has_helper': has_helper, 'fresh_drift_preserved': ok_preserved, 'delegates_to_current_boundary': delegates, 'contains_stale_inline_64': stale_inline, 'hidden_currentMask_127_pass': pass_hidden}


class Interceptor:
    def __init__(self, repo: Path, stale_claim: dict):
        self.repo = repo
        self.stale_claim = stale_claim
        self.reread_ok = False
        self.events = []
    def current_hash(self):
        _, _, span = fn_span((self.repo/TARGET).read_text())
        return sha(span)
    def guarded_apply(self, action_name: str, patch_body: str, apply_func):
        current = self.current_hash()
        if current != self.stale_claim['phase_a_fn_sha256'] and not self.reread_ok:
            ev = {'event':'TMF_REFLEX_BLOCK','action':action_name,'target':str(TARGET),'boundary':'CompactHashing.newCapacity(int mask)','phase_a_sha256':self.stale_claim['phase_a_fn_sha256'],'current_sha256':current,'reason':'stale boundary touched before reread'}
            self.events.append(ev)
            return {'applied': False, 'blocked': True, 'event': ev}
        apply_func()
        self.events.append({'event':'APPLY_ALLOWED','action':action_name,'reread_ok':self.reread_ok})
        return {'applied': True, 'blocked': False}
    def reread_boundary(self):
        _, _, span = fn_span((self.repo/TARGET).read_text())
        self.reread_ok = True
        ev = {'event':'BOUNDARY_REREAD','boundary':'CompactHashing.newCapacity(int mask)','current_span':span,'current_sha256':sha(span)}
        self.events.append(ev)
        return ev


def main():
    RUN.mkdir(parents=True, exist_ok=False)
    reports = EXP / 'reports'
    reports.mkdir(exist_ok=True)
    # setup repos
    control = RUN / 'control_repo'; treatment = RUN / 'treatment_repo'
    copy_repo(control); copy_repo(treatment)
    # phase A before drift
    base_text = (control/TARGET).read_text()
    _, _, phase_a_span = fn_span(base_text)
    phase_a_claim = {'path': str(TARGET), 'qualname':'CompactHashing.newCapacity(int mask)', 'phase_a_fn_sha256': sha(phase_a_span), 'phase_a_span': phase_a_span}
    # drift after phase A
    mutate(control); mutate(treatment)
    # stale action would inline old threshold; fresh recovery delegates to current boundary
    stale_helper = '''  @VisibleForTesting\n  static int resizedBucketCountForUi(int currentMask) {\n    checkArgument(currentMask >= 0, "currentMask must be nonnegative");\n    return ((currentMask < 64) ? 4 : 2) * (currentMask + 1);\n  }\n'''
    fresh_helper = '''  @VisibleForTesting\n  static int resizedBucketCountForUi(int currentMask) {\n    checkArgument(currentMask >= 0, "currentMask must be nonnegative");\n    return newCapacity(currentMask);\n  }\n'''
    # control: no interception, stale patch lands
    insert_helper(control, stale_helper)
    control_score = hidden_score(control)
    # treatment: stale patch is blocked, reread, fresh patch lands
    it = Interceptor(treatment, phase_a_claim)
    first = it.guarded_apply('apply_stale_helper_patch', stale_helper, lambda: insert_helper(treatment, stale_helper))
    reread = it.reread_boundary()
    second = it.guarded_apply('apply_fresh_helper_patch_after_reread', fresh_helper, lambda: insert_helper(treatment, fresh_helper))
    treatment_score = hidden_score(treatment)
    # light gates
    diff_check_control = sh(['git','diff','--check'], cwd=control, check=False)
    diff_check_treatment = sh(['git','diff','--check'], cwd=treatment, check=False)
    result = {
        'schema':'r17-real-intercept-smoke-v1',
        'run_dir': str(RUN),
        'base_repo': str(BASE),
        'target': str(TARGET),
        'phase_a_claim': phase_a_claim,
        'latent_drift': 'CompactHashing.newCapacity threshold mask < 64 -> mask < 128',
        'control': {'intercept_enabled': False, 'score': control_score, 'git_diff_check_rc': diff_check_control.returncode},
        'treatment': {'intercept_enabled': True, 'first_attempt': first, 'reread': reread, 'second_attempt': second, 'events': it.events, 'score': treatment_score, 'git_diff_check_rc': diff_check_treatment.returncode},
        'smoke_pass': bool(first.get('blocked') and second.get('applied') and (not control_score['hidden_currentMask_127_pass']) and treatment_score['hidden_currentMask_127_pass'] and diff_check_treatment.returncode == 0),
        'limitations': [
            'Zero-model smoke only: deterministic patch actions stand in for model edit attempts.',
            'Runner-level guarded patch protocol is real action-time interception, but not yet OpenClaw PreToolUse integration.',
            'Next model pilot must force patch proposal through this guarded runner; direct file-edit tools would invalidate causal interpretation.'
        ]
    }
    (RUN/'R17_SMOKE_RESULT.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
    report = f'''# r17 real/action-time interception smoke

## Verdict

{'PASS' if result['smoke_pass'] else 'FAIL'} for zero-model runner-level interception smoke.

This does **not** prove TMF product value yet. It proves the next evaluation can avoid r16's invalid prompt-simulated reflex by enforcing a real action-time block before a stale-dependent patch lands.

## Setup

- Run dir: `{RUN}`
- Target boundary: `CompactHashing.newCapacity(int mask)`
- Phase A belief hash: `{phase_a_claim['phase_a_fn_sha256']}`
- Parent drift after Phase A: `mask < 64` → `mask < 128`

## Observed behavior

- Control had no interception. Stale helper patch landed and hidden scorer failed for currentMask=127.
- Treatment first attempted the same stale helper patch.
- Runner emitted `TMF_REFLEX_BLOCK` because the action touched a stale boundary and no current reread had happened.
- After explicit boundary reread, the fresh helper patch was allowed and hidden scorer passed.

## Scores

```json
{json.dumps({'control': control_score, 'treatment': treatment_score, 'smoke_pass': result['smoke_pass']}, ensure_ascii=False, indent=2)}
```

## Next pilot requirements

A model pilot is valid only if:

1. The model is not told the stale boundary upfront.
2. The model outputs an intended patch/action to a runner-controlled file, not direct uncontrolled source edits.
3. The runner applies or blocks that action using the same stale-boundary hash check.
4. All per-arm artifacts are isolated.
5. Hidden scorer verifies current drift preservation, not only compile success.

If the model can edit source directly, r17 becomes invalid like r16 because the reflex is not actually enforced.
'''
    (RUN/'R17_SMOKE_REPORT.md').write_text(report)
    (reports/'R17_REAL_INTERCEPT_SMOKE_LATEST.md').write_text(report)
    print(json.dumps({'run_dir': str(RUN), 'smoke_pass': result['smoke_pass'], 'report': str(RUN/'R17_SMOKE_REPORT.md')}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result['smoke_pass'] else 2)

if __name__ == '__main__': main()
