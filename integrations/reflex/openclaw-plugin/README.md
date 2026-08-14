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
