# R21 long-chain / budget-pressure benchmark spec

Status: deterministic artifact, no model benchmark run.

## Purpose

R21 stops using short SOURCE_ONLY-vs-TMF smoke as the main proof. It targets TMF's main value case: a long-chain code maintenance task where an old note about a local entry point is stale, the real boundary moved several hops away, and a budget-limited agent must decide what to reread.

## Real chain under test

Repository baseline: `/root/.openclaw/workspace/repos/guava`.

Refresh chain:

1. A: `guava/src/com/google/common/cache/CacheBuilder.java`
   - `refreshAfterWrite(...)` documents that refresh uses `CacheLoader.reload` and may be asynchronous.
2. B: `guava/src/com/google/common/cache/LocalCache.java`
   - `Segment.refresh(...)` initiates refresh with `loadAsync(...)` and may return before completion.
3. C: `LocalCache.Segment.loadAsync(...)`
   - registers a `loadingFuture.addListener(...)` completion callback.
4. D: `LocalCache.Segment.getAndRecordStats(...)`
   - waits for the future and publishes the loaded value with `storeLoadedValue(...)`.
5. E: `LocalCache.LoadingValueReference.loadFuture(...)`
   - calls `CacheLoader.reload(...)` for refresh and transforms the returned future so `futureValue` is set before returning the new value.
6. F: `guava/src/com/google/common/cache/CacheLoader.java`
   - `reload(...)` default is synchronous but async reload is recommended/available.
7. G: `guava-tests/test/com/google/common/cache/CacheRefreshTest.java`
   - existing test host for refresh behavior.

## Stale-note trap

Old/stale note supplied to the agent:

> Refresh completion happens when `LocalCache.Segment.refresh(...)` returns from `loadAsync(...)`; adding a hook immediately after `loadAsync(...)` observes completed refreshes.

Current truth:

- `refresh(...)` starts refresh and returns `null` for asynchronous reloads.
- Completion/publication happens after the returned future completes, inside the `loadAsync(...)` listener around `getAndRecordStats(...)` and then `storeLoadedValue(...)`.
- `LoadingValueReference.loadFuture(...)` may transform an async `CacheLoader.reload(...)` future; the refresh boundary is not visible from A/B alone.

## Agent task

Add a call to `recordRefreshCompletionHook(key);` that fires only after refresh completion/publication, not after refresh initiation.

Required output protocol for model runs, if later executed:

```json
{
  "raw_status": "ok|timeout|tool_error|invalid_output",
  "protocol_clean": true,
  "semantic_status": "pass|fail|unclear",
  "failure_attribution": "none|raw_transport|protocol|agent_semantic|tmf_locator|tmf_stale_refresh|oracle_ambiguous",
  "changed_files": [],
  "reread_files": [],
  "reread_lines": 0,
  "tool_calls": 0,
  "budget_exhausted": false,
  "notes": "..."
}
```

## Budget-pressure setup

Recommended prompt budget limit for later model run:

- Max 4 source files reread, max 220 source lines, max 8 tool calls.
- SOURCE_ONLY receives the stale note plus entry-point hints A/B/G. It must choose what to inspect.
- TMF_LOCALIZED_REFRESH receives the stale note plus a compact TMF locator map pointing to the stale boundary claim and fresh anchors C/D/E/F. It should reread only localized completion boundary slices.

Expected value signal is not "TMF got a short question right". It is:

- fewer wrong hook placements under budget pressure;
- lower reread cost for reaching C/D/E/F boundary;
- explicit separation of raw/protocol failures from semantic agent/TMF failures.

## Mechanical oracle

`r21_long_chain_budget/oracles/r21_refresh_hook_oracle.py` classifies a patched `LocalCache.java` as:

- `pass_completion_listener_after_publication`: hook appears after `getAndRecordStats(...)` inside the `loadingFuture.addListener(...)` callback or inside `getAndRecordStats(...)` after `storeLoadedValue(...)`.
- `fail_initiation_path`: hook appears in `refresh(...)` after `loadAsync(...)`.
- `fail_before_publication`: hook appears before the async transform sets the value / before publication.
- `ambiguous_or_missing`: no hook or insufficient structural anchors.

This is a deterministic preflight/oracle artifact only; it intentionally does not run expensive model benchmarks.
