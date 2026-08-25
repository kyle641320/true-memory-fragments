# Mutation Freshness M07e R20 Review

## Purpose

M07e reruns the synthetic deterministic mutation-freshness fixture with parameterized final gates to reduce small-sample noise while keeping the causal question separated:

- `final_gate=off`: no runner-level deterministic final rejection. This is closest to the M07b headline: stale docs can lure the agent to a live, compiling, semantically wrong wrapper site; TMF freshness withholding should prevent that.
- `final_gate=hard`: runner rejects final unless the latest deterministic test passed after a successful edit. This tests an engineering/product setting with validation loop, not pure stale-doc harm.

## Verification before run

- `mutation_m07_runner.py` parameterized with `--final-gate off|advisory|hard`.
- Smoke runs completed for `off` and `hard`.
- JSON outputs validated with `python3 -m json.tool`.

## R20 results

### final_gate=off (`mutation_freshness_m07e_off_r20`)

```json
{
  "SOURCE_ONLY": {
    "runs": 20,
    "raw_pass": 11,
    "semantic_evaluable": 12,
    "semantic_adjusted_pass": 11,
    "compile_ok": 20,
    "wrong_wrapper_site": 1,
    "primary": {
      "edit_protocol_fail": 8,
      "semantic_boundary_fail": 1,
      "pass": 11
    }
  },
  "STALE_DOC_CONTROL": {
    "runs": 20,
    "raw_pass": 7,
    "semantic_evaluable": 20,
    "semantic_adjusted_pass": 7,
    "compile_ok": 20,
    "wrong_wrapper_site": 13,
    "primary": {
      "pass": 7,
      "semantic_boundary_fail": 13
    }
  },
  "TMF_STALE_GATED": {
    "runs": 20,
    "raw_pass": 17,
    "semantic_evaluable": 17,
    "semantic_adjusted_pass": 17,
    "compile_ok": 20,
    "stale_claim_withheld": 20,
    "wrong_wrapper_site": 0,
    "primary": {
      "pass": 17,
      "edit_protocol_fail": 3
    }
  }
}
```

Interpretation:

- This strongly confirms the M07b headline at larger N.
- Stale unbound docs lured the agent to the live wrong wrapper in `13/20` runs.
- TMF stale gate withheld the stale claim in `20/20` runs and had `0/20` wrong-wrapper placements.
- TMF raw/semantic-adjusted pass is higher than SOURCE and STALE_DOC despite protocol noise: `17/20 raw`, `17/17 semantic-adjusted`.
- SOURCE_ONLY remains noisy (`8/20 edit_protocol_fail`), so headline should not be “source alone is bad”; headline is “stale unbound docs are harmful; freshness-bound stale withholding avoids that specific wrong-wrapper failure mode.”

### final_gate=hard (`mutation_freshness_m07e_hard_r20`)

```json
{
  "SOURCE_ONLY": {
    "runs": 20,
    "raw_pass": 18,
    "semantic_evaluable": 18,
    "semantic_adjusted_pass": 18,
    "compile_ok": 20,
    "wrong_wrapper_site": 1,
    "primary": {
      "pass": 18,
      "edit_protocol_fail": 1,
      "no_final": 1
    }
  },
  "STALE_DOC_CONTROL": {
    "runs": 20,
    "raw_pass": 18,
    "semantic_evaluable": 18,
    "semantic_adjusted_pass": 18,
    "compile_ok": 20,
    "wrong_wrapper_site": 1,
    "primary": {
      "pass": 18,
      "no_final": 1,
      "edit_protocol_fail": 1
    }
  },
  "TMF_STALE_GATED": {
    "runs": 20,
    "raw_pass": 19,
    "semantic_evaluable": 19,
    "semantic_adjusted_pass": 19,
    "compile_ok": 20,
    "stale_claim_withheld": 20,
    "wrong_wrapper_site": 0,
    "primary": {
      "pass": 19,
      "edit_protocol_fail": 1
    }
  }
}
```

Interpretation:

- Hard deterministic validation sharply reduces publication of wrong placements.
- SOURCE/TMF become much more stable; STALE_DOC mostly recovers after test feedback.
- This validates the engineering point: deterministic validation loop catches or corrects stale-doc-induced wrong-site edits.
- It is not the best causal headline for TMF-only freshness value, because the hard gate itself corrects/block wrong edits across arms.

## Recommended claim wording

Use this wording to avoid overclaiming:

> In a deterministic mutation fixture where an old bound claim becomes stale but a stale unbound note still points to a live compiling wrapper anchor, stale unbound docs caused semantic wrong-wrapper placement in 13/20 no-hard-gate runs. TMF freshness checking withheld the stale claim in 20/20 runs and had 0/20 wrong-wrapper placements, with all semantic-evaluable TMF runs passing (17/17). With a hard deterministic validation gate, wrong placements were largely blocked or corrected across arms, showing validation loop value but reducing the purity of the freshness-only A/B contrast.

## Files

- Runner: `bench/agent_ab/same_version_chain_v1/mutation_m07_runner.py`
- Off R20 JSON/report: `results/mutation_freshness_m07e_off_r20.json`, `results/MUTATION_FRESHNESS_M07E_OFF_R20_REPORT.md`
- Hard R20 JSON/report: `results/mutation_freshness_m07e_hard_r20.json`, `results/MUTATION_FRESHNESS_M07E_HARD_R20_REPORT.md`
- Raw transcripts:
  - `results/raw/mutation_freshness_m07e_off_r20/`
  - `results/raw/mutation_freshness_m07e_hard_r20/`
