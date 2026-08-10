# Release evidence pointers

Evidence is kept outside the source archive and referenced by the build report.

- Ten-repo production gate: `experiments/tmf-java-validation-20260806/reports/ten-repo-production-gate-20260807-final/`
- Ten-repo mutation gate: `experiments/tmf-java-validation-20260806/reports/ten-repo-mutation-gate-20260807/`
- Guava RSS remediation: `experiments/tmf-java-validation-20260806/reports/guava-rss-remediation-20260808/`
- Clean-build policy decision: `experiments/tmf-java-validation-20260806/reports/clean-build-release-decision-20260808/`
- Consolidated gate: `experiments/tmf-java-validation-20260806/reports/consolidated-release-gate-20260808/`

The evidence directories are not included in the runtime wheel. The offline Java verifier requires the source evidence bundle or a complete git checkout with `vendor/wheels`.

## Java persistence-adapter qualification

Run `python3 tools/verify_java_persistence_qualification.py`. The checked `reports/java-persistence-qualification/report.json` uses format `tmf.java-persistence-qualification.v1` and records independent Maven/Gradle annotation-only evidence. This is a bounded partial-coverage gate, not enterprise-wide certification. Rollback is deletion of the fixture/verifier/report documentation package; no runtime semantics, schema migration, or persisted-cache migration was introduced.

## Java Spring Cache qualification

Run `python3 tools/verify_java_cache_qualification.py`. The checked report at `reports/java-cache-qualification/report.json` records a deterministic 7/7 held-out Maven/Gradle declaration-only gate. This is partial source evidence, not runtime cache certification.

## Java extractor structural consolidation (2026-08-10, unreleased)

The cumulative Java worktree was structurally audited before further adapter expansion. The effective extractor was preserved while 95 shadowed top-level definitions (3,112 lines) were removed, and `tests/test_java_extract_structure.py` now rejects duplicate top-level symbols. Local evidence: 20/20 existing Java qualification verifiers passed individually, Java-targeted unittest passed 204/204, full unittest passed 367/367 (366 prior baseline plus one structural test), and compileall/diff-check passed. This is local unreleased evidence only; it is not a package, publication, or enterprise-wide certification. The remaining 4,649-line extractor and similar annotation-specific parsers are a documented extension boundary, not evidence of runtime semantics.
