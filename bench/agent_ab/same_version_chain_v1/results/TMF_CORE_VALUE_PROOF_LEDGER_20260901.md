# TMF Core Value Proof Ledger — 2026-09-01 update

Scope: update the 2026-08-30 proof ledger with the new M15/M16/M21 R4 runs. This is evidence documentation only; TMF body code is not modified.

## New evidence added

### M15 R4
- Mode: `outbox_m15_two_phase_contract_shift`
- Total rows: 16
- `SOURCE_ONLY`: 4/4 raw, 4/4 semantic, withheld=0; primary: pass=4
- `PREREAD_STALE_SOURCE`: 4/4 raw, 4/4 semantic, withheld=0; primary: pass=4
- `STALE_DOC_CONTROL`: 4/4 raw, 4/4 semantic, withheld=0; primary: pass=4
- `TMF_STALE_GATED`: 4/4 raw, 4/4 semantic, withheld=4; primary: pass=4

### M16 R4
- Mode: `order_m16_complex_two_phase_payment_review`
- Total rows: 16
- `SOURCE_ONLY`: 0/4 raw, 0/4 semantic, withheld=0; primary: hidden_oracle_fail=4
- `PREREAD_STALE_SOURCE`: 0/4 raw, 0/4 semantic, withheld=0; primary: hidden_oracle_fail=4
- `STALE_DOC_CONTROL`: 4/4 raw, 4/4 semantic, withheld=0; primary: pass=4
- `TMF_REFRESHED_MAP`: 2/4 raw, 2/4 semantic, withheld=4; primary: hidden_oracle_fail=2, pass=2

### M21 R4
- Mode: `order_m21_stale_api_trap_fulfillment_gate`
- Total rows: 16
- `SOURCE_ONLY`: 4/4 raw, 4/4 semantic, withheld=0; primary: pass=4
- `PREREAD_STALE_SOURCE`: 1/4 raw, 1/4 semantic, withheld=0; primary: hidden_oracle_fail=3, pass=1
- `STALE_DOC_CONTROL`: 0/4 raw, 0/3 semantic, withheld=0; primary: no_effect_false_completion=1, hidden_oracle_fail=3
- `TMF_REFRESHED_MAP`: 3/4 raw, 3/4 semantic, withheld=4; primary: hidden_oracle_fail=1, pass=3

## Claim status after 2026-09-01 runs

### Claim 1 — Stale-memory containment works
**Status: PROVEN / strengthened.**

- M15 R4: TMF stale-gated arm withheld stale claim 4/4 while still passing 4/4.
- M16 R4: TMF_REFRESHED_MAP withheld stale claim 4/4.
- M21 R4: TMF_REFRESHED_MAP withheld stale claim 4/4.
- Across these new runs, stale-claim withholding occurred whenever expected: 12/12.

### Claim 2 — Current-source refresh can recover hidden invariants that stale/source-only contexts miss
**Status: SCOPED SUPPORTED, not universal.**

- M16 R4: SOURCE_ONLY 0/4 and PREREAD_STALE_SOURCE 0/4, while TMF_REFRESHED_MAP 2/4. This supports recovery over source-only/stale-preread, but only partially.
- M21 R4: TMF_REFRESHED_MAP 3/4 and STALE_DOC_CONTROL 0/4, supporting recovery over stale-doc control. However SOURCE_ONLY was 4/4, so it does not show source-only separation.
- M15 R4: all arms 4/4, so it is non-discriminating.

### Claim 3 — TMF is better than naive stale preread/docs
**Status: SUPPORTED for stale-doc traps, but fixture-dependent.**

- M21 R4 strongly supports this versus stale docs: TMF 3/4 vs STALE_DOC_CONTROL 0/4; PREREAD_STALE_SOURCE only 1/4.
- M16 R4 cuts against a broad formulation: STALE_DOC_CONTROL 4/4 while TMF 2/4. Therefore the claim must stay scenario-specific.

### Claim 4 — TMF is better than source-only baseline
**Status: NOT STABLY PROVEN.**

- Pro-TMF evidence: M16 R4 TMF 2/4 vs SOURCE_ONLY 0/4.
- Anti/neutral evidence: M21 R4 SOURCE_ONLY 4/4 vs TMF 3/4; M15 R4 all arms pass.
- Updated conclusion: TMF can help source-only misses, but current R4 matrix does not prove stable superiority over source-only.

### Claim 5 — TMF failures are not stale-gating failures
**Status: SUPPORTED / strengthened with explicit 2026-09-01 attribution.**

- M16 TMF failed rows: stale claims were withheld; agent made a plausible current-source patch in `OrderService`, but hidden oracle still failed. This is incomplete implementation / task-oracle mismatch, not stale claim injection.
- M21 TMF failed row: stale claim was withheld; failure was edit-placement/execution noise. The agent initially emitted multiple actions, had an early final rejected, then edited `PaymentIntentService` instead of the required `OrderService` branch.
- No inspected TMF failure shows stale claim text injected as authoritative current context.

### Claim 6 — TMF has positive product ROI
**Status: SCOPED ROI remains plausible, product ROI NOT PROVEN.**

- M15 adds clean non-regression but no ROI separation.
- M16/M21 add mixed discriminating evidence.
- Current best wording: TMF reduces stale-context risk and sometimes recovers hidden invariants; evidence is insufficient for broad product-level ROI or stable source-only superiority.

### Claim 7 — TMF should be modified now
**Status: NOT PROVEN; do not modify TMF body.**

- The new failures point to agent implementation/placement/read-order issues, not a demonstrated TMF freshness defect.
- User constraint remains: do not modify TMF body unless explicitly re-authorized.

## Overall verdict

The 2026-09-01 R4 matrix strengthens the narrow claim that TMF stale-memory containment works. It also supports that TMF can help in stale-context traps. It does **not** prove stable product-level superiority over source-only, because M16 and M21 split in opposite directions and M15 is non-discriminating.

Recommended next step: if more evidence is needed, design a preregistered discriminating fixture where source-only is not trivially sufficient and stale-doc control is not accidentally helpful; otherwise stop and report the current scoped-positive conclusion honestly.

## Addendum — direct semantic-map refresh oracle, 2026-09-01 late

After quarantining off-track M22-M25 end-to-end task traps, a direct pre-agent oracle was added:

- Script: `bench/agent_ab/same_version_chain_v1/direct_refresh_oracle_eval.py`
- JSON: `bench/agent_ab/same_version_chain_v1/results/tmf_direct_refresh_oracle_eval_20260901.json`
- Report: `bench/agent_ab/same_version_chain_v1/results/TMF_DIRECT_REFRESH_ORACLE_EVAL_20260901.md`

Result over retained M15/M16/M21 fixture families:

```json
{
  "cases": 3,
  "pass": 3,
  "stale_withheld": 3,
  "avg_required_precision": 0.5238,
  "avg_required_recall": 1.0,
  "avg_side_effect_recall": 1.0
}
```

Interpretation:

- This directly tests TMF's design-intent layer before any agent edit loop: stale invalidation, localized reread planning, and side-effect awareness.
- Recall is strong in this limited retained set: all expected fresh symbols and side-effect kinds were covered.
- Precision is moderate, especially M15, due extra local reads. That is acceptable for safety but not yet an efficiency/ROI proof.
- This addendum supersedes the off-track M22-M25 trap-design attempt as the preferred evidence direction.

## Addendum — stale-slice supplement precision cleanup, 2026-09-02

A minimal implementation optimization was applied to `tmf/stale_slice.py`: current-source supplement reads now skip ordinary class/interface/record/enum containers and constructors. Rationale: direct oracle showed M15's remaining clear noise was container/constructor reads; method-level reads carry the state transitions, collaborator contracts, and side effects needed for refresh.

Validation:

- `python3 -m unittest tests.test_stale_slice -q` → `Ran 3 tests ... OK`
- `python3 bench/agent_ab/same_version_chain_v1/direct_refresh_oracle_eval.py` → 3/3 pass
- `python3 -m unittest discover -s tests -q` → `Ran 615 tests in 69.628s OK (skipped=5)`

Updated direct-oracle summary:

```json
{
  "cases": 3,
  "pass": 3,
  "stale_withheld": 3,
  "avg_required_precision": 0.5397,
  "avg_tiered_useful_precision": 0.9444,
  "avg_required_recall": 1.0,
  "avg_side_effect_recall": 1.0
}
```

Effect: recall stayed at 1.0 and useful precision improved from 0.9048 to 0.9444. This is a modest but real efficiency cleanup, not a new broad ROI proof.
