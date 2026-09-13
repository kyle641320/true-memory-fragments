# MCP directory publishing preparation

Status: preparation only. TMF has not been published to the official MCP Registry
or Smithery by this change. This change does not release a package, replace an
installed service, or enable automatic publication.

## Shared description

TMF records source-linked understanding of code calls, reads, writes and
dependencies. It detects when source changes make remembered context stale and
provides reread locations, helping coding agents consider upstream/downstream
impact rather than only the code being edited. MIT-licensed developer preview.

## Official MCP Registry: PyPI route

Reserved publication target (not a claim of registration):
`io.github.kyle641320/true-memory-fragments`.

The [official package guide](https://modelcontextprotocol.io/registry/package-types)
requires the PyPI package description to contain the matching `mcp-name:` string.
The hidden marker in the root README supplies it for **future builds**. Editing
GitHub's README does not change an already-published PyPI description.

At the 2026-09-13 check:

- PyPI latest was `0.1.0rc3`; its description did not contain the ownership marker.
- Repository package metadata was `0.1.0rc4`, not yet on PyPI.
- Registry namespace search returned no servers for `io.github.kyle641320`.
- GitHub releases had rc2/rc3 wheels and sdists, but no MCPB assets.

Before publishing directory metadata:

1. Build from the reviewed release commit containing the marker. Use the existing
   release preflight and installed-wheel compatibility checks.
2. Inspect the built wheel METADATA and sdist README for the exact marker. Publish
   that verified version through the existing release/PyPI process; verify its
   description on PyPI. Never point an rc4 listing at rc3.
3. Prepare `server.json` using the current official schema, the matching namespace
   and exact PyPI version. The package name is `true-memory-fragments`, but its
   executable is **`tmf`**. Do not assume a registry client's default binary name
   matches the distribution name.
4. Verify the rendered client launch command from outside the source checkout,
   including `mcp --repo <absolute-task-worktree>`. Exercise actual MCP initialize,
   discovery, status and freshness behavior. Specify Java extras if Java support
   is advertised. Choose the normal indexing mode or explicit read-only locator
   mode deliberately; do not silently change existing locator semantics.
5. Authenticate the namespace using the official publisher's supported method,
   then publish and retrieve the exact version from the Registry API. Schema
   validation alone is not proof of installability or successful registration.

See [official publisher quickstart](https://modelcontextprotocol.io/registry/quickstart).
No authentication secrets or device codes belong in issue bodies or reports.

## Smithery: local distribution

[Smithery's publishing guide](https://smithery.ai/docs/build/publish) supports local
stdio servers via pre-built MCPB bundles as well as remote HTTP servers. Use the
local route for this evaluation: TMF does not need to become a hosted service to
be listed.

Prepare and validate an MCPB with explicit worktree configuration, the intended
TMF release and its runtime/dependencies. Verify clean installation and real MCP
queries before publishing. Include source-linked context and freshness behavior
in the description, not a promise of complete dependency resolution or automatic
bug prevention. No MCPB is built or submitted by this documentation change.

## Publication receipts

Keep version, source commit, artifact checksum, directory URL and verification
results together. A submitted listing is not editorial endorsement. Existing
user state, installed services and frozen experiment artifacts are not inputs to
publish; use isolated fixtures for validation.
