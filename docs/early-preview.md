# Early developer preview: rc5 and MCP stdio

TMF helps coding agents detect outdated source context and retain traceable
code-chain understanding, so edits consider related callers and dependencies.

## Install the rc5 preview

Python 3.10+ and Git are required. Install the package in an isolated
environment (POSIX shell):

```sh
python3 -m venv .venv
.venv/bin/python -m pip install 'true-memory-fragments[java]==0.1.0rc5'
```

- [PyPI package](https://pypi.org/project/true-memory-fragments/0.1.0rc5/)
- [Release assets and SHA256 checksums](https://github.com/kyle641320/true-memory-fragments/releases/tag/v0.1.0rc5)
- [rc5 release notes](releases/0.1.0rc5.md)
- [rc5 MCP Registry record and live publication status](https://registry.modelcontextprotocol.io/v0.1/servers/io.github.kyle641320%2Ftrue-memory-fragments/versions/0.1.0-rc5)

The Python package version for this preview is `0.1.0rc5`. The `server.json`
manifest maps Registry version `0.1.0-rc5` to that same package and pins its Java
extra to `true-memory-fragments[java]==0.1.0rc5`. Registry publication is a separate
step after public PyPI verification; the record linked above reports its live
publication status. The explicit commands below do not depend on Registry
metadata. MCP uses the same Python package, not a separate binary. Older rc3/rc4
installation commands are superseded by the rc5 commands here.

**This installs the engine, not the Claude Code reflex.** A warmed index and MCP
connection do not register `PreToolUse`; without that separate hook the agent
must opt in to TMF queries. Follow the [reflex diagnostic and setup guide](reflex-doctor.md).
The `tmf doctor` command is included in rc5. Run it after installation and after
changing hook configuration; a successful static check is not proof that the
host fired the hook.

## Bind the server to the task worktree

With [uv](https://docs.astral.sh/uv/) installed, start the server directly:

```sh
uvx --from 'true-memory-fragments[java]==0.1.0rc5' tmf mcp --repo /absolute/path/to/task-worktree
```

For clients using the common `mcpServers` JSON layout:

```json
{
  "mcpServers": {
    "tmf-task": {
      "command": "uvx",
      "args": ["--from", "true-memory-fragments[java]==0.1.0rc5", "tmf", "mcp", "--repo", "/absolute/path/to/task-worktree"],
      "env": {"TMF_MODEL_COMMAND": ""}
    }
  }
}
```

Alternatively, use `/absolute/path/to/.venv/bin/tmf` from the isolated install
with arguments `mcp --repo /absolute/path/to/task-worktree`.
Client configuration locations differ. Use separately named server entries with
explicit absolute paths for multiple worktrees; this selects which checkout is
queried, not a limitation on supporting multiple worktrees.

## A first fresh-to-stale check

Use a disposable Git worktree with a small source file. Call `tmf_status` and
confirm its `repo`, then `tmf_warm` and `tmf_retrieve` for a function in that file.
Pass the returned claim ID to `tmf_explain`. After changing the function body,
call `tmf_explain` again: the old binding should be stale. `tmf_stale_slice`
provides reading suggestions; read the current source before refreshing with
`tmf_warm` and checking again. Keep this demonstration out of your production
working tree.

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

## rc5 public-package transport verification

The `0.1.0rc5` wheel and sdist on public PyPI match the SHA256 checksums in the
GitHub release. A fresh environment installed the version directly from
`https://pypi.org/simple`; imports resolved to `site-packages`. An engine-only
install returned the expected unarmed doctor warning and exit 1. The eight-check
installed-package reflex smoke passed without changing live Claude settings.

Real stdio verification with MCP Python SDK `2.2.0` passed initialize, tool
discovery, worktree binding, fresh/stale transitions, required-read output,
actual source reread, and refresh recovery. To check the manifest-generated
launch, use `scripts/verify_registry_launch.py` and `server.json` from the same
checkout, with `mcp==2.2.0` and `uv==0.8.22` installed, then run:

```sh
python scripts/verify_registry_launch.py
```

The Registry workflow repeats this check against the public package before
publishing metadata. These are transport and diagnostic checks, not proof of
Claude host hook dispatch, every client's UI integration, or a new autonomous
agent A/B result. The older rc4 evidence below retains its original scope.

## Historical transport verification (rc4)

The published rc4 package was exercised through real stdio with the MCP Python
SDK 2.2.0: initialize, tool discovery, worktree binding, fresh-to-stale,
required-read output, actual file reread and refresh recovery passed. Public
PyPI installation using uvx also passed. The Registry launch configuration was
separately validated in GitHub Actions on Python 3.12.

To reproduce, obtain `scripts/verify_registry_launch.py` and `server.json` from
source commit `45a5ded` together. Install `mcp==2.2.0` in a test environment and
run the script with uvx on PATH. It uses a temporary Git repository and the
public PyPI package; no live client configuration is changed. This scripted
transport check is not a new autonomous-agent experiment or proof of every
client application's UI integration.

## Feedback requested

[Submit early-preview feedback](https://github.com/kyle641320/true-memory-fragments/issues/new?template=preview-feedback.yml)
for either a successful trial or a problem. One report per workflow is enough;
no private repository access is required. For other reports, use the
[issue chooser](https://github.com/kyle641320/true-memory-fragments/issues/new/choose).

Include source commit, Python/client versions, OS, worktree setup, expected versus
actual behavior, and a minimal sanitized reproduction. Prioritize wrong-worktree
binding, missed stale bindings, unnecessary reads, startup/refresh failures and
recovery. Do not post private source, tokens or raw private session archives.

Reading suggestions are conservative, not a complete semantic dependency graph:
short same-name methods and call-shaped text can be ambiguous, and bounded
scanning can miss distant declarations. Resolve historical anchors against
current source. The protocol is not an atomic read/write lock.

In the recorded Guava comparison, development token usage was 384,389 without
TMF and 387,961 with TMF (about +0.93%); indexing cost is separate. This was a
specific task with a post-hoc source-only retry, not a general productivity
estimate.
