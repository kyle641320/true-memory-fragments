# TMF Mixed-Language Freshness Oracle — 2026-09-02

Verdict: **PASS**.

Scope: small Python+Java repository. The oracle mutates one Python function and one Java method after deriving claims, then verifies changed symbols are stale while unrelated Python/Java method/function claims remain fresh.

## Summary

- Cases: 5/5 pass.
- Localized changed symbols stale: True.
- Cross-language unrelated function/method claims remain fresh: True.
- Java class over-invalidates on member body change: True (documented current behavior, not counted as failure in this oracle).

## Cases

- changed_py: PASS; expected_fresh=False; actual_fresh=False.
- stable_py: PASS; expected_fresh=True; actual_fresh=True.
- service_class: PASS; expected_fresh=False; actual_fresh=False.
- changed_java: PASS; expected_fresh=False; actual_fresh=False.
- stable_java: PASS; expected_fresh=True; actual_fresh=True.

## Interpretation

This validates a bounded mixed-language freshness property: Python and Java claims can coexist, localized function/method mutations stale the relevant symbols, and unrelated function/method claims in either language remain fresh. The Java class-level claim still stales when a member body changes; this is current conservative over-invalidation and should not be marketed as class-level precision.
