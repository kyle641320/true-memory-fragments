# Verify Claude Code reflex arming

**Installing TMF, warming an index, configuring MCP, or loading usage rules does
not register a reflex hook.** Without a host hook, TMF remains opt-in memory:
the agent must remember to query it. Engine installation and reflex arming are
separate deployment states.

`tmf doctor` is available in source checkouts containing this change. It is not
part of the already published rc3/rc4 wheels; install the updated source in your
chosen environment before using these commands.

## Post-install check

After installing TMF and setting up the intended task repository, run:

```sh
tmf doctor --repo /absolute/path/to/task-repo
tmf doctor --repo /absolute/path/to/task-repo --json
```

From a source checkout, `python -m tmf.cli doctor --repo ...` is equivalent.
The default repository is the current directory. No model, network request,
warm, settings write, or configured hook execution is involved.

When the hook is absent, the command exits **1** and explicitly reports:

```text
reflex NOT armed — operating as opt-in memory
```

Exit **0** means a supported, statically recognized registration covers Claude's
`Read`, `Edit`, and `Write` tools. It does **not** prove that the host loaded or
fired the hook. JSON always includes `runtime_verified: false`.
Disabled, malformed, incomplete, or unverifiable configurations return 1;
the report lists checked locations, findings and setup guidance.

## What is checked

- User settings: `~/.claude/settings.json`, or
  `$CLAUDE_CONFIG_DIR/settings.json` when the config directory is overridden.
- Project settings: `<repo>/.claude/settings.json`.
- Project-local settings: `<repo>/.claude/settings.local.json`.
- TMF command hooks under **PreToolUse**, their matcher coverage, and the
  referenced hook script. A `SessionStart` hook, unrelated command, or mention
  of the filename is not sufficient.
- `disableAllHooks`, with local settings taking precedence over project
  settings, which take precedence over user settings.

The check recognizes direct Python launches of the shipped
`integrations/reflex/hooks/pre_tool_use.py` layout. It deliberately does not
evaluate arbitrary shell wrappers. It does not inspect a running host's
command-line overrides, managed policy, plugin activation, or trust decisions;
confirm these in Claude Code. See the official
[hook configuration reference](https://code.claude.com/docs/en/hooks#hook-locations)
and [settings precedence](https://code.claude.com/docs/en/settings#settings-precedence).
This command diagnoses Claude settings, not an OpenClaw plugin installation.

## Arm the hook explicitly

1. Obtain the integration from a TMF source checkout; the engine-only wheel
   does not install the `integrations/` directory into a target repository.
2. Merge the [example configuration](../integrations/reflex/examples/claude-settings.example.json)
   into an appropriate Claude settings file. Preserve existing hooks. The
   example assumes the **whole** `integrations/reflex` directory is available
   under the task repository. Alternatively, use absolute paths to your TMF
   checkout and its Python interpreter. Quoting paths matters for spaces.
3. Re-run `tmf doctor --repo /absolute/path/to/task-repo`.
4. In Claude Code, inspect `/hooks` and verify the intended registration. On a
   disposable warmed repository, confirm a fresh supported action is allowed,
   then change a tracked function and confirm the stale action is blocked.
   A static doctor result alone is not runtime enforcement evidence.

TMF does not edit Claude settings, install hooks, restart a host, or change
gateway configuration on your behalf.

## Regression and experiment boundary

```sh
python tools/verify_reflex_arming.py
python tools/verify_reflex_arming.py --python /path/to/installed-venv/bin/python
```

The offline smoke constructs its own temporary Git repository and Claude
settings. It warms the engine, verifies both fresh and mutated **unarmed**
states report failure, registers the real hook, verifies fresh allow and stale
block by direct hook invocation, then disables/removes the registration and
checks the warning again. It also checks that doctor leaves the fixture
unchanged. The `--python` form verifies imports come from the installed wheel,
not the source checkout. CI covers source and installed-package paths.

Historical `fresh_revisit` / `mutation_revisit` results describe behavior with
evidence supplied by their harness. They do not measure whether Claude settings
were armed or whether an unprompted agent would consult an unarmed engine. This
new smoke detects the deployment gap; it is **not** a new autonomous-agent A/B
result. Future host-level experiments should record both the doctor report and
actual hook firing, and report an engine-only/unarmed control separately.
