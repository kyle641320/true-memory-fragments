# Round 12 — retrieval presentation and bounded graph expansion

## Boundary

This slice changes retrieval/presentation only. It adds no Java/Spring runtime semantics, no event-chain inference, no parser/build-system work, and no repository-specific symbols, paths, or query rules. The algorithm is language/provider neutral. Public MCP fields are additive and existing tools/signatures remain compatible.

## Changes

- `retrieve_text` now deterministically round-robins a bounded scored pool by source path. This prevents repeated file/class/method/contract claims from one source file consuming the first screen while preserving lexical rank as the path ordering signal.
- `tmf_context` performs a strict one-hop, bounded expansion from returned seed claims over existing fresh `calls`, `reads`, `writes`, `uses_type`, `inherits`, and `overrides` edge claims.
- Relation payloads identify edge id, exact endpoints, anchor, partial coverage, and unresolved count. No edge is synthesized and no sequence is called a runtime/event chain.
- Stale, unverified-foreign, or unresolved-endpoint edges fail closed. Ambiguous name addressing continues to return candidates rather than guessing.
- Context packing reserves compact relation evidence under tight budgets; budget is 3 edges at the default 3000 chars and 8 at larger contexts.

## Verification

- Directed: `python -m unittest tests.test_java_retrieval_ranking tests.test_mcp_ergonomics tests.test_final_contracts` — 13 passed.
- Full: `python -m unittest discover -s tests -q` — 503 passed.
- Real pinned E2E: `petclinic_tmf_locator.py` against commit `58c3310...`, frozen P01 prompt, 3000 chars — valid JSON, 3 claims + 3 one-hop relations, 2706 chars; paths include `VisitScheduler.java` and `VisitBooked.java`.

## Frozen P01–P04 offline ablation

Method and rows are in `bench/agent_ab/java_real_v1/ROUND12_ABLATION.json`. Frozen prompts were retrieved unchanged without seeded Java symbols/paths; goldens were loaded only afterward for scoring.

- Baseline mean MRR from `RETRIEVAL_DIAGNOSIS`: `(0 + .333 + .5 + 1) / 4 = .458`.
- Round 12 mean MRR: `.579`.
- First key anchor: P01 absent → rank 2; P02 remains rank 1; P03 remains rank 1; P04 remains rank 1.
- First-screen path diversity: 8 distinct paths for each frozen prompt at 3000 chars. P01 is no longer occupied by repeated `Visit.java` claims.
- P02 improves from MRR `.333` to `.567`; P03/P04 do not regress.

## What the existing graph now buys

Without new extraction semantics, fresh static edges already expose useful local blast-radius evidence: calls between booking/controller/scheduler/roster methods, readers/writers of declarations, and Java type users. The presentation now makes those edges visible directly from natural-language top claims and carries their partial-coverage/unresolved boundary.

## Static edges still missing

P01 still does not retrieve `VetEventListener.java` as a scored key anchor (MRR `.25`, not full recall). The store has no justified static publication → event type → listener-consumption edge for this application event flow, so strict one-hop expansion cannot manufacture it. This remains a static graph/extraction gap; resolving it later must model source-observed publication/subscription evidence without claiming Spring runtime ordering or delivery semantics.

No commit or push was made.
