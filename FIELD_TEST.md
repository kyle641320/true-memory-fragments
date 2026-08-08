# FIELD_TEST.md — Window 1/4 plan-only harness

This file defines the future field-test scouting protocol for TMF after all four completion windows pass review.

Window 1 status: **plan only**. Do not start external repository scouting from this window.

## What this harness may do now

- Write local command templates.
- Record what metrics must be captured later.
- Define a JSONL diary schema for future runs.
- Explain interpretation baselines.

## What this harness must not do now

- Clone, fetch, or browse external repositories.
- Start network reconnaissance.
- Run model warming or semantic contract generation.
- Change TMF engine behavior based on field results.

## Future field-test protocol

When windows 1–4 have passed review, each candidate repository run should record one JSON object per line:

```json
{
  "timestamp": "2026-06-12T00:00:00Z",
  "repo": "owner/name",
  "commit": "<sha>",
  "language_mix": {"python": 0, "java": 0},
  "commands": ["python3 -m tmf.cli warm --repo .", "python3 -m tmf.cli stats --repo ."],
  "metrics": {
    "files_seen": 0,
    "claims_total": 0,
    "cache_hit": 0,
    "miss": 0,
    "stale_detected": 0,
    "rederive": 0,
    "degrade_to_source": 0,
    "rename_migration": 0,
    "rename_mass_invalidation": 0
  },
  "failures": [],
  "notes": ""
}
```

## Interpretation baseline

- TMF source fallback is success when unsupported constructs are exposed honestly.
- Precision regressions are worse than recall gaps.
- Rename migration is only a positive signal when it is exact-blob, one-old/one-new, and freshness remains true after migration.
- A field result must not be used to claim semantic correctness unless it is backed by source-bound validation.
