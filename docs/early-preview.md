# Early developer preview: pinned source and MCP stdio

This preview targets developers and integration authors. It is not a production
write barrier. Use the exact source below; the published rc3 tag predates the
branch-freshness acceptance package even though package metadata is still rc3.

## Install the validated source

Python 3.10+ and Git are required. Commands below use a POSIX shell:

```sh
git clone https://github.com/kyle641320/true-memory-fragments.git
cd true-memory-fragments
git checkout --detach 83f6ec8ef74c5eaebfb82bda494ef9dccde6ad63
python3 -m venv .venv
.venv/bin/python -m pip install '.[java]'
.venv/bin/python scripts/demo_stale_gate.py
.venv/bin/python scripts/verify_branch_freshness.py --output /tmp/tmf-preview-freshness-new
```

Use a new output directory. Record `git rev-parse HEAD` when reporting results;
`pip show` alone cannot distinguish this snapshot from the older rc3 release.
The isolated package/install and Java preflight passed for this merged snapshot.

## Bind the server to the task worktree

Launch the installed server (not from the source checkout):

```sh
/absolute/path/to/true-memory-fragments/.venv/bin/python -m tmf.cli mcp --repo /absolute/path/to/task-worktree
```

For clients using the common `mcpServers` JSON layout, the equivalent is:

```json
{
  "mcpServers": {
    "tmf-task": {
      "command": "/absolute/path/to/true-memory-fragments/.venv/bin/python",
      "args": ["-m", "tmf.cli", "mcp", "--repo", "/absolute/path/to/task-worktree"],
      "env": {"TMF_MODEL_COMMAND": ""}
    }
  }
}
```

Client configuration locations differ. This JSON is an example, not a claim of
verified compatibility with every desktop client. For multiple worktrees use
separately named server entries with explicit absolute `--repo` paths. Automatic
branch routing is not provided by this example.

## Agent protocol

1. Call `tmf_status`; confirm `repo` equals the current task worktree. Stop using
   that server if it does not match.
2. If the index is missing, call `tmf_warm`. It writes derived data to `.tmf`, not
   source files. Limit indexing with `.tmfignore` where appropriate.
3. Use `tmf_context` or `tmf_retrieve` for the task; check returned coverage and
   anchors, then `tmf_explain` for relevant existing claim IDs.
4. On stale/unknown, do not treat old text as current evidence. Call
   `tmf_stale_slice`, actually read the indicated current source with the agent's
   file-reading tool, and resolve any gaps before editing.
5. Refresh with `tmf_warm` after understanding changes, then query again. Passing
   `path` currently checks containment; it is NOT a guarantee of single-file warm.
6. Validate the change with the project's tests. If source changes again after
   reading, recheck it; this protocol is not an atomic read/write lock.

If transport fails or the server is unavailable, disclose that fact and inspect
current source directly. Do not silently trust cached TMF output. Reconnect and
check `tmf_status.repo` before resuming TMF use. No credentials are needed for the
offline path above.

## Verified transport client

The official MCP Python SDK **2.2.0**, Python **3.13.12**, and an independently
installed TMF build of the pinned snapshot were exercised through real stdio
subprocess communication, from outside the source checkout. Negotiated protocol:
`2024-11-05`. Initialize, tool discovery, worktree binding, fresh-to-stale,
required-read output, actual file reread and refresh recovery all passed.

To reproduce using the [MCP verification script](../scripts/verify_mcp_preview.py) supplied with this guide (save it separately before checking out the pinned snapshot):
install `mcp==2.2.0` alongside the pinned TMF package, then run that script with
the same environment's Python. It creates a temporary Python fixture and talks
only through MCP; it does not import TMF service internals. The SDK is a test
client dependency, not a new TMF runtime dependency. Desktop agent UI integration
and arbitrary client versions remain unverified. The scripted reread is transport
acceptance, not a new autonomous-agent experiment.

## Feedback requested

Include source commit, Python/client versions, OS, worktree setup, expected versus
actual behavior, and a minimal sanitized reproduction. Prioritize wrong-worktree
binding, missed stale bindings, unnecessary reads, startup/refresh failures and
recovery. Do not post private source, tokens or raw private session archives.

Known limits: partial dependency modeling, extra stale-slice reading noise, no
universal write enforcement, no guaranteed zero overhead or productivity gain.
