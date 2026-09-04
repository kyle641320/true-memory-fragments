# R21 clean rehearsal report — 2026-09-04

```json
{
  "schema": "r21-clean-rehearsal-eval-v2",
  "base": "experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/runtime/clean-rehearsal-20260904T093842+0800",
  "rows": [
    {
      "arm": "source_only",
      "required_files_present": true,
      "verify_log_exit0": true,
      "independent_apply_ok": true,
      "oracle_ok": true,
      "oracle_overall": "pass_completion_listener_after_publication",
      "hook_count": 1,
      "metrics_json_valid": true,
      "metrics": {
        "raw_status": "ok",
        "protocol_clean": true,
        "semantic_status": "pass",
        "failure_attribution": "none",
        "changed_files": [
          "patch.diff",
          "NOTE.md",
          "VERIFY.sh",
          "VERIFY.log"
        ],
        "reread_files": [
          "/root/.openclaw/workspace/repos/guava/guava/src/com/google/common/cache/LocalCache.java"
        ],
        "reread_lines": 162,
        "tool_calls": 8,
        "budget_exhausted": false,
        "placement_summary": "Hook placed after storeLoadedValue(...) in getAndRecordStats(...), the listener-driven refresh completion/publication path; not after loadAsync(...) in refresh(...).",
        "citations": [
          "/root/.openclaw/workspace/repos/guava/guava/src/com/google/common/cache/LocalCache.java:2314-2327",
          "/root/.openclaw/workspace/repos/guava/guava/src/com/google/common/cache/LocalCache.java:2335-2350",
          "/root/.openclaw/workspace/repos/guava/guava/src/com/google/common/cache/LocalCache.java:2385-2395",
          "/root/.openclaw/workspace/repos/guava/guava/src/com/google/common/cache/LocalCache.java:3148-3235"
        ]
      }
    },
    {
      "arm": "tmf_localized",
      "required_files_present": true,
      "verify_log_exit0": true,
      "independent_apply_ok": true,
      "oracle_ok": true,
      "oracle_overall": "pass_completion_listener_after_publication",
      "hook_count": 1,
      "metrics_json_valid": true,
      "metrics": {
        "raw_status": "ok",
        "protocol_clean": true,
        "semantic_status": "pass",
        "failure_attribution": "none",
        "changed_files": [
          "patch.diff",
          "NOTE.md",
          "VERIFY.sh",
          "VERIFY.log"
        ],
        "reread_files": [
          "/root/.openclaw/workspace/worktrees/tmf-java-nodes-step0/experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/runtime/rehearsal-20260904T092311+0800/source_only/TASK.md",
          "/root/.openclaw/workspace/worktrees/tmf-java-nodes-step0/experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/runtime/rehearsal-20260904T092311+0800/source_only/TASK_BASE.md",
          "/root/.openclaw/workspace/worktrees/tmf-java-nodes-step0/experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/runtime/rehearsal-20260904T092311+0800/tmf_localized/NOTE.md",
          "/root/.openclaw/workspace/worktrees/tmf-java-nodes-step0/experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/runtime/rehearsal-20260904T092311+0800/tmf_localized/patch.diff",
          "/root/.openclaw/workspace/repos/guava/guava/src/com/google/common/cache/LocalCache.java"
        ],
        "reread_lines": 178,
        "tool_calls": 8,
        "budget_exhausted": false,
        "placement_summary": "Hook placed in the async completion/publication path, immediately after getAndRecordStats(...) inside the loadAsync listener, so it fires after refresh completion and value publication.",
        "citations": [
          "guava/src/com/google/common/cache/LocalCache.java:2314-2330",
          "guava/src/com/google/common/cache/LocalCache.java:2333-2349"
        ]
      }
    }
  ],
  "summary": "Both arms produced required protocol files, VERIFY.log records exit 0, independent git apply check passed, and oracle passed. SOURCE_ONLY NOTE has valid METRICS_JSON. TMF_LOCALIZED NOTE has malformed METRICS_JSON label/object syntax, so protocol is apply/oracle clean but metrics parsing still needs hardening. No TMF superiority claim because SOURCE_ONLY also passed."
}
```

Interpretation: harness hardening fixed the major patch-apply verification issue: both arms have real VERIFY.log exit 0 and independently pass git apply + oracle. Remaining protocol issue: TMF_LOCALIZED NOTE emitted malformed METRICS_JSON, so evaluator must enforce strict metrics JSON before scaling. No TMF superiority claim from this pair.
