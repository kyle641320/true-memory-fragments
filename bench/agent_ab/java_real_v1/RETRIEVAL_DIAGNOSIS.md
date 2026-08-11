# Petclinic TMF retrieval diagnosis (java_real_v1)

## Scope and method

Read-only inspection of the repository-pinned Petclinic store at commit `58c3310e36c7d827959df6af4d64bdeb8d81f1ea`. Frozen natural prompts were used unchanged for the baseline. Offline alternatives are provider-neutral expansions made only from prompt vocabulary plus generic workflow facets; golden symbols/paths were used **only after retrieval for scoring**, never as Agent/task input. No engine/parser/build adapter, frozen task/golden/metric, repository source, commit, or store was modified.

## Store and graph evidence

- Store is warm and complete: **1,071 claims**, freshness sample **20/20 fresh**, **0 stale**; graph reports **159 calls**, 174 reads, 29 writes, 85 type-use edges.
- Target material is not wholly absent. Direct diagnostic retrieval finds:
  - `VisitScheduler.bookVisit` at `VisitScheduler.java:44-50`;
  - `VisitBooked` and its tests;
  - `VetEventListener.java:1-40`;
  - `VetRoster.assignVet` at `VetRoster.java:61-74`;
  - `VisitController.processNewVisitForm` at `VisitController.java:96-106`.
- However, `tmf_callers` addressing for the retrieved Java functions returned `not_found` even with exact retrieved qualname/path. More importantly, publication → event consumer is not exposed as one traversable relation. Thus the graph is useful but incomplete for the required end-to-end event path.

## Frozen-prompt ablation

`MRR` is averaged across each task's required golden files; missing anchors score zero. Full per-result paths are in `RETRIEVAL_DIAGNOSIS.json`.

| task | current context@3000: ranks / MRR | composed retrieval@20 (best): ranks / MRR | first key anchor |
|---|---|---|---|
| P01 | –, – / **0.000** | –, – / **0.000** | none |
| P02 | 1, –, – / **0.333** | all missing / **0.000** | 1 baseline |
| P03 | –, 1 / **0.500** | –, 1 / **0.500** | 1 |
| P04 | 1 / **1.000** | 17 / **0.059** | 1 baseline; 17 composed |

P01 confirms the reported failure: natural context does not surface either required chain anchor. Generic query composition alone also fails, so this is not merely an Agent failing to ask one obvious follow-up. P02/P04 show that naïve expansion can actively worsen strong exact-name natural prompts.

## Cause classification

1. **Query ranking — primary.** P01's generic words (“visit”, “booking”, “Java path”) over-rank repeated `Visit.java` structural claims; the workflow-bearing methods/listener do exist under direct symbol probes.
2. **Thin-context budget and de-duplication — contributing.** At 3,000 chars only 3–4 claims survive. Truncation removes relations, while repeated same-path/declaration variants consume first-screen slots.
3. **Entry-point design — contributing.** `context(question)` is a one-shot lexical bundle, not staged entry → producer → event → consumer exploration.
4. **Partial graph — real but not total.** Calls exist, but event publication/consumption and reverse-addressability do not yield the complete chain. This prevents pure graph traversal even after a useful claim is found.
5. **Agent usage — contributing, not root cause.** A good Agent should combine retrieval and bounded source fallback, but the natural-question first screen gives insufficient anchors; “use context once” is an inadequate recipe.

## Minimal next experiment (no new Java semantics)

1. **Wrapper A/B, not engine change:** baseline `context(prompt)` versus a staged wrapper that derives 2–3 generic facets from the prompt (“entry/call path”, “publish/event”, “consumer/listener/downstream”), retrieves each, merges by claim-id/path, and records provenance. Never inject known symbols or paths.
2. **Presentation diversity:** cap duplicate path/qualname entries and reserve output slots for distinct source paths, relations, and fallback paths before repeated declarations.
3. **Bounded orchestration:** expand returned claim IDs with `explain`/`callers` where resolution works, then source-read fallback; accept static uncertainty rather than blind querying.
4. Re-run only the frozen prompts and compare Recall@k/MRR plus source files/lines, calls, and correctness. Do **not** adopt the wrapper unless P01 improves without regressing exact-name P02/P04.

The present evidence does **not** justify adding Java semantics first. Retrieval/presentation/orchestration is the smaller, testable intervention.
