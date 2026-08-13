> **Status note (2026-08-13):** Historical result for this specific protocol. Do not generalize it across delivery modes. See the unique current [Agent runtime value status](../../../docs/AGENT_RUNTIME_VALUE_STATUS.md).

# Java Real-Agent A/B v2 Report

## Completion

- Native isolated agent runs: 17 valid arms.
- Valid ordinary pairs: **6** (target at least 6 met).
- Valid freshness pairs: **2** (target 2 met).
- JHipster/Petclinic independent-store pollution gate: **PASS (3/3)**.
- v1 P01-P04 and TMF engine/parser/retrieval: unchanged.

## Descriptive results

SOURCE_ONLY: n=9, conservative lexical-rubric accuracy=0.889, citation accuracy=1.000, mean wall=101.7s, freshness stale-block=1.000.

TMF_MAP: n=8, conservative lexical-rubric accuracy=0.750, citation accuracy=1.000, mean wall=113.5s, freshness stale-block=1.000.

Under this small v2 sample, TMF_MAP did not demonstrate an advantage and was slower. Both freshness pairs blocked the injected stale claim in both arms. This is descriptive only; no causal win is claimed.

For the six valid ordinary pairs, the stored lexical rubric scores SOURCE_ONLY 6/6 and TMF_MAP 5/6. Manual audit found that the sole difference, V2J02, is a **lexical-rubric false negative** rather than a demonstrated answer error: the held-out fact says “three overloads,” while the TMF_MAP answer separately and correctly covers single-item, unpaged-list, and paged reads, cites all three required repository files, explains label-fetch delegation, and states restoration of original ID order. The frozen golden and conservative machine score are retained unchanged; this audit does not retroactively rewrite the benchmark. Accordingly, the defensible conclusion is **no observed accuracy difference after audit**, not evidence that TMF_MAP is less accurate.

## Invalid runs and limitations

One freshness TMF call failed from temporary AI-service overload; its raw failure is retained as `V2F01_TMF_MAP.*.invalid.*`, and a clean isolated retry succeeded. The optional seventh ordinary JHipster pair did not complete in TMF_MAP because the isolated runner timed out; invalid metadata is retained and that pair is excluded. The target is nevertheless met by six other ordinary pairs. Source/tool/line metrics are agent-reported; absent values remain null. Correctness evaluation is a conservative held-out citation/fact-key rubric, not an independent expert panel.

## Artifacts

`manifest.json` freezes commits, prompts, budgets, random order, and tasks. `goldens/goldens.jsonl` is evaluator-only. `prompts/`, `raw/`, `mutations/`, and `artifacts/` preserve inputs, native outputs, mutations, stale checks, and pollution evidence. `REPORT.json` contains row and pair metrics.
