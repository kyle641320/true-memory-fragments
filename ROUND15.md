# Round 15 — actionable endpoint hints for bounded static relations

## Diagnosis from real-agent A/B v2

The frozen `bench/agent_ab/java_real_v2/` evidence shows that TMF_MAP did not reduce mean latency or source rereads overall. In particular, V2J03 TMF_MAP used 11 tool calls and reread 539 lines before producing an answer from two files; several other TMF arms reread as much or more source than SOURCE_ONLY. The context presentation contributed a concrete adoption blind spot: fresh one-hop relations contained only opaque endpoint claim IDs. If an endpoint claim did not fit in the independently packed `claims` list, an agent could not turn the relation into a symbol or source read without another lookup or broad search.

This is a presentation defect in an already-supported, statically proved capability. It does not require new Java inference, runtime Spring semantics, build resolution, or dynamic-dispatch guesses.

## Minimal implementation

`tmf_context` relations now include `endpoint_hints`, keyed by the existing endpoint role (for example `caller_id` / `callee_id`). Each hint is derived only from the endpoint claim already required to exist and contains:

- `qualname`
- repository-relative `path`
- the endpoint claim's existing source `anchor`

The hints are retained in the compact relation representation used when a context bundle is truncated. A relation is eligible only when both the edge and every endpoint claim are fresh and locally trusted; an independently stale or foreign endpoint cannot be repackaged as an actionable hint. Existing endpoint IDs, edge IDs, relation budgets, partial-coverage labels, and event-candidate semantics are unchanged. No chain is inferred and no source behavior is asserted beyond the stored fresh edge.

## Focused verification

`tests/test_mcp_ergonomics.py` now verifies that:

- fresh call relations expose role-aligned endpoint hints with actionable names and paths;
- truncated context still retains endpoint hints, so relations do not regress to opaque IDs under the common bounded-payload path.
- an independently stale endpoint claim suppresses the relation hint even when the edge claim itself remains fresh.

A pinned real JHipster locator smoke at the frozen v2 commit confirmed that truncated relation entries now carry exact source anchors such as `OperationRepository.findAllWithEagerRelationships` at `OperationRepository.java:24` and its statically resolved callee at line 38.

## Remaining limitations

- Endpoint hints make a selected relation actionable; they do not improve lexical seed relevance or relation ranking.
- Relations remain bounded, one-hop, partial, and freshness-gated. Missing or unresolved edges are not guessed.
- Hints can consume enough payload budget to reduce the number of packed relations or claims. This is an explicit precision-over-volume tradeoff and remains bounded by `max_chars`.
- The frozen benchmark, prompts, goldens, raw answers, and report were not changed or rerun, so no causal latency or adoption gain is claimed.
