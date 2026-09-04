# R21 protocol rehearsal report — 2026-09-04 09:38 CST

## Scope
One cheap protocol rehearsal pair for R21 long-chain / budget-pressure benchmark:

- SOURCE_ONLY
- TMF_LOCALIZED_REFRESH

Task: add `recordRefreshCompletionHook(key);` on Guava refresh completion/publication side.

## Final verification

Commands:

```bash
cd /root/.openclaw/workspace/repos/guava
git apply --check /root/.openclaw/workspace/worktrees/tmf-java-nodes-step0/experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/runtime/rehearsal-20260904T092311+0800/source_only/patch.diff
git apply --check /root/.openclaw/workspace/worktrees/tmf-java-nodes-step0/experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/runtime/rehearsal-20260904T092311+0800/tmf_localized/patch.diff
cd /root/.openclaw/workspace/worktrees/tmf-java-nodes-step0
python3 experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/oracles/r21_refresh_hook_oracle.py .../LocalCache.patched.final.java
```

Result JSON: `experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/runtime/rehearsal-20260904T092311+0800/EVAL.final.json`

```json
{
  "schema": "r21-rehearsal-final-eval-v2",
  "base": "experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/runtime/rehearsal-20260904T092311+0800",
  "rows": [
    {
      "arm": "source_only",
      "final_patch_apply_ok": true,
      "final_oracle_ok": true,
      "overall": "pass_completion_listener_after_publication",
      "hook_count": 1,
      "raw_protocol_issue_before_parent_fix": false,
      "semantic_placement": "pass",
      "patch_lines": 12
    },
    {
      "arm": "tmf_localized",
      "final_patch_apply_ok": true,
      "final_oracle_ok": true,
      "overall": "pass_completion_listener_after_publication",
      "hook_count": 1,
      "raw_protocol_issue_before_parent_fix": true,
      "semantic_placement": "pass",
      "patch_lines": 12
    }
  ],
  "summary": "Both arms converged to same correct completion-path placement; raw run exposed patch protocol failures, including TMF patchfix self-report mismatch before parent correction. No TMF superiority claim from this rehearsal."
}
```

## Interpretation

- Both arms selected the same semantically correct placement: inside `loadAsync(...)` listener, immediately after `getAndRecordStats(...)`.
- Final corrected patches apply cleanly and pass the oracle.
- Raw rehearsal still surfaced important protocol issues:
  - initial SOURCE_ONLY patch had invalid unified diff format;
  - initial TMF patch had an inapplicable hunk;
  - TMF patchfix self-reported apply success, but parent verification found it still failed. Parent corrected the patch format while preserving the same semantic placement.
- Therefore this rehearsal is useful as protocol hardening, not evidence of TMF superiority.

## Next step

Tighten R21 harness so agents must verify `git apply --check` against the exact baseline and persist the command output. Then rerun one clean pair. Only after protocol-clean pair(s) should we scale to repetitions or compare reread burden.
