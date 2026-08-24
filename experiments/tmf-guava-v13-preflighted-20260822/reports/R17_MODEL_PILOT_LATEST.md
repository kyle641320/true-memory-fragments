# r17 runner-controlled model pilot draft

## Verdict

PASS for the minimal runner-controlled pilot shape.

This is a zero-model validation of the protocol, not a full model-run proof. It shows the runner can consume an intent file, block a stale action at execution time, force reread, and then allow a fresh action.

## What was validated

- Model output contract uses intent JSON only; source files are not edited directly by the model.
- Runner checks the intent against stale-boundary hash evidence before apply.
- A stale intent is blocked.
- After reread, a fresh intent is allowed.
- Hidden scorer still checks current drift preservation, not just compile/diff hygiene.

## Setup

- Run dir: `/root/.openclaw/workspace/experiments/tmf-guava-v13-preflighted-20260822/runtime/run-r17-model-pilot-20260824T101005`
- Target boundary: `CompactHashing.newCapacity(int mask)`
- Phase A belief hash: `0551dcd54dbc198ca3314cebb1cfbd2960314ff56e0df4d843d9dca02832bbf8`
- Parent drift after Phase A: `mask < 64` → `mask < 128`

## Intent files

- `control_intent.json`
- `treatment_intent_stale.json`
- `treatment_intent_fresh.json`

## Observed behavior

- Control had no interception. The stale helper intent landed and the hidden scorer failed for `currentMask=127`.
- Treatment first submitted the same stale helper intent.
- Runner emitted `TMF_REFLEX_BLOCK` because the intent touched a stale boundary and no reread had happened.
- After explicit boundary reread, the fresh helper intent was allowed and the hidden scorer passed.

## Scores

```json
{
  "control": {
    "has_helper": true,
    "fresh_drift_preserved": true,
    "delegates_to_current_boundary": false,
    "contains_stale_inline_64": false,
    "hidden_currentMask_127_pass": false
  },
  "treatment": {
    "has_helper": true,
    "fresh_drift_preserved": true,
    "delegates_to_current_boundary": true,
    "contains_stale_inline_64": false,
    "hidden_currentMask_127_pass": true
  },
  "pilot_pass": true
}
```

## Checks

```json
{
  "script_py_compile_rc": 0,
  "script_py_compile_stderr": "",
  "control_git_diff_check_ok": true,
  "treatment_git_diff_check_ok": true
}
```

## Files read

- runtime/run-r16-20260823T234915/R16_FINAL_REPORT.md
- runtime/run-r17-real-intercept-20260824T095418/R17_SMOKE_REPORT.md
- R17_NEXT_STEPS.md
- R17_MODEL_PILOT_DRAFT.md

## Files changed

- scripts/r17_runner_controlled_model_pilot.py
- runtime/run-r17-model-pilot-20260824T101005/control_intent.json
- runtime/run-r17-model-pilot-20260824T101005/treatment_intent_stale.json
- runtime/run-r17-model-pilot-20260824T101005/treatment_intent_fresh.json
- runtime/run-r17-model-pilot-20260824T101005/R17_MODEL_PILOT_REPORT.md
- reports/R17_MODEL_PILOT_LATEST.md

## Recommendation

Recommend a formal model pilot next, with the same guarded intent protocol and a real model producing the intent JSON.
