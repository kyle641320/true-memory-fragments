# Guava M10: stale-claim gating case study

This scoped case study records the existing Guava M10 preread experiment; it is not a benchmark of Guava or a claim about general agent performance.

## Setup

The R50 report compares four arms (50 runs each): `SOURCE_ONLY`, `PREREAD_STALE_SOURCE`, `STALE_DOC_CONTROL`, and `TMF_STALE_GATED`. The independent audit was read-only and used the existing report and 200 raw records; no runs were re-executed.

## Observed result

`TMF_STALE_GATED` produced 42/50 raw passes versus 40/50 for `SOURCE_ONLY`; all arms compiled 50/50. The stale preread arms produced 2/50 and 0/50 raw passes, with wrong-inline-loop placement in 43/50 and 45/50 runs respectively. The audit's interpretation is that stale claims can pull edits toward the obsolete queue-drain boundary; gating withholds the stale boundary and leaves source inspection to select the current prepared-dispatch handoff.

## Reproduce the deterministic gate demo

```bash
python3 scripts/demo_stale_gate.py
```

The demo is offline and creates a temporary Git repository. A terminal recording is provided at [`../../recordings/stale-gate.cast`](../../recordings/stale-gate.cast) when asciinema is available.

## Scope and limitations

These are existing fixture/report observations, not causal proof. The experiment uses a single Guava M10 scenario, synthetic agent interactions, and protocol-sensitive scoring. Raw-pass differences are small between the two healthy arms, and failures include edit-protocol/no-final noise. The audit found no per-record `stale_claim_withheld=true` field; the arm-level interpretation comes from runner aggregation and freshness mismatch metadata. No claim is made about other repositories, versions, models, or production workloads.

Sources: [`GUAVA_M10_PREREAD_R50_REPORT.md`](../../bench/agent_ab/same_version_chain_v1/results/GUAVA_M10_PREREAD_R50_REPORT.md), [`GUAVA_M10_PREREAD_R50_INDEPENDENT_AUDIT.md`](../../bench/agent_ab/same_version_chain_v1/results/GUAVA_M10_PREREAD_R50_INDEPENDENT_AUDIT.md).
