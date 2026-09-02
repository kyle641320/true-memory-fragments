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
| Reverse graph queries (readers/writers/callers/subtypes/implementors/type-use) | Bounded fixture PASS; bounded real-repo oracle PASS after overload-aware type-use fix | Strong for bounded fixture, Medium+ for real repos | `TMF_GRAPH_QUERY_ORACLE_20260902.md`: 6/6 PASS on small mixed fixture. `TMF_REAL_REPO_GRAPH_ORACLE_20260902.md`: 5/5 PASS, micro/macro precision/recall 1.000/1.000 after fixing overloaded Java method type-use identity and `uses_type` rewarm reconciliation. |
| API/Config/YAML/SQL nodes | Partially proven | Medium | Unit and source-analysis evidence exists for selected adapters; not fully validated as multi-language product surface. |
| Multi-language mixed repos / freshness | Proven on bounded Python+Java freshness oracle; larger real-repo validation pending | Strong for bounded fixture, Medium/Low for real repos | `TMF_MIXED_LANGUAGE_FRESHNESS_20260902.md`: 5/5 cases PASS; changed Python/Java symbols stale, unrelated Python/Java function/method claims remain fresh. Java class-level over-invalidation remains documented current behavior. |
| Real-repo agent A/B transfer | Baseline audited; stale-context transfer pending; one deterministic V3 stale fixture prepared | Medium for baseline, Low for superiority | `TMF_REAL_REPO_AB_STATUS_20260902.md`: retained java_real_v2 real Petclinic/JHipster evidence has 17 valid arms, 6 ordinary pairs, 2 freshness pairs, pollution gate PASS 3/3, but shows no audited accuracy advantage and no latency advantage for TMF_MAP. `bench/agent_ab/java_real_stale_v3/REPORT.md`: deterministic Petclinic stale event-contract fixture is valid, but initial paired agent runs hit CLI/provider timeout and one subagent TMF abort; a minimal TMF retry completed a valid pair: both arms correct, no correctness superiority, TMF used fewer reread lines/tool calls. |
| Runtime framework behavior | Not proven | Low | Source analysis does not certify Spring runtime, DI container behavior, database migration, or message broker runtime semantics. |
| Release packaging / current HEAD preflight | Current HEAD local re-preflight passed; publication unreleased | Strong for local preflight, not publication | 2026-09-02 run passed Java qualifications, source-only smoke, 615 unittests, compileall, and diff check; no tag/upload authorized. |
| Production CLI/MCP integration smoke | Bounded smoke passed; rollout playbooks pending | Strong for local CLI/MCP smoke, Medium for production ops | `TMF_PRODUCTION_INTEGRATION_SMOKE_20260902.md`: 15/15 checks PASS across CLI warm/retrieve/explain/callers, stale labeling, source fallback, MCP initialize/list/warm/retrieve/status, path traversal rejection, malformed JSON fail-closed, no traceback stderr. |

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

1. **Real-repo stale-context A/B gate — BASELINE AUDIT DONE 2026-09-02; TRANSFER STILL PENDING**
   - Evidence: `TMF_REAL_REPO_AB_STATUS_20260902.md` over retained `bench/agent_ab/java_real_v2/`.
   - Result: real-repo baseline evidence exists, but real-repo stale-context superiority is not proven.
   - java_real_v2: 17 valid arms, 6 ordinary pairs, 2 freshness pairs, Petclinic/JHipster independent-store pollution gate PASS 3/3.
   - Audited interpretation: no observed accuracy difference after correcting a lexical-rubric false negative; TMF_MAP did not show latency advantage; both freshness arms blocked stale memory; V2F02 failed in both arms.
   - 2026-09-02 V3 smoke: `bench/agent_ab/java_real_stale_v3/REPORT.md` prepared a deterministic Petclinic event-contract stale fixture; relevant old `VisitBooked` claims are stale 5/5 and current source uses `VisitScheduled`, after a minimal TMF retry, the pair is scored: SOURCE_ONLY and TMF_MAP both blocked stale memory and answered correctly; TMF reread fewer source lines/tool calls, but correctness superiority is not established.
   - Remaining: rerun reliable valid pairs and scale to at least 2 real repos or 4 real-repo stale tasks before claiming transfer beyond bounded fixtures.

2. **Graph query precision/recall gate — BOUNDED + REAL-REPO ORACLES PASS 2026-09-02**
   - Bounded evidence: `TMF_GRAPH_QUERY_ORACLE_20260902.md` and `reports/graph-query-oracle-20260902.json`; 6/6 PASS, micro/macro precision/recall 1.000/1.000.
   - Real-repo evidence: `TMF_REAL_REPO_GRAPH_ORACLE_20260902.md` and `reports/real-repo-graph-oracle-20260902.json`; 5/5 PASS, micro/macro precision/recall 1.000/1.000.
   - Fix included: overloaded Java method type-use identity now uses method `identity_key`, and `uses_type` edge reconciliation uses `user_path` during rewarm.
   - Remaining boundary: run larger real-repo oracle coverage for dynamic/reflection/DI-heavy Java and mixed repos before claiming complete blast-radius validation.

3. **Mixed-language freshness gate — BOUNDED ORACLE DONE 2026-09-02**
   - Evidence: `TMF_MIXED_LANGUAGE_FRESHNESS_20260902.md` and `reports/mixed-language-freshness-20260902.json`.
   - Result: PASS on a small Python+Java repository.
   - Cases: 5/5 PASS.
   - Changed Python function and Java method stale correctly; unrelated Python function and Java method remain fresh.
   - Boundary: Java class claim still stales on member body change; documented as conservative over-invalidation, not marketed as class-level precision.
   - Remaining: larger real mixed-repo validation.

4. **Production integration smoke — DONE 2026-09-02**
   - Evidence: `TMF_PRODUCTION_INTEGRATION_SMOKE_20260902.md` and `reports/production-integration-smoke-20260902.json`.
   - Result: PASS.
   - Checks: 15/15 PASS.
   - Covered CLI warm/retrieve/explain/callers, stale labeling after source mutation, source fallback, thin retrieval, MCP initialize/tools/list/warm/retrieve/status, path traversal rejection, malformed JSON fail-closed, and no traceback stderr.
   - Remaining boundary: no package publication, release tag, hosted MCP deployment, latency SLO, cache operations, rollback playbook, or runtime framework certification.

5. **Release re-preflight on current HEAD — DONE 2026-09-02**
   - Evidence: `TMF_CURRENT_HEAD_REPREFLIGHT_20260902.md`.
   - Result: PASS.
   - `python3 tools/run_java_qualifications.py`: 46/46 qualifiers, 731/731 checks.
   - `python3 tools/verify_java_source_only_smoke.py`: PASS; exported_files=435.
   - `python3 -Werror -m unittest discover -s tests -v`: 615 tests OK, skipped=5.
   - `python3 -m compileall -q tmf tests scripts tools`: PASS.
   - `git diff --check`: PASS.
   - Remaining boundary: this does not authorize publication and does not certify runtime framework behavior.

## 6. Current recommended status label

Recommended label for external/internal tracking:

`CORE_STALE_CONTEXT_ROI_VALIDATED__FULL_CAPABILITY_VALIDATION_PENDING`

Reason:

The strongest current result is not merely a demo: it is a product-level ROI pass for a precise segment, current HEAD passes local release re-preflight, reverse graph queries have a bounded mixed-language precision/recall oracle, mixed Python+Java freshness has a bounded oracle, and CLI/MCP production integration smoke passes locally. But full TMF capability validation still requires a new discriminating real-repo stale A/B, larger mixed-repo validation, and production rollout evidence.

- Equal-budget SOURCE_ONLY control also answered correctly under the same four-file framing, so the latest V3 evidence supports efficiency differences only, not correctness superiority.

- Real SOURCE_ONLY_MIN_RETRY completion scored: same four-file budget, both SOURCE_ONLY and TMF_MAP correct; no correctness superiority. TMF retains explicit freshness evidence and lower reported tool-call count (2 vs 4), with same source files/lines (4 files/218 lines).
