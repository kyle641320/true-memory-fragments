# Read-only locator compatibility (candidate)

This entry point preserves the legacy locator launch contract:

```sh
tmf mcp --repo /absolute/worktree --state-root /absolute/state
```

`--state-root` (or `TMF_STATE_ROOT`) selects the read-only locator. Explicit
`--read-only` without a state root reads the selected repository's `.tmf`.
Without these options, the existing experimental MCP entry point is unchanged.

The locator retains the nine legacy tool input schemas and adds
`tmf_stale_slice`. It does not expose warm, refresh, or write tools. Assist is
optional and requires an explicitly configured provider.

## State handling

The authoritative JSON claims and schema marker must already exist. A
service-local in-memory search index is constructed from them; disk SQLite and
WAL files are not opened or migrated. Missing, unsupported, corrupt, or
inconsistently read state produces an error, not an automatic rebuild. Protocol
requests check for external JSON updates. Source remains authoritative.

Legacy module-top-level records are retained rather than discarded. Legacy
source-binding checks apply only to records loaded as legacy by this explicit
locator path. Records with current derivation-version metadata keep current
version checks.

## Deliberate differences

Lexical retrieval uses current ranking and cross-path diversification, so the
top results need not have the same order or membership as the old locator.
Schema compatibility is not a promise of byte-identical responses. Validate
representative queries for the intended workflow before switching.

The locator conservatively reports `warm_complete=false` and partial coverage;
it does not certify whole-repository coverage from legacy JSON alone.
Freshness hints are not an enforced write barrier.

## Upgrade gate

Keep the old environment and launch configuration available for rollback.
First validate the installed candidate outside its source checkout against a
copy of the existing state: tool schemas, queries, stale behavior, and unchanged
source/state fingerprints. Then validate the actual client registration after
switching. A standalone SDK test does not prove that a running client switched.
This document describes a compatibility candidate, not a completed live upgrade.
