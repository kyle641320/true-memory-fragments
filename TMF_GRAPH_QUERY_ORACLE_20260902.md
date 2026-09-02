# TMF Graph Query Oracle — 2026-09-02

Verdict: **PASS**.

Scope: small hand-checked mixed Python/Java fixture covering reverse callers, readers, writers, subtypes, and implementors. This is precision/recall evidence for known already-derived graph edges, not a complete blast-radius guarantee over arbitrary dynamic code.

## Summary

- Cases: 6/6 pass.
- Micro precision/recall: 1.000 / 1.000.
- Macro precision/recall: 1.000 / 1.000.
- TP/FP/FN: 8/0/0.

## Cases

- python_callers_helper: PASS; precision=1.000; recall=1.000; tp=1; fp=0; fn=0.
- python_callers_load_count: PASS; precision=1.000; recall=1.000; tp=1; fp=0; fn=0.
- python_readers_count: PASS; precision=1.000; recall=1.000; tp=2; fp=0; fn=0.
- python_writers_count: PASS; precision=1.000; recall=1.000; tp=1; fp=0; fn=0.
- java_subtypes_base: PASS; precision=1.000; recall=1.000; tp=1; fp=0; fn=0.
- java_implementors_job: PASS; precision=1.000; recall=1.000; tp=2; fp=0; fn=0.

## Interpretation

This closes a previously unquantified gap in the capability matrix: reverse graph query APIs have a hand-checked oracle with perfect precision/recall on this bounded mixed fixture. Remaining validation still needs larger real-repo oracle coverage and dynamic/reflection boundaries reported as out of scope rather than inferred.
