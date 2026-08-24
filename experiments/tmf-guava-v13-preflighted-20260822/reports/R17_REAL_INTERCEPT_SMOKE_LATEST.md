# r17 real/action-time interception smoke

## Verdict

PASS for zero-model runner-level interception smoke.

This does **not** prove TMF product value yet. It proves the next evaluation can avoid r16's invalid prompt-simulated reflex by enforcing a real action-time block before a stale-dependent patch lands.

## Setup

- Run dir: `/root/.openclaw/workspace/experiments/tmf-guava-v13-preflighted-20260822/runtime/run-r17-real-intercept-20260824T095418`
- Target boundary: `CompactHashing.newCapacity(int mask)`
- Phase A belief hash: `0551dcd54dbc198ca3314cebb1cfbd2960314ff56e0df4d843d9dca02832bbf8`
- Parent drift after Phase A: `mask < 64` → `mask < 128`

## Observed behavior

- Control had no interception. Stale helper patch landed and hidden scorer failed for currentMask=127.
- Treatment first attempted the same stale helper patch.
- Runner emitted `TMF_REFLEX_BLOCK` because the action touched a stale boundary and no current reread had happened.
- After explicit boundary reread, the fresh helper patch was allowed and hidden scorer passed.

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
  "smoke_pass": true
}
```

## Next pilot requirements

A model pilot is valid only if:

1. The model is not told the stale boundary upfront.
2. The model outputs an intended patch/action to a runner-controlled file, not direct uncontrolled source edits.
3. The runner applies or blocks that action using the same stale-boundary hash check.
4. All per-arm artifacts are isolated.
5. Hidden scorer verifies current drift preservation, not only compile success.

If the model can edit source directly, r17 becomes invalid like r16 because the reflex is not actually enforced.
