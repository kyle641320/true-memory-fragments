# TMF Reflex Integration

This directory turns TMF freshness facts into an execution-time safety reflex for coding agents.

## Architecture

- **TMF engine = sensory organ and freshness authority.** Function claims and `fn_hash` comparisons say whether cached cognition still matches source.
- **This integration = reflex arc and actuator.** It intercepts a concrete code action, blocks when the relevant fact is stale, and gives a localized re-warm path.
- **Locator != reflex.** Retrieval/locator answers a question by finding claims. Reflex runs on the tool execution path even when retrieval had no hit. Earlier Guava A/B experiments measured locator behavior only; their zero-hit result did **not** exercise and cannot disprove this reflex.

The integration deliberately does not duplicate the TMF engine, rank importance, infer intent, or ship external telemetry experiments.

## Components

- `hooks/pre_tool_use.py`: Claude-compatible PreToolUse stdin/exit-code adapter. `exit 2` hard-blocks stale `Read`, `Edit`, `Write`, or path-resolvable `apply_patch` actions.
- `hooks/session_start.py`: consumes invalidation manifests and injects a non-blocking suspect-cognition warning.
- `scripts/local_warm.py`: re-derives one file only, restores its claims, and verifies freshness.
- `scripts/git_calibrate.py` and `git-hooks/`: produce/refresh an invalidation manifest after Git transitions; hook failures never break Git.
- `openclaw-plugin/`: native `before_tool_call` and `session_start` adapter, with a real hook-registration harness. It never edits gateway configuration.
- `examples/`: Claude and Codex configurations. Codex coverage is inherently weaker when an action has no explicit path.

## Install

The scripts default to the TMF checkout containing this directory. An installed Python package can instead be selected with `TMF_WORKTREE=/path/to/tmf`.

### Claude Code

Copy and adapt `examples/claude-settings.example.json`. Its command assumes the target repository vendors or links this integration at `integrations/reflex`.

### OpenClaw

```sh
cd integrations/reflex/openclaw-plugin
npm install
npm test
npm run typecheck
openclaw plugins install --link .
```

Configure one or more explicit repositories. Paths are deployment parameters, never product defaults:

```json
{"enabled":true,"mode":"block","repos":[{"repoRoot":"/path/to/repo","stateRoot":"/path/to/repo/.tmf"}]}
```

Installing/enabling/restarting a production gateway is intentionally outside this repository operation.

For plugin-only guidance, including linked installation, verification and removal, see
[`openclaw-plugin/README.md`](openclaw-plugin/README.md).

### Optional Git calibration hooks

Copy or symlink the scripts in `git-hooks/` into a target repository's configured
hooks directory (`git rev-parse --git-path hooks`). They use only checkout-relative
paths and write the latest manifest under `.tmf/invalidation-manifests/` by default.
Existing hooks must be merged rather than overwritten.

## Recovery loop

1. Warm a repository with `python -m tmf.cli warm --repo /path/to/repo`.
2. Source drifts while old function claims remain.
3. A dangerous code action is intercepted and blocked with the stale function name.
4. Run:
   `python integrations/reflex/scripts/local_warm.py /path/to/repo relative/file.py`
5. Retry. Freshness now matches and the action is allowed.

`exec`/shell is not intercepted by the Python reflex, so the recovery action cannot recursively block itself. Failures, unknown symbols, unsupported languages, missing state, and path-ambiguous patches degrade conservatively to allow rather than deadlock the agent.

## Test

```sh
python -m unittest discover -s integrations/reflex/tests -v
cd integrations/reflex/openclaw-plugin && npm test && npm run typecheck
```

The Python suite includes the full old-cognition → signature drift → hard block → localized re-warm → retry allow collision and mutation-restoration checks.
