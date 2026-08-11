# Round 17 — deterministic query-aware relation-ordering evaluation

## Decision

No production or unit-test change is retained. None of the six conservative query-aware candidates clears the hard 10,000-character required-path coverage gate (current accepted Round 16 reference: 8/20), so changing `tmf/mcp_server.py` would be unsupported. The best candidate improves the present 3k diagnostic from 2/20 to 4/20 but reaches only 7/20 at 10k and reduces packed claims from 31 to 27; this is not a non-regressive acceptance result.

## Offline harness

`reports/java-relation-ordering-round17/evaluate_ordering.py` evaluates all nine frozen v2 prompts against the manifest-pinned Petclinic/JHipster repository commits. It copies each repository and its existing `.tmf` store to a temporary directory, performs a fixed read-through stabilization pass there, then evaluates twice without modifying source repositories or frozen benchmark evidence. Output is `results.json`.

Candidates reorder only relations admitted by production `_bounded_relations`, which already requires an existing supported one-hop edge, fresh locally trusted edge claim, fresh locally trusted endpoint claims, and actionable endpoint hints. Candidate features are lexical query tokens intersected with either (a) endpoint field names, qualnames, paths and anchors or (b) those hints plus existing static edge/endpoint claim text. Strategies are stable full-overlap ordering and conservative >=2 / >=3 overlap partitions. No model, runtime Spring semantics, build resolution, dispatch inference, or golden label enters ranking. Golden required paths are loaded only after packing for evaluation.

## Aggregate metrics

All payloads are within budget, all packed relations are actionable, and two isolated runs produced byte-identical JSON (`458e0a87466835540444fe98b55078f20df06d82222c0fe1745982e2eaab1ab0`).

| strategy | 3k paths | 3k chars / rel / claims | 10k paths | 10k chars / rel / claims (full/stub) |
|---|---:|---:|---:|---:|
| production baseline | 2/20 | 25,757 / 21 / 3 | 7/20 | 88,503 / 66 / 31 (13/18) |
| full overlap, hints | 3/20 | 25,724 / 21 / 3 | 6/20 | 88,157 / 66 / 26 (14/12) |
| >=2 partition, hints | 3/20 | 25,621 / 21 / 3 | 6/20 | 88,456 / 66 / 27 (14/13) |
| >=3 partition, hints | 2/20 | 25,809 / 21 / 3 | 7/20 | 88,232 / 66 / 29 (13/16) |
| full overlap, trusted text | **4/20** | 25,604 / 21 / 3 | 7/20 | 88,172 / 66 / 27 (14/13) |
| >=2 partition, trusted text | 2/20 | 25,757 / 21 / 3 | 7/20 | 88,503 / 66 / 31 (13/18) |
| >=3 partition, trusted text | 2/20 | 25,757 / 21 / 3 | 7/20 | 88,503 / 66 / 31 (13/18) |

The last two candidates are effectively the baseline on this corpus. Full trusted-text overlap adds V2P01 and V2P03 coverage at 3k, and V2P02 at 10k, but loses V2J02 at 10k and packs four fewer claims. Hints-only full overlap also loses V2J02 and does not recover V2P02.

## Per-query required-path coverage (baseline → best observed candidate)

“Best observed” is full trusted-text overlap; it has the highest 3k coverage, not an accepted production winner.

| query | 3k baseline → candidate | 10k baseline → candidate |
|---|---:|---:|
| V2P01 | 0/3 → 1/3 | 2/3 → 2/3 |
| V2P02 | 0/3 → 0/3 | 0/3 → 1/3 |
| V2P03 | 0/2 → 1/2 | 2/2 → 2/2 |
| V2J01 | 2/2 → 2/2 | 2/2 → 2/2 |
| V2J02 | 0/3 → 0/3 | 1/3 → 0/3 |
| V2J03 | 0/1 → 0/1 | 0/1 → 0/1 |
| V2J04 | 0/2 → 0/2 | 0/2 → 0/2 |
| V2F01 | 0/1 → 0/1 | 0/1 → 0/1 |
| V2F02 | 0/3 → 0/3 | 0/3 → 0/3 |

Exact per-query path hits, edge IDs, payload characters, relation counts, and full/stub claim costs for every strategy are in `results.json`.

## Baseline/store reproducibility diagnosis

Round 16 recorded 1/20 at 3k and 8/20 at 10k. At the same source HEAD and unchanged frozen evidence, the current mutable stores initially produced 2/20 and 7/20. A repeat also exposed one JHipster stale read-through mutation: V2F01's eligible pool changed from three to two relations. The final harness therefore evaluates disposable store copies after a fixed stabilization pass, producing deterministic 2/20 and 7/20. This does **not** revise the accepted Round 16 reference gates; it demonstrates that repository commit pins alone do not snapshot `.tmf` store state. Future benchmark-grade store comparisons need a store hash/snapshot or a deterministic no-write normalization contract.

## Frozen integrity

Unchanged hashes:

- manifest: `e6357ffaf4a41f544c4d3a76ed4b7027573cdd0a9a50dfc060bb9529d18b08d2`
- goldens: `9d8d48f2cb48113d99150d4cc92c93a475809a1ad9d713851ec9226e577cf5ce`
- report: `b1bcc36b55cc57e1263a55cb5a3ff2c0a59bf15b1f3e1771b35e6f0f3887bf6c`

## Verification

- Two independent isolated evaluator runs were byte-identical to the checked-in `results.json`: SHA-256 `458e0a87466835540444fe98b55078f20df06d82222c0fe1745982e2eaab1ab0`.
- Full Python unit suite: 520/520 passed.
- Java qualification aggregate: 46/46 groups passed.
- `py_compile`, `git diff --check`, frozen-evidence hashes, and sensitive-context pattern scan passed.
- No production code or unit test changed; `tools/.javac-helper-build/` remains untracked and untouched.

## Limitations

Nine Spring-centric prompts and two existing stores are not a general ranking benchmark. Required-path endpoint coverage is a conservative locator proxy, not answer correctness; useful non-golden relations may be displaced or selected. Lexical overlap cannot reliably distinguish governing workflow edges from incidental shared vocabulary. No agent rerun or causal latency/correctness claim is made.
