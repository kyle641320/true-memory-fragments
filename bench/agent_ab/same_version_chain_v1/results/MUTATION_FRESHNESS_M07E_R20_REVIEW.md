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
- TMF `17/20 raw` is not a semantic/freshness failure rate. The 3 raw failures are edit protocol / no-effect false completions: the agent attempted nonexistent exact anchors, all edits failed, no diff was produced, then it finalized anyway.
- TMF semantic-evaluable pass is therefore `17/17`; stale claim withholding is `20/20`; wrong-wrapper placement is `0/20`.
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
- `raw_pass` here still includes a final-protocol requirement. If measured as “did the task reach a verifiable correct result in the workspace?”, hard-gate task-result pass is SOURCE `19/20`, STALE_DOC `19/20`, TMF `20/20`.
- TMF's only raw failure in hard mode (`r11`) had already produced the correct helper-site diff, but the agent stopped before running `test` + `final`; therefore it is a final-protocol/no-final failure, not a task-result failure.
- This validates the engineering point: deterministic validation loop catches or corrects stale-doc-induced wrong-site edits, and a result-oriented evaluator should not mark correct workspace state as failed solely because final reporting was missing.
- It is not the best causal headline for TMF-only freshness value, because the hard gate itself corrects/blocks wrong edits across arms.



## Result-oriented metric note

The original `raw_pass` metric requires a valid `final` action. That is useful for measuring autonomous protocol completion, but it is stricter than the human/product question: “did the task reach a verifiable result?”

For `final_gate=hard`, one TMF run (`r11`) was raw-failed because the model stopped after a correct edit without running final. The final workspace diff was nevertheless correct:

```diff
 static void invokeReflectively(Object event) {
   phase = 1;
   // CURRENT INVARIANT: the hook call belongs below this line and immediately before methodInvoke(event).
+  hook();
   methodInvoke(event);
   phase = 2;
 }
```

Therefore the hard-gate result should be read with two separate metrics:

| arm | raw/final-protocol pass | task-result pass | note |
| --- | ---: | ---: | --- |
| SOURCE_ONLY | 18/20 | 19/20 | one correct workspace state lacked final; one remaining protocol/edit failure |
| STALE_DOC_CONTROL | 18/20 | 19/20 | one correct workspace state lacked final; one remaining protocol/edit failure |
| TMF_STALE_GATED | 19/20 | 20/20 | only raw failure was correct diff without final/test completion |

This metric better matches the expectation that an executor should continue until a task has a result, and that a verifiably correct workspace state should be counted separately from final-message protocol compliance.

## TMF raw-pass root-cause note

`TMF_STALE_GATED` under `final_gate=off` has `17/20` raw pass, but the three failures are not TMF semantic boundary failures:

| rep | primary | freshness | withheld | diff | successful edits | root cause |
| --- | --- | --- | --- | --- | --- | --- |
| r2 | `edit_protocol_fail` | stale | yes | none | 0 | attempted nonexistent exact anchor `return invokeReflectively(method, subscriber, event);`, then false-finalized |
| r3 | `edit_protocol_fail` | stale | yes | none | 0 | attempted nonexistent Guava-style anchors `method.invoke(target, event);` / `method.invoke(subscriber, event);`, then false-finalized |
| r10 | `edit_protocol_fail` | stale | yes | none | 0 | attempted several nonexistent `method.invoke(...)` anchors, then false-finalized |

All three share the same pattern: freshness check worked (`fresh=false`), stale claim was withheld, no wrong-wrapper edit was made, compilation stayed OK only because the file was unchanged, and the agent falsely finalized after failed edits. Therefore these count as raw/protocol failures, not TMF semantic failures.

## Recommended claim wording

Use this wording to avoid overclaiming:

> In a deterministic mutation fixture where an old bound claim becomes stale but a stale unbound note still points to a live compiling wrapper anchor, stale unbound docs caused semantic wrong-wrapper placement in 13/20 no-hard-gate runs. TMF freshness checking withheld the stale claim in 20/20 runs and had 0/20 wrong-wrapper placements. TMF raw pass was 17/20 only because of three edit protocol / no-effect false completions with zero successful edits and no diff; among semantic-evaluable TMF runs, pass was 17/17. With a hard deterministic validation gate, wrong placements were largely blocked or corrected across arms; under a result-oriented metric, hard-gate task-result pass was SOURCE 19/20, STALE_DOC 19/20, and TMF 20/20. This shows validation loop value but reduces the purity of the freshness-only A/B contrast.

## Files

- Runner: `bench/agent_ab/same_version_chain_v1/mutation_m07_runner.py`
- Off R20 JSON/report: `results/mutation_freshness_m07e_off_r20.json`, `results/MUTATION_FRESHNESS_M07E_OFF_R20_REPORT.md`
- Hard R20 JSON/report: `results/mutation_freshness_m07e_hard_r20.json`, `results/MUTATION_FRESHNESS_M07E_HARD_R20_REPORT.md`
- Raw transcripts:
  - `results/raw/mutation_freshness_m07e_off_r20/`
  - `results/raw/mutation_freshness_m07e_hard_r20/`
