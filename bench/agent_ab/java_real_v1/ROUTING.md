# TMF routing for `java_real_v1`

## Diagnosis

The exposed OpenClaw tool `zhihu-yanxuan-tmf__tmf_context` is not cwd-sensitive. Its MCP registration in `/root/.openclaw/workspace/config/mcporter.json` starts:

```text
python3 -m tmf.cli mcp --repo /root/.openclaw/workspace/repos/zhihu-yanxuan-workflow
```

with the frozen TMF checkout as `cwd`/`PYTHONPATH`. `tmf.cli cmd_mcp` passes that single `--repo` to `mcp_server.serve`; `McpService` owns one `GitRepo`/`Store`. Tool schemas intentionally have no per-call repo/state-root argument. Therefore invoking that registered tool while an agent happens to be in Petclinic cannot change stores. The observed Zhihu anchors are expected for this registration, not Petclinic cache contamination.

Source audit also confirms that `Store.root` is always `<repo>/.tmf`; there is no independent state-root option. Supported repo selection is startup/CLI-level:

- MCP: `python3 -m tmf.cli mcp --repo <repo>` (one repo-pinned process)
- CLI: `python3 -m tmf.cli retrieve ... --repo <repo>`
- in-process read-only locator: instantiate existing `McpService(<repo>)`

No global gateway/MCP config was changed and nothing was restarted.

## Experiment route

`petclinic_tmf_locator.py` is an experiment-only wrapper around the existing `McpService`. It:

1. reads the Petclinic path and commit from frozen `manifest.json` (no task/golden path seeding);
2. refuses to run if `HEAD` differs from `58c3310e36c7d827959df6af4d64bdeb8d81f1ea`;
3. binds the existing service directly to that checkout and its repository-local `.tmf`;
4. accepts a natural-language question and emits the normal deterministic `tmf_context` payload.

This changes routing only, not parser, build adapter, freshness, retrieval, or claim semantics.

## Warm and smoke result

The Petclinic store was warmed through the existing CLI. Result: `warm_complete=true`, 1,071 claims, sampled freshness 20/20. Four natural questions from the manifest were queried. Every response contained Petclinic `src/...` paths and zero Zhihu/script/config paths. Machine-readable evidence is in `routing_smoke.json`.

## Exact TMF_MAP invocation

From any cwd:

```bash
python3 /root/.openclaw/workspace/worktrees/tmf-java-nodes-step0/bench/agent_ab/java_real_v1/petclinic_tmf_locator.py \
  'Locate the complete Java path for booking a visit through publication and consumption.' \
  --max-chars 12000
```

For an A/B agent, replace the quoted string with the task's natural `prompt` from `manifest.json`; provide the returned `result` as the TMF_MAP locator observation, then inspect cited source normally. Do **not** call `zhihu-yanxuan-tmf__tmf_context` for this arm.

Optional preflight:

```bash
python3 /root/.openclaw/workspace/worktrees/tmf-java-nodes-step0/bench/agent_ab/java_real_v1/petclinic_tmf_locator.py --status
```

Optional re-warm (writes only repository-local `.tmf`):

```bash
python3 /root/.openclaw/workspace/worktrees/tmf-java-nodes-step0/bench/agent_ab/java_real_v1/petclinic_tmf_locator.py --warm
```

An alternative is a separately registered MCP instance using `tmf.cli mcp --repo <petclinic>`, but that requires global registration/reload and was deliberately not performed.
