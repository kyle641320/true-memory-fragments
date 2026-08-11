# P04 Real stale-memory paired experiment

- Result: **1 valid pair; both arms correct; both rejected stale memory.**
- Mutation: adjacent-call swap in `VisitScheduler.bookVisit`, from flush→publish to **publish→flush**. Patch SHA-256 `52df648ef0ddc06f47754ff29999143fa960c713c118e31b261378ffe50aadad`.
- Isolation: two detached worktrees at fixed commit; same patch; SOURCE arm had no `.tmf`; freshness arm received copied pre-mutation store and checked claim `claim_java_24facfea08ca808b` first.
- TMF result: `fresh=false`, reason `java_hash mismatch`, action `degrade_to_source_or_rederive`; then 7-line local reread.

| arm | valid | correct | stale trust error | blocked stale | files/lines | calls | wall |
|---|---:|---:|---:|---:|---:|---:|---:|
| SOURCE_ONLY_WITH_STALE_MEMORY | True | True | False | True | 1/18 | 2 | 35782 ms |
| TMF_FRESHNESS | True | True | False | True | 1/7 | 2 | 27977 ms |

## Evidence and scope
Both cited `src/main/java/org/springframework/samples/petclinic/owner/application/VisitScheduler.java:44-50`. SOURCE reported reading 35-60 (18 source lines); TMF reread only 44-50 (7 lines) after freshness rejection. Raw agent JSON, exact prompts, tool-event extracts, old claim, TMF explain, patch, and hash are under `p04_real/`.

## Invalid attempts / limitations
Direct acpx setup attempts failed before an agent ran and are excluded from metrics. Native `openclaw agent` isolated runs then succeeded. Harness bootstrap/context usage exceeded the frozen 12k token target in both arms; this is disclosed as a protocol deviation, while task tool/source budgets remained within limits. No TMF engine, frozen prompt/golden/metric file, fixed checkout, commit, or remote was changed.
