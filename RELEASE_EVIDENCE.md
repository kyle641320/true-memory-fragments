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

## Large-repository snapshot checkpoint (unreleased, 2026-08-13)

Repository-wide Java consumers now share a per-`GitRepo` immutable snapshot of tracked Java paths, text, classes, and methods. The normal unpinned API invalidates after tracked file addition, deletion, or content/size/mtime change; `warm_repo` pins only for that single warm lifecycle, and a new `GitRepo` obtains a fresh view. Ordinary unittest includes a 240-file synthetic regression gate asserting exactly one read and one class/method parse per Java file, avoiding a wall-clock threshold and keeping the gate fast.

Apache Dubbo preflight evidence at `experiments/tmf-large-java-20260812/results/DUBBO-PREFLIGHT-SUCCESS.md` records the locked **4,051-file** repository result: complete warm **4,051/4,051**, zero failed files, **145,743** claims, and complete no-op verification. Its last blocking 643-claim file improved from about 60 seconds to 4.433 seconds. This is preflight and store-integrity evidence only—not the pending SOURCE_ONLY/TMF_MAP paired A/B result and not enterprise-ready certification.

The current local validation baseline is **536/536 unittests**, Java targeted **68/68**, offline Java verification PASS, Python byte-compilation PASS, and `git diff --check` PASS. The bounded Java aggregate remains partial source analysis; Phase 4 production qualification is still open.

## Cumulative Java worktree baseline (unreleased)

The cumulative Java worktree includes the extractor consolidation and subsequent bounded declaration adapters. The aggregate runner is `python3 tools/run_java_qualifications.py`; its manifest-governed baseline is **46/46 qualifiers and 731/731 checks**. The opt-in real-build gate now compiles **7/7 Gradle fixtures**, including exact-import Jakarta `PostConstruct` and `PreDestroy`; both lifecycle corpora also pass `mvn clean verify`. The full unittest baseline before this snapshot checkpoint was **478/478 tests**; see the dated checkpoint above for the current baseline. The runner's default JSON remains deterministic and excludes timings; `--timings` is explicitly diagnostic. `python3 tools/verify_java_source_only_smoke.py` also passes from an index-free temporary export that excludes `.git`, `uv.lock`, generated state, caches, and reports.

This is local unreleased evidence only. It does not identify or imply a commit, tag, package, publication, runtime framework behavior, or enterprise-wide certification. The earlier structural-consolidation checkpoint was 20 qualifiers and 367 tests; those counts are historical rather than the current cumulative baseline.
