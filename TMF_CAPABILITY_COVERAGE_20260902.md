# TMF Capability Coverage Matrix — 2026-09-02

Verdict: **CORE STALE-CONTEXT ROI PROVEN; FULL TMF CAPABILITY VALIDATION NOT COMPLETE.**

This document consolidates current retained evidence after commit `e9ac8ce` (`Add TMF product ROI scorecard evidence`) and separates proven capability from release/readiness gaps. It is intentionally scoped: source code remains authoritative, TMF output is freshness-labeled locator evidence, and no TMF engine code was modified by the 2026-09-02 ROI proof.

## 1. Newly proven product ROI capability

Evidence:

- `bench/agent_ab/same_version_chain_v1/product_roi_scorecard_20260902.py`
- `bench/agent_ab/same_version_chain_v1/results/TMF_PRODUCT_ROI_SCORECARD_20260902.md`
- `bench/agent_ab/same_version_chain_v1/results/tmf_product_roi_scorecard_20260902.json`
- `bench/agent_ab/same_version_chain_v1/results/ORDER_M16_COMPLEX_TWO_PHASE_PAYMENT_REVIEW_R4_REPORT.md`
- `bench/agent_ab/same_version_chain_v1/results/order_m16_complex_two_phase_payment_review_r4.json`

Result:

- Scorecard verdict: `STRONG_PRODUCT_ROI_PASS`.
- Coverage: 7 repeat-qualified R4 fixtures, 28 semantic-evaluable rows per primary arm.
- SOURCE_ONLY: 18/28 = 0.643.
- TMF_REFRESHED_MAP: 23/28 = 0.821.
- Semantic uplift: +0.179, above the +0.10 product gate.
- pass/hour: 63.778 vs 45.572.
- pass/1k tokens: 0.037 vs 0.035.
- Mean source reads: TMF saves 1.2 per run.
- Stale containment: perfect on expected rows.
- Direct-refresh oracle: 3/3 pass with required recall and side-effect recall both 1.0.

Interpretation:

TMF's **stale-context + freshness gate + localized reread map** capability has product-level ROI evidence for bounded Java agent-coding tasks where stale claims can mislead an agent and fresh localized source neighborhoods can change behavior.

## 2. Existing Java/Spring source-analysis release evidence

Evidence:

- `RELEASE_AUDIT.md`
- `RELEASE_EVIDENCE.md`
- `RELEASE_HANDOFF_JAVA_SPRING_CONFIGPROPS.md`
- `RELEASE_MANIFEST.txt`
- `README.md`
- `docs/JAVA_ENTERPRISE_ROADMAP.md`
- `reports/java-*` evidence packages
- `tools/run_java_qualifications.py`
- `tools/verify_java_source_only_smoke.py`
- `tools/verify_java_gradle_integration.py`

Previously recorded baseline:

- `python3 tools/run_java_qualifications.py`: 46/46 qualifiers, 731/731 checks.
- `python3 tools/verify_java_gradle_integration.py`: 7/7 real Gradle clean builds.
- `python3 -Werror -m unittest discover -s tests -v`: 478 tests OK at rc3 audit time.
- `python3 tools/verify_java_source_only_smoke.py`: PASS at rc3 audit time.
- Later evidence notes list local baseline as 536/536 unittests, Java targeted 68/68, offline Java verification PASS, compileall PASS, `git diff --check` PASS.

Interpretation:

TMF has substantial bounded Java/Spring **source-analysis** validation: declaration nodes, Java relationships, selected Spring annotations/contracts, source-only smoke, packaging preflight, and selected Gradle fixture builds. This is not the same claim as runtime enterprise certification.

## 3. Capability matrix

| Capability | Current status | Evidence strength | Notes / remaining gaps |
|---|---:|---:|---|
| Git/file freshness invalidation | Proven for bounded source workflows | Strong | Freshness mismatch and stale binding gates are exercised in unit tests and ROI fixtures. |
| Function/method-level Java hashing | Proven for Java source analysis | Strong | Guava diff and Java qualifiers show usable fn-level tracking. |
| Java AST/source extraction | Proven for bounded Java/Spring source analysis | Strong | Broad unit and qualification coverage; still source-analysis, not full compiler semantic model. |
| Java/Spring declaration adapters | Broadly qualified | Strong but bounded | Many Spring annotation/relationship tests and 46/46 qualification baseline. |
| Stale claim withholding | Proven for ROI fixtures | Strong | Perfect stale withholding in product ROI scorecard expected rows. |
| Localized reread / refreshed map | Proven for stale-context ROI fixtures | Strong | Direct-refresh oracle and agent-loop ROI scorecard pass. |
| Agent productivity ROI | Proven for scoped product segment | Strong within segment | `STRONG_PRODUCT_ROI_PASS` for retained Java stale-context benchmark set. |
| Boundary / semantic stopping | Partially proven | Medium | Boundary precision evidence exists, but attribution distinguishes semantic failures from protocol/harness failures; not a universal proof. |
| Reverse graph queries (readers/writers/callers/subtypes) | Partially proven | Medium | Tooling and tests exist, but product-level precision/recall across real repos is not fully established. |
| API/Config/YAML/SQL nodes | Partially proven | Medium | Unit and source-analysis evidence exists for selected adapters; not fully validated as multi-language product surface. |
| Multi-language mixed repos | Not fully proven | Low | Python exists historically; Java is current focus; mixed Python+Java repo behavior needs explicit gate. |
| Real long-running repo maintenance tasks | Not fully proven | Low/Medium | Some real Java evidence exists, but today's ROI pass is synthetic/bounded agent A/B fixtures. |
| Runtime framework behavior | Not proven | Low | Source analysis does not certify Spring runtime, DI container behavior, database migration, or message broker runtime semantics. |
| Release packaging | Preflight passed, unreleased | Medium/Strong for packaging | rc3 audit says package builds/installs, but publication/tag/upload not authorized. |
| Production operations / CI integration | Partially documented | Medium | Reflex hook docs and workflows exist; product rollout, latency, cache ops, rollback and support playbooks remain open. |

## 4. What is fair to claim now

Fair claim:

> TMF's core stale-context ROI is validated at product-scorecard level for bounded Java agent-coding tasks: stale claims are withheld, fresh localized source context improves semantic success rate, and the scorecard passes preregistered product ROI gates.

Also fair:

> TMF has substantial bounded Java/Spring source-analysis qualification and unreleased packaging preflight evidence.

Not fair yet:

> TMF is fully validated across all languages, repositories, runtime frameworks, and production integration scenarios.

Not fair yet:

> TMF is enterprise runtime-certified or generally proven to improve all agent coding tasks.

## 5. Minimal next validation to approach full capability coverage

1. **Real-repo stale-context A/B gate**
   - Use one existing real Java repo harness (`bench/agent_ab/java_real_v2/` or PetClinic-like flow).
   - Force a stale architectural change across sessions.
   - Compare SOURCE_ONLY vs TMF refreshed map with hidden tests.
   - Success criterion: TMF improves semantic pass rate without over-reading or stale leakage.

2. **Graph query precision/recall gate**
   - Pick 2–3 real Java repos with known callers/readers/writers/subtypes.
   - Evaluate `tmf_callers`, `tmf_readers`, `tmf_writers`, `tmf_subtypes` against hand-checked oracle.
   - Success criterion: report precision/recall separately and mark dynamic/reflection unknowns as out of scope, not false certainty.

3. **Mixed-language freshness gate**
   - Build a small Python+Java fixture or use a real mixed repo.
   - Mutate one language and ensure unrelated claims in the other language are not over-invalidated.
   - Success criterion: correct stale/fresh split and useful retrieval fallback.

4. **Production integration smoke**
   - Exercise MCP tool path, CLI warm/retrieve, reflex hook warning, and fallback-to-source behavior in one scripted flow.
   - Success criterion: no unsafe blocking, stale claims clearly labeled, source remains authoritative.

5. **Release re-preflight on current HEAD**
   - Rerun the current full local release gates because rc3 evidence is dated 2026-08-10 and the worktree has changed.
   - Minimum commands:
     - `python3 tools/run_java_qualifications.py`
     - `python3 tools/verify_java_source_only_smoke.py`
     - `python3 -Werror -m unittest discover -s tests -v`
     - `python3 -m compileall -q tmf tests scripts tools`
     - `git diff --check`

## 6. Current recommended status label

Recommended label for external/internal tracking:

`CORE_STALE_CONTEXT_ROI_VALIDATED__FULL_CAPABILITY_VALIDATION_PENDING`

Reason:

The strongest current result is not merely a demo: it is a product-level ROI pass for a precise segment. But full TMF capability validation still requires real-repo stale A/B, graph-query oracle coverage, mixed-language freshness, integration smoke, and current-HEAD release preflight.
