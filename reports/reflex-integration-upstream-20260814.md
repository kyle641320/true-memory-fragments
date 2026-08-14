# TMF reflex upstream integration — 2026-08-14

## Result

The formal integration is rooted at parent `1518051`; initial product commit
`a52fdda` added the execution adapters. This follow-up closes the remaining
inseparable product gaps: generic Git transition calibration/hooks, safe Store
reconciliation during local warm, plugin install/removal documentation, and a
native session-start registration test.

No gateway configuration, runtime state, secrets, private repository defaults,
or external experiment data are included.

## Product surface

- Python PreToolUse hard block for stale target functions and uniquely resolved
  newly-written Python call symbols.
- One-file local re-warm through Store's guarded path and edge reconciliation.
- Function invalidation manifest producer plus optional post-checkout,
  post-commit, post-merge and post-rewrite hooks.
- Advisory, once-per-manifest SessionStart injection.
- OpenClaw `before_tool_call`/`session_start` plugin, schema, tests and linked
  installation/rollback guidance.
- Claude/Codex examples with explicit interception limits.

## Verification

- Reflex Python suite: **PASS**, 22 tests, including Git calibration.
- OpenClaw plugin: **PASS**, 4 Node tests; `npm run build` and
  `npm run typecheck` pass.
- Full repository unittest: **PASS**, 571 tests in 62.656s. Java offline verifier: **PASS**, 13 tests plus fixture and inheritance benches.
- `git diff --check`, host/private-path scan and clean-worktree check: recorded
  before publication.

## E2E collision

`test_E_call_symbol_collision_on_editing_caller` creates an isolated Git repo,
warms old cognition for `build_url(host, path)`, drifts source to a three-argument
signature, and attempts to write an old two-argument call into a fresh caller.
PreToolUse exits 2, names `build_url` and its defining `u.py`, local re-warm
reconciles only `u.py`, and retry with the current signature is allowed. The
fixture is context-managed; mutation restoration is proven by fixture removal
and final clean status of the target checkout.

## Safety boundaries

Pathless/ambiguous actions, unsupported claims, absent state and adapter/engine
errors fail open. Shell edits remain outside interception and are the
non-recursive recovery path. Git hooks are opt-in, preserve Git command success,
and must be merged with existing hooks rather than overwriting them.
