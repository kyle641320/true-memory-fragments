# Reflex design

## Contracts

The engine owns claim derivation, storage, and freshness. Adapters consume only those public facts. They must not reinterpret a stale result as semantic relevance.

The execution contract is:

1. Resolve one explicit action path and its repository.
2. Ask TMF about function claims bound to that path; for newly written Python call expressions, also check uniquely resolvable callees.
3. Block stale facts before execution.
4. Reconcile only the stale file with current source.
5. Retry and allow when fresh.

SessionStart calibration is advisory and separate: it projects a previously generated invalidation manifest into context but neither warms nor blocks.

## Safety properties

- **Hard gate:** stale actions return Claude exit 2 or OpenClaw `{block:true}` (approval mode is optional).
- **Local recovery:** re-warm replaces claims for one file; unrelated claim files are unchanged.
- **No loop:** recovery uses a non-intercepted shell/exec path, then changes the freshness predicate from stale to fresh.
- **Mutation restoration:** the E2E test snapshots and restores the test worktree; no production repository or gateway configuration is touched.
- **Conservative degradation:** absent state, unsupported claims, ambiguous paths/symbols, or engine errors allow and may warn. Safety coverage is therefore bounded, not absolute.
- **Path isolation:** the OpenClaw adapter operates only within uniquely matched configured repositories.

## Language and harness boundaries

Function precision follows engine support (currently strongest for Python). File suffix recognition is not evidence that every language has function claims. Claude's explicit file tools provide stronger interception coverage than Codex variants with pathless patches or shell-based edits. OpenClaw's adapter is tested through the actual plugin registration callbacks without installing it globally.

## Locator evidence boundary

Retrieval experiments and the execution reflex are different experiments. The prior Guava A/B v2 measured locator adoption/hits and did not put stale code actions through PreToolUse or `before_tool_call`. A locator zero-hit observation says nothing about whether the reflex blocks a collision; only the collision harness measures that path.
