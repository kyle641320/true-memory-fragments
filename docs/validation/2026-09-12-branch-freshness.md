# Branch freshness and controlled Guava continuation

## Scope

This change packages existing source-freshness behavior for review. It does not
introduce a new freshness engine or a universal write barrier. The production
change excludes the queried endpoint from routing destination counts, preserving
edge provenance. Deterministic routing fixtures cover forward and reverse calls;
async and override checks are classifier unit tests only.

The candidate engine Python files were byte-compared with the engine used in the
September 11 acceptance runs: no differences after selecting the routing fix.
Unrelated session-recovery integration changes and historical task artifacts are
intentionally excluded.

## Reproduce the deterministic acceptance

Install this checkout with the Java extra (`python -m pip install -e '.[java]'`).
With Git available, run from the repository root:

```sh
python scripts/verify_branch_freshness.py --output /tmp/tmf-freshness-new-run
python -m unittest discover -s tests
```

The output directory must not exist. The script creates isolated Git worktrees,
retains old indexes across changes, calls the actual Python service API, and
writes raw responses, Git observations, source hashes and assertions to
`result.json`. It exits nonzero on failure. No model calls are required.

Checks cover same-path differences across branches, bound parent changes,
unrelated fresh content, uncommitted changes, switching to an old revision,
fast-forward integration, incremental refresh, engine protection and four stale
API responses. This is a direct service API test, not an online MCP transport test.

## Controlled Guava observation (historical, not rerun here)

A single continuing agent session read Guava revision
`94f39958baf7ad51ddf9c70e406ed6b188194daa`, then resumed after the controller integrated
upstream revision `a8adf77c0eddafde7e3646c6fa0083d72a6b6f64` (PR #8609).
The two old method bindings for `combineOrdered` and `combineUnordered` returned
stale (`java_hash mismatch`). Tool records showed actual current-source reads
before a new regression test was written. The test reported 60 checks twice;
the controller reran the compiled test successfully. Production source was not
modified. These are assertions in one task, not 60 independent experiments or a
pre-registered independent scoring oracle.

The agent followed a fixed query/reread protocol, was supplied binding IDs, and
used a two-file index through a direct Python helper. The controller integrated
upstream code; it was not a second autonomous developer. The raw session archive
is not distributed in this repository. This paragraph records a bounded observed
result, not a claim that an outside reviewer can reconstruct the agent transcript
from this PR alone.

## Limits and follow-up

- Fresh means matching the selected worktree, not globally newest across branches.
- Only modeled and bound dependencies are covered.
- The Guava stale slice requested extra apparently unrelated methods; minimal
  rereading and zero overhead are not established.
- Automatic worktree routing, online MCP, universal write enforcement and changes
  occurring between read and write were not validated.
- Static repair comparisons do not establish a speed or token advantage.

These limits do not turn a successful bounded freshness test into a production
reliability claim. Slice relevance and host integration belong in separate work.
