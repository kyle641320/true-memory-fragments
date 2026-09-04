# R21 task card — refresh completion hook under stale-note budget pressure

You are editing Guava cache refresh behavior.

Old note, known possibly stale:

> Refresh completion happens when `LocalCache.Segment.refresh(...)` returns from `loadAsync(...)`; adding a hook immediately after `loadAsync(...)` observes completed refreshes.

Task:

Add `recordRefreshCompletionHook(key);` so it fires only after a refresh has completed and the refreshed value has been published/recorded. Do not fire it merely when refresh starts.

Budget constraints for benchmark execution:

- max 4 source files reread;
- max 220 source lines reread;
- max 8 tool calls;
- cite the exact line ranges used for the final placement decision.

Required answer packet:

```json
{
  "raw_status": "ok|timeout|tool_error|invalid_output",
  "protocol_clean": true,
  "semantic_status": "pass|fail|unclear",
  "failure_attribution": "none|raw_transport|protocol|agent_semantic|tmf_locator|tmf_stale_refresh|oracle_ambiguous",
  "changed_files": ["..."],
  "reread_files": ["..."],
  "reread_lines": 0,
  "tool_calls": 0,
  "budget_exhausted": false,
  "placement_summary": "...",
  "citations": ["path:start-end"]
}
```

Success oracle:

- pass if hook is in the async completion/publication path, after `getAndRecordStats(...)` listener publication or after `storeLoadedValue(...)` inside `getAndRecordStats(...)`;
- fail if hook is placed after `loadAsync(...)` in `refresh(...)` or before `LoadingValueReference.this.set(newResult)` in the async reload transform.
