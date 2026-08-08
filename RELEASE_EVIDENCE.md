# Release evidence pointers

Evidence is kept outside the source archive and referenced by the build report.

- Ten-repo production gate: `experiments/tmf-java-validation-20260806/reports/ten-repo-production-gate-20260807-final/`
- Ten-repo mutation gate: `experiments/tmf-java-validation-20260806/reports/ten-repo-mutation-gate-20260807/`
- Guava RSS remediation: `experiments/tmf-java-validation-20260806/reports/guava-rss-remediation-20260808/`
- Clean-build policy decision: `experiments/tmf-java-validation-20260806/reports/clean-build-release-decision-20260808/`
- Consolidated gate: `experiments/tmf-java-validation-20260806/reports/consolidated-release-gate-20260808/`

The evidence directories are not included in the runtime wheel. The offline Java verifier requires the source evidence bundle or a complete git checkout with `vendor/wheels`.
