# OpenClaw plugin

This adapter registers TMF's `before_tool_call` hard gate and advisory
`session_start` calibration without changing gateway configuration.

## Build and test

```sh
npm ci
npm test
npm run build
npm run typecheck
```

## Linked install

From this directory:

```sh
openclaw plugins install --link .
```

Configure `plugins.entries.tmf-reflex.config.repos` with explicit `repoRoot`
and optional `stateRoot` values; see the parent README. Then use the normal
OpenClaw plugin inspection/configuration workflow for the installed version.
Restarting or editing a production gateway remains a deployment decision.

## Remove / rollback

Use OpenClaw's supported plugin removal workflow for the installed plugin ID
`tmf-reflex`, or remove the linked entry through the same configuration manager
that created it. Do not delete source files as an uninstall mechanism. Preserve
and restore a configuration backup if deployment policy requires rollback.

## Boundaries

Pathless/ambiguous actions, missing state, engine failures and unsupported
claims fail open. Repository routing requires exactly one configured match.
No telemetry, credentials, runtime ledgers or machine-specific defaults ship in
this package.

## Recovery Read lifecycle

Once a stale collision is pending, an exact recovery `read` is not treated as a
normal dangerous retry. `before_tool_call` first verifies the canonical stale
path, anchor coverage, unchanged source blob, and current localized TMF warm;
it then registers a candidate and allows the Read to execute. Only a successful
matching `after_tool_call` promotes that candidate to an observation. Failed or
missing results never unlock the edit.

OpenClaw lifecycle payloads can carry `offset` and `limit` as either integers or
decimal strings. Both representations are normalized with the same strict
positive-integer policy; fractional, negative, and malformed values do not
cover an anchor. When TMF cannot provide a reliable symbol anchor, the plugin
requires a demonstrable whole-file Read: line 1 plus no limit, or a positive
limit at least as large as the current file's line count. This preserves the
conservative boundary without rejecting OpenClaw's normal `offset: 1,
limit: 2000` whole-file request.
