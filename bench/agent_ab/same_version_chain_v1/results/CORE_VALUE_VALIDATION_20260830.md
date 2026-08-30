# TMF Core Value Validation — 2026-08-30

## Scope

No TMF body code was modified in this validation pass.

Repository/worktree:

- `/root/.openclaw/workspace/worktrees/tmf-java-nodes-step0`
- `HEAD == origin/master == 6649d6e005dce44fc61732818ae4e9b0ad507513`

## Setup checks

Both committed runners passed setup checks:

- `python3 bench/agent_ab/same_version_chain_v1/order_m16_complex_two_phase_runner.py --setup-check`
- `python3 bench/agent_ab/same_version_chain_v1/order_m21_stale_api_trap_runner.py --setup-check`

Both returned `ok: true`.

## New smoke run: M21 stale API trap

Command:

```bash
python3 bench/agent_ab/same_version_chain_v1/order_m21_stale_api_trap_runner.py \
  --repeats 1 \
  --tag order_m21_corevalue_smoke_r1 \
  --final-gate hard \
  --phase-a-turns 8 \
  --phase-b-turns 24
```

Result files:

- `results/order_m21_corevalue_smoke_r1.json`
- `results/ORDER_M21_COREVALUE_SMOKE_R1_REPORT.md`

Summary:

- SOURCE_ONLY: 0/1 pass, `hidden_oracle_fail`
- PREREAD_STALE_SOURCE: 0/1 pass, `hidden_oracle_fail`
- STALE_DOC_CONTROL: 0/1 pass, `hidden_oracle_fail`
- TMF_REFRESHED_MAP: 1/1 pass

Interpretation:

M21 gives a clean one-run separation in favor of TMF refreshed-map behavior. The stale controls and source-only path all fail hidden oracle, while TMF withholds stale claim and succeeds.

## Attempted smoke run: M16 complex payment review

Command attempted:

```bash
python3 bench/agent_ab/same_version_chain_v1/order_m16_complex_two_phase_runner.py \
  --repeats 1 \
  --tag order_m16_corevalue_smoke_r1 \
  --final-gate hard \
  --phase-a-turns 8 \
  --phase-b-turns 24
```

Partial result file:

- `results/order_m16_corevalue_smoke_r1.json`

Effective rows before interruption:

- SOURCE_ONLY: 0/1 pass, `hidden_oracle_fail`
- PREREAD_STALE_SOURCE: 0/1 pass, `hidden_oracle_fail`
- STALE_DOC_CONTROL: not run
- TMF_REFRESHED_MAP: not run

The run was interrupted at STALE_DOC_CONTROL Phase A by broker `exit 4`. This is execution-layer noise, not a benchmark semantic result. Therefore this M16 smoke should not be counted as a complete four-arm replication.

## Current validation judgment

TMF core value is further supported but still scoped-positive:

- Confirmed: stale claim withholding plus current localized refresh can prevent stale-context-induced hidden-oracle failures.
- Newly reinforced by M21 smoke: SOURCE_ONLY / PREREAD_STALE_SOURCE / STALE_DOC_CONTROL failed, while TMF_REFRESHED_MAP passed.
- Still not fully proven: broad ROI, stable superiority across many task families/repos, and cost-adjusted productivity.

Recommended next validation if continuing:

1. Keep TMF body unchanged.
2. Run a clean M21 R4/R8 replication only if more statistical confidence is needed.
3. Treat M16 partial smoke as invalid for four-arm replication due to broker exit 4; optionally rerun later when broker is stable.
4. Avoid overclaiming beyond stale-context safety / current semantic refresh.

## Follow-up: M16 retry R1

The earlier M16 smoke was interrupted by broker exit 4. A retry completed all four arms:

File:

- `results/order_m16_corevalue_retry_r1.json`

Summary:

- SOURCE_ONLY: hidden_oracle_fail
- PREREAD_STALE_SOURCE: hidden_oracle_fail
- STALE_DOC_CONTROL: pass
- TMF_REFRESHED_MAP: hidden JUnit pass, but runner primary `compile_action_fail`

Interpretation:

This supports TMF > SOURCE_ONLY at the hidden-oracle level, but still contains M16 runner/classifier noise. Do not count it as a clean raw-pass replication unless M16 classifier/checker is cleaned up separately.

## Follow-up: M16 classfix/checkerfix replay

The M16 runner/checker was cleaned in the same style as M21 and the existing retry R1 work dirs were replayed without LLM rerun.

Files:

- `results/order_m16_corevalue_retry_r1_classfix_checkerfix_replay.json`
- `results/ORDER_M16_COREVALUE_RETRY_R1_CLASSFIX_CHECKERFIX_REPLAY_REPORT.md`

Corrected summary:

- SOURCE_ONLY: 0/1 hidden_oracle_fail
- PREREAD_STALE_SOURCE: 0/1 hidden_oracle_fail
- STALE_DOC_CONTROL: 1/1 pass
- TMF_REFRESHED_MAP: 1/1 pass

This provides a clean corrected replay showing TMF > SOURCE_ONLY on M16 retry R1, while also confirming that stale-doc control can match TMF on this fixture.
