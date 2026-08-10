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

## Cumulative Java worktree baseline (unreleased)

The cumulative Java worktree includes the extractor consolidation and subsequent bounded declaration adapters. The aggregate runner is `python3 tools/run_java_qualifications.py`; its manifest-governed baseline is **46/46 qualifiers and 731/731 checks**. The opt-in real-build gate now compiles **7/7 Gradle fixtures**, including exact-import Jakarta `PostConstruct` and `PreDestroy`; both lifecycle corpora also pass `mvn clean verify`. The full unittest baseline is **478/478 tests**; compileall and `git diff --check` also pass. The runner's default JSON remains deterministic and excludes timings; `--timings` is explicitly diagnostic. `python3 tools/verify_java_source_only_smoke.py` also passes from an index-free temporary export that excludes `.git`, `uv.lock`, generated state, caches, and reports.

This is local unreleased evidence only. It does not identify or imply a commit, tag, package, publication, runtime framework behavior, or enterprise-wide certification. The earlier structural-consolidation checkpoint was 20 qualifiers and 367 tests; those counts are historical rather than the current cumulative baseline.
