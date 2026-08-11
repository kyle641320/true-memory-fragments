# Round 16 — endpoint-hint packing on frozen real Java queries

## Method

Evaluated pushed HEAD `160e47f` against the repository-local stores pinned by `bench/agent_ab/java_real_v2/manifest.json`: Petclinic `58c3310e36c7d827959df6af4d64bdeb8d81f1ea` and JHipster `f8da577c944ecc4db46fc961a1ba022d5bbf8964`. The nine frozen v2 task prompts were passed directly to `McpService.tmf_context` at 3,000 and 10,000 characters. Agents were not rerun, stores were not rewarmed, and benchmark prompts, raw evidence, goldens, and reports were not modified.

An endpoint relation was counted actionable only when every role had a non-empty fresh `qualname`, repository-relative `path`, and source `anchor`. Golden-path coverage is diagnostic only: it counts distinct required citation files represented by selected endpoint hints and does not rescore the frozen benchmark.

## Packing results

| budget | queries | payload chars total / mean | relations | claims (full / stub) | actionable relations | required-path endpoint coverage |
|---|---:|---:|---:|---:|---:|---:|
| 3,000 | 9 | 25,623 / 2,847.0 | 20 | 7 (0 / 7) | 20/20 | 1/20 (5%) |
| 10,000 | 9 | 88,730 / 9,858.9 | 67 | 31 (14 / 17) | 67/67 | 8/20 (40%) |

All packed relations were actionable after Round 15, including truncated bundles. The cost is material: at 3,000 characters endpoint-bearing relations leave room only for seven claim stubs across nine queries and no full claims. At 10,000 characters relation packing remains near the cap and only 31 claims fit.

At the benchmark's 10,000-character locator budget, selected endpoint hints covered required files as follows: V2P01 2/3, V2P02 0/3, V2P03 2/2, V2J01 1/2, V2J02 2/3, V2J03 1/1, V2J04 0/2, V2F01 0/1, V2F02 0/3.

## Ordering audit

Selected order was often not query-relevant. Examples include owner pagination/test edges preceding the visit-creation event pair for V2P01, validator fixture calls for V2P02, bank-account eager-loading edges for operation creation/update queries, and unrelated exception-translator DTO field edges for V2F01. V2P01 and V2J02 nevertheless contained useful supported relations later in the 10,000-character bundle.

A candidate change to order edges by retrieval-seed rank was implemented experimentally and tested locally, then discarded. It made ordering deterministic but reduced required-path endpoint coverage from 8/20 to 4/20 because lexical seed rank itself is not a reliable proxy for relation relevance. This demonstrates a retrieval/ranking quality limitation, not a concrete deterministic packing defect with a supported safe fix. Claim-ID ordering is weak, but replacing it with seed order would be an ungrounded regression rather than a repair.

## Decision

No production or test change is retained. Evidence does not support a narrow deterministic ranking fix without introducing query-semantic scoring or changing retrieval behavior. Such work would exceed a minimal packing correction and should be evaluated separately against frozen queries.

Freshness gates, foreign-trust rejection, bounded one-hop partial semantics, and shared source-observed event candidate semantics remain unchanged. No Java/runtime/build-system inference was added.

## Frozen evidence integrity

Pre/post hashes were checked for the frozen files:

- `manifest.json`: `e6357ffaf4a41f544c4d3a76ed4b7027573cdd0a9a50dfc060bb9529d18b08d2`
- `goldens/goldens.jsonl`: `9d8d48f2cb48113d99150d4cc92c93a475809a1ad9d713851ec9226e577cf5ce`
- `REPORT.json`: `b1bcc36b55cc57e1263a55cb5a3ff2c0a59bf15b1f3e1771b35e6f0f3887bf6c`

## Verification

- Focused MCP ergonomics: 7/7 tests passed.
- Full unit suite: 520/520 tests passed.
- Java qualification aggregate: 46/46 groups passed.
- `git diff --check`: passed.
- `tools/.javac-helper-build/` remains untracked and untouched.

## Limitations

This is deterministic presentation analysis over nine Spring-centric prompts and two existing stores. Required-path coverage is a conservative usefulness proxy, not answer correctness or agent adoption. Endpoint hints can point to useful non-golden context, and absence from hints does not mean the corresponding claim or source fact is absent from TMF. No causal latency, reread, or correctness gain is claimed because agents were intentionally not rerun.
