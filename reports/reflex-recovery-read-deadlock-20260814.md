# TMF reflex recovery Read deadlock acceptance — 2026-08-14

## Root cause

The v3 excluded smoke reached the intended sequence: stale edit blocked, localized warm succeeded, then the agent issued an exact `Read api.py`. Two production transport/metadata shapes combined to reject it. OpenClaw's lifecycle can supply Read pagination as decimal strings, while Python callee-collision bindings can have `reliable: false` with no line range. The plugin accepted only numeric pagination and, for an unreliable anchor, accepted only literally omitted pagination. It therefore rejected OpenClaw's normal whole-file `offset: 1, limit: 2000` request and returned `need_read`. This produced a self-deadlock: the gate required a Read while forbidding the qualifying whole-file Read.

The Python freshness hook was not the blocker after warm; its Read decision was `allow`. The fault was the plugin's transport-shape handling before candidate registration.

## Fix

- Normalize Read `offset`/`limit` from either safe integers or unsigned decimal strings.
- For unavailable/unreliable anchors, accept only a demonstrable whole-file Read: start at line 1 and omit the limit or request at least the current complete file line count.
- Preserve conservative rejection for fractions, negatives, zero limits, malformed values, and shorter unreliable-anchor ranges.
- Keep the production lifecycle invariant: `before_tool_call` allows and registers only a qualifying recovery-read candidate; only successful `after_tool_call` records observation.
- A failed Read remains unobserved; the identical stale fingerprint remains blocked; a corrected retry can proceed only after successful observation.

## Deterministic regression

The real plugin registration harness now drives `before_tool_call` and `after_tool_call` with OpenClaw-shaped string pagination. It verifies candidate registration, success-only observation, failed-read non-observation, corrected retry allowance, and stale fingerprint rejection alongside all prior isolation/rearm/boundary tests.

## Verification

Final command results are recorded in the commit and publication handoff. No formal16 or Guava run is part of this product fix.
