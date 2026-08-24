# R20 Tunnel Vision Prevention Pre-registration (Guava)

## Objective

Test whether TMF prevents tunnel-vision bugs during code edits when a dependency boundary changes.

This is a correctness experiment, not a read/token efficiency experiment.

## Hypothesis

When a stale dependency fragment is detected, TMF will force a localized reread that lowers the rate of tunnel-vision bugs compared with a source-only baseline.

## Chosen chain

Use the Guava cache refresh path:

- A: `com.google.common.cache.CacheBuilder`
- B: `com.google.common.cache.LocalCache`
- C: `com.google.common.cache.LoadingValueReference`
- D: `com.google.common.cache.CacheLoader`
- E: `com.google.common.cache.LoadingCache`

The chain is deliberately multi-file and behaviorally meaningful.

## Why this chain

- `CacheBuilder.refreshAfterWrite(...)` declares the refresh boundary.
- `LocalCache.refresh(...)` executes the refresh boundary.
- `LoadingValueReference.loadFuture(...)` decides how the refreshed value is produced and published.
- `CacheLoader.reload(...)` defines the refresh semantic contract.
- `LoadingCache.refresh(...)` exposes the user-visible action.

A stale mental model of one file can plausibly place a new call or behavior change on the wrong side of the refresh boundary.

## Arms

### SOURCE_ONLY

- Agent gets the t0 chain understanding.
- No TMF stale detection.
- No forced reread.
- Agent edits the target file directly.

### TMF_PROTECT

- Agent gets the t0 chain understanding plus a bounded fragment for the stale boundary.
- If C or another boundary file has drifted, TMF blocks stale continuation.
- TMF forces reread of the affected boundary before the edit in A is allowed.

## Stage 1: t0 understanding

Both arms read the full chain.

The TMF arm also keeps only a bounded fragment for the relevant boundary.

Discard the final answer from this stage.

## Stage 2: mutation

Mutate the refresh boundary in C / adjacent boundary code so that an A-only edit becomes wrong.

The mutation must create a case where:
- looking only at A is insufficient
- rereading C changes the correct edit in A

Candidate mutation family:
- change how refresh is scheduled or published
- change the reload path so the timing/order boundary moves
- change the contract for when a refreshed value is returned versus published

The mutation must not be cosmetic.
It must affect correctness of the later A edit.

## Stage 3: modification task

Ask the agent to modify A with a small but behaviorally meaningful change.

The A task must be phrased so that:
- SOURCE_ONLY is likely to make a tunnel-vision mistake if it ignores the mutated boundary
- TMF_PROTECT is forced to reread C and is therefore more likely to edit A correctly

## Mechanical oracle

Use a mechanical oracle only.
Do not use an LLM judge.

The oracle should verify one or more of:
- the new call lands on the correct side of the refresh boundary
- refresh order is preserved
- reload / publish semantics remain correct after the patch
- the patch does not violate the chosen contract around refresh timing

Possible oracle forms:
- source-position assertions around the refresh path
- static pattern checks around refresh/reload publication order
- unit tests that fail for the tunnel-vision patch and pass for the correct patch

## Primary metric

Bug rate:
- fraction of scenarios where SOURCE_ONLY violates the oracle
- fraction of scenarios where TMF_PROTECT violates the oracle

TMF wins if its bug rate is materially lower.

## Secondary metric

- reread count
- token count
- tool-call count

Secondary only.

## Pre-registration rules

Before running:
- freeze the exact task list
- freeze the exact mutation list
- freeze the oracle
- do not rewrite the success criterion after seeing results

## Suggested minimum sample size

At least 6-10 mutation scenarios.

Each scenario must run both arms.

## Interpretation

- If TMF_PROTECT bug rate is lower: TMF core value is supported.
- If the two arms are similar: either the mutation was not a true tunnel-vision trap, or TMF did not actually influence the edit.
- If TMF is slower but less buggy: that is still a TMF win, because correctness is the main target.
