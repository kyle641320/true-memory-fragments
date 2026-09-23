# Verify Claude Code reflex arming

**Installing TMF, warming an index, configuring MCP, or loading usage rules does
not register a reflex hook.** Without a host hook, TMF remains opt-in memory:
the agent must remember to query it. Engine installation and reflex arming are
separate deployment states.

`tmf doctor` was introduced in **0.1.0rc5** and is included in **0.1.0rc6**.
Older rc3/rc4 wheels do not include it; upgrade the engine in your chosen
environment before using these commands. See the [installation guide](early-preview.md).

**Java coverage fix (rc6):** the published rc5 hook selected
only Python `scope="function"` claims. Java methods use `scope="class"` with a
`role="declaration"` binding, so registration could pass while the hook checked
zero methods. The rc6 source distribution includes the updated hook and
selector, and the rc6 engine includes the updated doctor. Merely upgrading the engine wheel
does not update an existing integration copy.

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
`Read`, `Edit`, and `Write` tools and passes the static Python/Java capability
checks for the inspected repository. It does **not** prove that the host loaded
or fired the hook, that its interpreter has the parser installed, or that its
cache covers every source node. JSON always includes `runtime_verified: false`.
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
- Bounded source-filename inspection for Python/Java file coverage. Nested
  projects are included; reported metadata/dependency exclusions are not
  inspected. An incomplete scan cannot establish an armed result. Other known
  source languages are explicitly reported as unverified, not protected.
- On Java repositories, each required tool needs a hook with the supported
  Java capability declaration and selector linkage. A recognized legacy
  function-only file filter fails this check even if someone appends a Java
  capability marker. Registration remains separately visible in the report.

These are **static compatibility checks, not execution proofs**. A capability
literal and recognizable selector shape cannot prove arbitrary configured code
is correct. Doctor never imports or executes that code. Use the behavioral
smoke below, then verify actual dispatch in the host.

The check recognizes direct Python launches of the shipped
`integrations/reflex/hooks/pre_tool_use.py` layout. It deliberately does not
evaluate arbitrary shell wrappers. It does not inspect a running host's
command-line overrides, managed policy, plugin activation, or trust decisions;
confirm these in Claude Code. See the official
[hook configuration reference](https://code.claude.com/docs/en/hooks#hook-locations)
and [settings precedence](https://code.claude.com/docs/en/settings#settings-precedence).
This command diagnoses Claude settings, not an OpenClaw plugin installation.

## Arm the hook explicitly

1. Obtain the integration from an updated TMF source checkout or source
   distribution. The engine-only wheel does not install the `integrations/`
   directory into a target repository.
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

For Java, install the matching engine's `[java]` extra in the hook interpreter,
update the **whole** integration (including `scripts/claim_selection.py` and
`local_warm.py`), and warm the target repository. Upgrading only the engine or
copying only the hook file can leave the integration incomplete.

The file gate checks Python function nodes and Java direct syntactic declaration
nodes (including methods, constructors, types and fields), using production
freshness checks. Java type spans include their member bodies: a method edit
can correctly stale both that method and its enclosing type, but an unchanged
sibling method is not reported stale. A direct Java declaration enriched with
entity dependencies is checked through a non-mutating projection of its own
declaration binding, not dropped because it has multiple bindings. A local
`fresh` result does not assert that those external dependencies are fresh.
Multi-file relationship claims are not part of this local-file gate.
Python new-call detection is separate; Java
cross-file discovery of newly written calls is **not implemented**.

No eligible claims, unsupported source languages and missing state are not
freshness measurements. The hook retains its nonblocking fallback but emits an
explicit warning/reason rather than `fresh`. Local re-warm uses the same node
selector and cannot report `all_fresh_now=true` after verifying zero claims.

TMF does not edit Claude settings, install hooks, restart a host, or change
gateway configuration on your behalf.

## Regression and experiment boundary

```sh
python tools/verify_reflex_arming.py
python tools/verify_reflex_arming.py --python /path/to/installed-venv/bin/python
python tools/verify_reflex_arming.py --require-java
python tools/verify_reflex_arming.py --python /path/to/installed-java-venv/bin/python --require-java
```

The offline smoke constructs its own temporary Git repository and Claude
settings. It warms the engine, verifies both fresh and mutated **unarmed**
states report failure, registers the real hook, verifies fresh allow and stale
block by direct hook invocation, then disables/removes the registration and
checks the warning again. It also checks that doctor leaves the fixture
unchanged. The `--python` form verifies imports come from the installed wheel,
not the source checkout. CI covers source and installed-package paths.

With the Java parser available, the smoke also derives real Java method claims,
asserts FRESH at T0, mutates one method, asserts STALE with an unchanged control,
and verifies Read/Edit/Write block with the correct binding identities. It then
checks local re-warm restores coverage and a legacy Java-blind hook is rejected
by doctor. Core-only installations report the Java behavioral checks as skipped;
`--require-java` turns parser absence into failure. CI requires Java checks for
source, installed Java wheel, and extracted source-distribution integration.

Historical `fresh_revisit` / `mutation_revisit` results describe behavior with
evidence supplied by their harness. They do not measure whether Claude settings
were armed or whether an unprompted agent would consult an unarmed engine. This
new smoke detects the deployment gap; it is **not** a new autonomous-agent A/B
result. Future host-level experiments should record both the doctor report and
actual hook firing, and report an engine-only/unarmed control separately.
