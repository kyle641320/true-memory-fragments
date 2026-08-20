# Execution notes (operational, not part of the frozen preregistration)

`PROTOCOL.md` is frozen. Nothing here changes arms, tasks, scoring, or gates.
This file records execution-environment constraints that the protocol assumed
away, plus the log of invalid runs.

## Constraint discovered 2026-08-20: arm execution is not freely parallel

The protocol treats the 9 arms (3 tasks × 3 retrieval conditions) as
independent, which is true *by design* but not true *operationally*. Each arm is
a separate model session, and the shared model channel enforces a rate limit.
Launching all 9 at once exhausted the quota before any arm produced a token.

Two things follow, and both must be respected by whoever runs this next.

**1. Batch the arms.** Do not launch all 9 concurrently. Launch at most a few at
a time, ideally one task's three arms per batch, so the three conditions of a
given task run under comparable channel conditions. Cross-arm comparability is
the whole point of the suite; running `no_tool` on a healthy channel and
`tmf_full` on a throttled one would confound retrieval condition with
infrastructure state.

**2. Keep per-arm work trees isolated.** B02 is `compile_repair`. All three arms
must edit their own copy under `results/work/B02__<arm>/`, never the pristine
`fixtures/B02/work/`. If arms shared one tree, whichever arm ran first would
leave the code compiling and later arms would score a free pass.

## Invalid run log

Per `PROTOCOL.md` attribution rules, infrastructure failures are classified
`tool/runtime`, are **invalid**, and must never be used to tune prompts,
goldens, the scorer, retrieval, packing, or freshness logic.

### Run 2026-08-20T00:5x — INVALID (`tool/runtime`)

- Arms launched: all 9, concurrently, on `newapi/gpt-5.5`.
- Outcome: 9/9 failed with `API rate limit reached` (FailoverError).
- Runtime per arm: 2–10s. Tokens per arm: 0 in / 0 out.
- A subsequent minimal probe ("reply PROBE_OK, no tools") also failed in ~1s
  with 0 tokens, which rules out concurrency as the sole cause: the channel
  itself was unavailable, not merely saturated by this suite.

Integrity check after the failure, confirming the suite is clean for a rerun:

- `results/answers/` empty — no partial or salvaged answers exist.
- `diff -rq fixtures/B02/work results/work/B02__<arm>` returned 0 differences
  for all three arms — no work tree was touched.

No fixture rebuild is required. The rerun starts from the same state as the
first attempt.

### Retry 2026-08-20, single arm — INVALID (`tool/runtime`)

To separate "quota saturated by our own 9 concurrent arms" from "channel down",
a single arm (`B01__no_tool`) was launched alone. It also failed with
`API rate limit reached` in ~1s at 0 tokens.

Conclusion: the batching constraint above is real and worth keeping, but it was
not the cause of this outage. Reducing concurrency does not make the suite
runnable while the channel itself is rate-limited. Launch nothing further until
a trivial probe succeeds.

Integrity re-verified after this attempt: `results/answers/` still empty, B02
work trees still byte-identical to the fixture, and the B02 baseline still fails
with exactly the seeded single error at `EventBus.java:260`.

## Rerun preconditions

1. Confirm the model channel answers a trivial probe before launching any arm.
2. Launch in batches (see above), B01 first to get one complete comparable
   triple as early as possible.
3. Re-verify the B02 baseline still fails with exactly the seeded error
   (`List<Subscriber>` not convertible to `Iterator<Subscriber>`) before any arm
   edits its tree.
4. If the model channel has to change, change it for **all nine arms** and
   record the new model here. Mixing channels across arms invalidates the
   comparison.
