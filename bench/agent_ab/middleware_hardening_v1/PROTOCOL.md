# middleware_hardening_v1 protocol (pre-registered 2026-08-13)

Frozen mechanism-only validation. Existing layered_v1 results are retained and never regraded.

The hook runs only immediately before a concrete source `read` after the agent/tool router has selected a target. Inputs are structured target + prior navigation + source-bound store; prompt, answer, transcript and golden are forbidden. Exact repo, canonical path, session/agent namespace, branch fingerprint, and optional symbol/region identity are required. Mismatch yields MISS, or a fact-free STALE pointer only when the exact stored target changed.

Fresh means byte SHA-256 equality (not semantic equivalence). Semantic edits, rename/delete/move, dirty target changes, branch switch/reset/rebase fingerprints are stale/miss as conservatively specified. Comment/format changes are expected false-stale and their reread cost is reported. Unrelated-file edits preserve freshness only when repo/branch/target hash remain identical.

STALE withholds old facts and blocks finish/edit until successful evidence covers the stale definition/affected region. Wrong file, caller-only, partial range, failed read, and no read remain blocked. Evidence is source-authoritative.

Payload allowlist: claim id, path:line/region, freshness, provenance, non-instruction marker. No answer/prompt/transcript/golden or source text. Top3, <=1200 estimated tokens, same-round dedupe. Broker/store failure degrades to MISS; corrupt records fail closed.

Hard gates: false injection=0; unknown false hit=0; stale trust error=0; stale precision=recall=1; localized reread rate=1; fresh source binding=1; each of five genuinely different held-out sequences passes. Top1 and Top3 are fixed subtests. Agent answer correctness is independently reported and post-reread error is not a mechanism failure. Stop without tuning if any hard gate fails.
