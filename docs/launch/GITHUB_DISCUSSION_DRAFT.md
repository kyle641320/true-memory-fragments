# True Memory Fragments v0.1.0rc3 is available

TMF is a source-aware stale-context guard for AI coding agents.

When a coding agent remembers a call chain from an earlier session, source changes can make that memory unsafe. TMF checks the source-backed claim and blocks reuse when it is stale.

## What we have validated

Through deterministic source-analysis tests, Python and Java validation, and scoped agent experiments, we have validated:

- Source-bound freshness and stale-claim detection;
- Hard stale gates that stop unsafe graph expansion;
- Explicit source fallback and localized reread guidance;
- Calls, reads, writes, inheritance, and API relationships in the covered scenarios;
- Reproducible stale-context prevention behavior across the covered Python and Java paths.

If the source binding is still current, the claim may be reused. If the source has changed, TMF stops and requires a fresh read.

In this Guava M10 experiment, TMF_STALE_GATED matched SOURCE_ONLY on evaluated semantic-boundary correctness: semantically evaluable runs passed 34/34 and 20/20 respectively, with no obsolete inline-loop placements in either arm. Raw failures were attributed to edit/finalization protocol issues rather than confirmed semantic-boundary failures. This is an observed result in this experiment, not a statistical equivalence claim or a 50/50 task-success claim.

## 30-second demo

Run this from a clean checkout:

```bash
git clone https://github.com/kyle641320/true-memory-fragments.git
cd true-memory-fragments
python -m pip install --pre true-memory-fragments==0.1.0rc3
python scripts/demo_stale_gate.py
```

Expected output:

```text
STALE CLAIM BLOCKED: PASS
SOURCE FALLBACK PROVIDED: PASS
REREAD REQUIRED: PASS
```

The demo is run from the repository root; installing the PyPI package alone does not download repository demo scripts.

## Scoped case study

In a 50-run Guava M10 pre-read experiment:

- `TMF_STALE_GATED`: 42/50 raw passes;
- `SOURCE_ONLY`: 40/50 raw passes;
- Both arms compiled successfully in 50/50 runs;
- `PREREAD_STALE_SOURCE`: 2/50 raw passes;
- `STALE_DOC_CONTROL`: 0/50 raw passes.

Raw passes, task-result passes, compilation, and evaluated semantic-boundary correctness are distinct measures. Task-result passes (`task_result_pass`, also matching `post_test_ok`) were 42/50 for `TMF_STALE_GATED` and 41/50 for `SOURCE_ONLY`; one SOURCE_ONLY run achieved the task result but failed raw scoring because finalization was missing. Runs without an evaluable semantic result are not counted as semantic successes, and successful compilation does not imply task success.

The two arms matched on evaluated semantic-boundary correctness (34/34 and 20/20 respectively), not on every outcome measure. Neither arm had obsolete inline-loop placements. The stale-context control arms frequently placed edits at the obsolete inline queue-drain loop (43/50 and 45/50), while the current source required the `dispatchPreparedSubscriber` boundary.

This observed result is limited to this experiment; it is not a statistical equivalence claim or a 50/50 task-success claim. It is not a claim of general productivity, speed, token savings, or bug reduction. The experiment uses one Guava M10 scenario, synthetic agent interactions, and protocol-sensitive scoring.

Raw results and independent audit:

- Case study: https://github.com/kyle641320/true-memory-fragments/blob/master/docs/case-studies/guava-m10-stale-gating.md
- Evidence status: https://github.com/kyle641320/true-memory-fragments/blob/master/docs/AGENT_RUNTIME_VALUE_STATUS.md

## Feedback wanted

- Could you install it without reading the source?
- Is the stale-gate result understandable?
- Does it fit any real coding-agent workflow?
- Did you encounter a false positive, false negative, or unhelpful reread boundary?

Project: https://github.com/kyle641320/true-memory-fragments
PyPI: https://pypi.org/project/true-memory-fragments/

This is an independent open-source project. Feedback, criticism, and reproduction reports are welcome.
