# R21 long-chain / budget-pressure TMF artifact report — 2026-09-04 09:06:27 +0800

## What was built

Built a small deterministic R21 benchmark artifact for the Guava cache refresh chain. This moves away from short SOURCE_ONLY-vs-TMF smoke as primary proof and toward TMF's intended long-chain scenario: stale dependency, multiple modules/files, localized refresh advantage, budget pressure, and explicit failure attribution.

Created files:

- `experiments/tmf-guava-v13-preflighted-20260822/R21_LONG_CHAIN_BUDGET_PRESSURE_SPEC.md`
  - benchmark design and protocol;
  - real chain A-G across `CacheBuilder`, `LocalCache`, `LoadingValueReference`, `CacheLoader`, and `CacheRefreshTest`;
  - stale-note trap and budget-pressure framing;
  - raw/protocol-clean/semantic failure attribution schema.
- `experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/tasks/R21_REFRESH_COMPLETION_TASK.md`
  - concrete agent task card requiring `recordRefreshCompletionHook(key);` to fire after refresh completion/publication, not initiation.
- `experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/tasks/R21_TMF_LOCALIZED_REFRESH_LOCATOR.json`
  - compact TMF-style localized refresh map: stale claim plus fresh anchors/slices for C/D/E/F boundary reread.
- `experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/oracles/r21_refresh_hook_oracle.py`
  - deterministic source-position oracle for patched `LocalCache.java`.
- `experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/oracles/r21_oracle_preflight.py`
  - preflight harness that creates temporary good/bad patched `LocalCache.java` cases from `/root/.openclaw/workspace/repos/guava` and verifies oracle classification.
- `experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/reports/r21_oracle_preflight.json`
  - latest deterministic preflight output.
- this report file.

No TMF engine code under `tmf/` was modified.

## Why this targets long-chain TMF value

The benchmark centers on a real multi-hop Guava behavior boundary:

1. `CacheBuilder.refreshAfterWrite(...)` advertises refresh semantics.
2. `LocalCache.Segment.refresh(...)` starts refresh via `loadAsync(...)` and may return before completion.
3. `LocalCache.Segment.loadAsync(...)` registers `loadingFuture.addListener(...)`.
4. `LocalCache.Segment.getAndRecordStats(...)` waits for the future and calls `storeLoadedValue(...)`.
5. `LocalCache.LoadingValueReference.loadFuture(...)` calls `CacheLoader.reload(...)` and transforms async futures so `futureValue` is set.
6. `CacheLoader.reload(...)` may be synchronous by default but async reload is recommended/available.
7. `CacheRefreshTest.java` is the existing behavior-test host.

The stale trap is deliberately plausible but wrong: “refresh completion happens after `refresh(...)` returns from `loadAsync(...)`.” A budget-limited source-only agent can easily place a hook immediately after `loadAsync(...)`; a TMF-localized refresh map should steer reread to the C/D/E/F completion boundary and avoid rereading unrelated code.

This is closer to product ROI than previous small stale-note Q&A smoke because the measured win would be fewer boundary-placement bugs or lower reread burden under an equal budget, not simply answering a short local question.

## Mechanical oracle/preflight

Oracle classifications:

- pass: hook appears after `getAndRecordStats(...)` in the `loadingFuture.addListener(...)` completion callback, or after `storeLoadedValue(...)` inside `getAndRecordStats(...)`;
- fail: hook appears after `loadAsync(...)` in `refresh(...)` initiation path;
- fail: hook appears before `LoadingValueReference.this.set(newResult)` in async reload transform;
- ambiguous/missing: no hook or insufficient structural anchors.

Validation commands run:

```bash
python3 experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/oracles/r21_oracle_preflight.py
python3 -m py_compile experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/oracles/r21_refresh_hook_oracle.py experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/oracles/r21_oracle_preflight.py
```

Result:

- `r21_oracle_preflight.py`: PASS.
  - `good`: expected ok=true, actual ok=true, `pass_completion_listener_after_publication`, hook line 2324.
  - `bad_initiation`: expected ok=false, actual ok=false, `fail`, hook line 2393.
  - `bad_transform`: expected ok=false, actual ok=false, `fail`, hook line 3573.
- `py_compile`: PASS, no output.

## Diff/status

`git diff --stat -- experiments/tmf-guava-v13-preflighted-20260822/R21_LONG_CHAIN_BUDGET_PRESSURE_SPEC.md experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget` produced no tracked diff output because these are new untracked files.

New artifact file sizes at verification time:

```text
experiments/tmf-guava-v13-preflighted-20260822/R21_LONG_CHAIN_BUDGET_PRESSURE_SPEC.md | 86 lines | 4221 bytes
experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/oracles/r21_oracle_preflight.py | 80 lines | 3368 bytes
experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/oracles/r21_refresh_hook_oracle.py | 142 lines | 5121 bytes
experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/reports/r21_oracle_preflight.json | 37 lines | 685 bytes
experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/tasks/R21_REFRESH_COMPLETION_TASK.md | 41 lines | 1540 bytes
experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/tasks/R21_TMF_LOCALIZED_REFRESH_LOCATOR.json | 39 lines | 1489 bytes
```

## Blockers / limitations

- No expensive model benchmark was run by design.
- The oracle is source-position based, not a full Guava unit-test execution. It is appropriate for preflight and task scoring but should be supplemented by compile/test checks if later agents generate real patches.
- The artifact uses `/root/.openclaw/workspace/repos/guava` as the source baseline for preflight; if the Guava repo moves, update `SOURCE_LOCAL_CACHE` in `r21_oracle_preflight.py` or parameterize it.
- This artifact does not yet bind a live TMF stale-claim ID; it provides a protocol-clean localized-refresh locator JSON that can later be replaced or augmented with actual TMF retrieval output.

## Exact next step

Run one cheap protocol rehearsal, not a large model benchmark:

```bash
python3 experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/oracles/r21_oracle_preflight.py
```

Then, if running agents later, execute exactly one pair under the R21 task card with equal budget:

- SOURCE_ONLY: stale note + A/B/G entry hints only;
- TMF_LOCALIZED_REFRESH: stale note + `R21_TMF_LOCALIZED_REFRESH_LOCATOR.json`;
- score both produced `LocalCache.java` patches with:

```bash
python3 experiments/tmf-guava-v13-preflighted-20260822/r21_long_chain_budget/oracles/r21_refresh_hook_oracle.py /path/to/patched/LocalCache.java
```

Only after this one-pair rehearsal passes protocol should a larger repeated benchmark be considered.
