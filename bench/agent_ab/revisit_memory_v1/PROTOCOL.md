# revisit-memory-v1 preregistration

Frozen before execution. This experiment tests code memory, not generic retrieval. Three paired sequences use `gpt-5.6-sol`, identical tasks, raw stateless broker, source tools and one-call task budgets. CONTROL rebuilds from source every session. TMF_MEMORY first reads source and persists only claim identity, text, anchors, source hashes/fingerprint, and freshness; no transcript, prompt, answer, or golden. Every revisit is a separate broker invocation and runner state.

A revisit lookup occurs only when task identity is already in that arm's first-visit memory set. Unknown identity must miss and read source. Fresh matching source-bound claims may replace repeated reading. After a held-out semantic PricePolicy change plus unrelated Inventory edit, per-file hashes mark the PricePolicy claim stale; stale evidence is never injected and the affected source file is reread. Source is authoritative; fresh is not asserted correct.

Metrics (fixed): exact required facts + citation correctness; source lines/files/bytes (and repeated values on revisits); prompt+completion tokens; latency; stale-memory trust errors; stale detection precision/recall; localized reread precision/recall; hit and adoption. TMF lookup latency is separate.

Leakage gates: broker preflight stateless; store exact allowlist only; no transcript/answers/goldens; CONTROL store absent; unknown miss/no injection; pre/post hashes recorded; stale claim blocked. Budgets symmetric (memory evidence counts toward prompt; source line cap equal).

Smoke one sequence first. Stop before pilot unless both arms valid/correct, all leakage gates pass, stale errors=0, stale recall=1, localized reread precision=recall=1. Pilot is exactly three sequences, no post-result prompt/metric changes. Product directional gate: TMF correctness >= CONTROL, fresh repeated source lines and context tokens lower; mutation stale errors no greater and reread localized. Small sample cannot prove generality.
