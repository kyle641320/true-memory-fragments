# cognitive_continuity_v2 prospective protocol

This is a new held-out second-read experiment. It does not regrade v1. One logical cognitive subject is the pair `logical_agent_id` + `workflow_id`; both arms receive the same identifiers and provenance markers. The minimal envelope contains completion, claim IDs, and source-bound provenance only: no source, answer, prompt, golden, or transcript (no transcript replay).

Phase A is a controlled autonomous Agent search/read task. Only paths actually read may enter derivation. The runner calls the authoritative `derive_claims_for_path(GitRepo, path)`, persists every result through `Store.put_claim`, and records claim ID, scope/type, anchors, bindings, and source hash. Agent answers, prompts, and transcripts are never claims. A missing Store fact stays a miss.

In phase B, SOURCE receives no claims. TMF middleware retrieves only fresh persisted Store claims selected from phase-A tool-trace path/symbols. Freshness requires current source hashes. After a real semantic mutation, old facts are withheld and localized read is mandatory. Broker calls may be stateless: persistence is the explicit cognitive layer.

## Prospective gates

`validate.py` must PASS before model execution and freezes tasks, goldens, and fixture tree. Understanding goldens execute deterministic fixture oracles. Edit/test fixtures fail initially and pass after the asserted target diff. Semantic mutations change oracle output where an oracle exists and invalidate old source bindings. Smoke is B01 understanding plus B03 mechanical edit. Full (B01–B10, Python+Java, understanding/edit/cross-file/test-fix, fresh/semantic/unknown/unrelated) is allowed only if smoke has two valid pairs and at least one machine-qualified adoption.

Adoption requires phase-B correctness/tests, a fresh injected claim whose coverage oracle contains the needed fact or anchor, and no reread of that covered region. Reduced reading alone is not adoption. Metrics: repeat reads/bytes/lines, success/citations/tests, coverage/adoption, estimated tokens, wall time; failure attribution is memory-caused, stale-memory, post-reread, baseline, output-contract, runtime, or mechanism. Product passage requires non-decreasing fresh success, stable adoption, directional repeat-read or total-cost reduction, and non-decreasing semantic safety. Small-N findings remain directional.
