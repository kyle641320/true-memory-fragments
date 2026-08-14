# TMF reflex cognition dual-gate acceptance — 2026-08-14

## Summary
Implemented the session-scoped cognition-closure dual gate for `integrations/reflex`.

A native stale collision no longer becomes safe merely because TMF storage has been warmed. A matching dangerous retry is allowed only after both gates pass:

1. local warm/reconciliation confirms the stale source path is current for the recorded blob; and
2. the same OpenClaw session observes a successful `Read` of the exact stale path/anchor through `after_tool_call`.

The fix addresses the v3 smoke finding: **TMF state fresh != agent cognition refreshed**.

## Implemented behavior
- Structured collision payload from `pre_tool_use.py` with collision id, repo/state root, blocked action fingerprint, blocked target, stale paths, anchors, current source blobs, and recovery commands.
- `local_warm.py` emits machine-stable JSON with path/status/blob fields.
- OpenClaw plugin pending store scoped by session identity and repo/state root.
- `before_tool_call` creates/maintains pending collisions; `after_tool_call` marks observation only on successful exact `read`.
- Warm without read keeps blocking with `need_read`.
- Read failure, wrong file, partial anchor, source change after observation, missing source, identical stale retry, session/repo leakage, batch edit payloads, shell/pathless fail-open boundaries, TTL and cleanup are covered by tests.

## Deterministic lifecycle coverage
The plugin harness exercises the production lifecycle registration (`before_tool_call`, `after_tool_call`, `session_end`) and verifies:
- stale dangerous edit -> native block + pending collision;
- warm fresh but no Read -> matching retry remains blocked;
- exact successful Read -> corrected retry may proceed;
- identical stale retry remains blocked;
- source change after Read re-arms the collision;
- unrelated benign action is not globally locked;
- shell/pathless actions cannot unlock pending cognition state.

## Verification
- `npm test` in `integrations/reflex/openclaw-plugin`: 14/14 PASS
- `npm run build`: PASS
- `npm run typecheck`: PASS
- `python3 -m unittest discover -s tests -q`: 571/571 PASS
- `python3 -m unittest discover -s integrations/reflex/tests -q`: 23/23 PASS
- `bash scripts/verify_java_offline.sh`: PASS
- `git diff --check`: PASS

## Boundaries
- No model smoke, formal pilot, or Guava experiment was executed in this change.
- Shell/pathless/ambiguous operations remain documented fail-open boundaries and cannot unlock a pending collision.
- A future model smoke/formal experiment must be separately authorized after this product fix.
