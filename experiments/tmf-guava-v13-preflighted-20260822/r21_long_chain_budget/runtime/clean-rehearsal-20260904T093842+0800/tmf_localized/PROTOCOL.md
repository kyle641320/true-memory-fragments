# R21 rehearsal protocol hardening v1

Every R21 rehearsal arm must produce these files in its arm directory:

- `patch.diff` — unified diff for `guava/src/com/google/common/cache/LocalCache.java`.
- `NOTE.md` — short explanation plus one machine-readable `METRICS_JSON:` line.
- `VERIFY.sh` — a shell script that verifies the patch against the exact baseline.
- `VERIFY.log` — captured output from running `VERIFY.sh`.

Protocol-clean requirements:

1. `patch.diff` must pass from the exact baseline repo:

   ```bash
   cd /root/.openclaw/workspace/repos/guava
   git apply --check /ABS/PATH/TO/ARM/patch.diff
   ```

2. `VERIFY.sh` must be executable or runnable with `bash VERIFY.sh` and must not modify the source tree. It should run only `git apply --check` against `/root/.openclaw/workspace/repos/guava`.

3. `VERIFY.log` must contain the actual verification command and exit code. Success is exit code `0`. Failure must be reported honestly.

4. `NOTE.md` may set `protocol_clean:true` only if `VERIFY.log` records exit code `0`.

5. Parent/evaluator must ignore self-reported `protocol_clean` if `VERIFY.log` is missing, malformed, or contradicts independent verification.

Recommended `METRICS_JSON` fields:

```json
{
  "raw_status": "ok|failed",
  "protocol_clean": true,
  "semantic_status": "pass|fail|unknown",
  "failure_attribution": "none|protocol_patch_apply_failed|agent_self_report_mismatch|semantic_boundary_error|budget_exhausted|other",
  "changed_files": ["patch.diff", "NOTE.md", "VERIFY.sh", "VERIFY.log"],
  "reread_files": [],
  "reread_lines": 0,
  "tool_calls": 0,
  "budget_exhausted": false,
  "placement_summary": "..."
}
```
