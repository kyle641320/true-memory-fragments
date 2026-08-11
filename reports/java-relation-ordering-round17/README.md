# Round 17 relation-ordering evaluation

Run from repository root:

```bash
python3 reports/java-relation-ordering-round17/evaluate_ordering.py > reports/java-relation-ordering-round17/results.json
```

The evaluator is offline and deterministic. It checks manifest-pinned source commits, works in disposable copies, uses production freshness/trust filtering, ranks without golden features, and scores frozen required paths only after packing. See `ROUND17.md` for diagnosis and decision.
