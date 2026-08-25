# Boundary Precision B12/B13 — Correct Interpretation

This directory contains raw repeat data and post-hoc failure attribution for the B12/B13 boundary precision reruns.

## Do not read raw pass rate as TMF value

The raw B12/B13 original rerun numbers are:

- SOURCE_ONLY: `9/10`
- TMF_CLAIMS: `7/10`
- DOC_CONTROL: `8/10`

Those raw numbers are **misleading if read as semantic TMF value**.

A raw-transcript and diff review found that all three TMF_CLAIMS raw failures were caused by agent/edit protocol or source-shape failures, not by TMF pointing to the wrong semantic boundary.

## Correct adjusted interpretation

For TMF_CLAIMS on the original B12/B13 rerun:

- Raw pass: `7/10`
- Protocol-clean raw pass: `6/6`
- Semantic-known pass/fail: `7 pass / 0 fail`
- Protocol-unclean/unknown: `3`

For comparison:

- SOURCE_ONLY has one genuine B12 semantic boundary failure.
- DOC_CONTROL has one genuine B12 semantic boundary failure.

Therefore the fair conclusion is:

> TMF did **not** fail semantically on B12/B13 in the original rerun. TMF avoided the true B12 semantic boundary mistakes seen in SOURCE_ONLY and DOC_CONTROL, but its raw pass rate was depressed by agent/edit protocol failures.

## What the TMF raw failures actually were

- `B12 r1`: correct boundary shape (`checkNotNull(event)` hoisted before hook, then `Method.invoke`), but helper definition exact-text edit did not match the current method signature, causing compile failure.
- `B12 r3`: correct boundary shape, but helper definition anchor was non-unique / then stale, causing compile failure.
- `B13 r3`: no effective source change because the agent assumed a return-expression/private-returning source shape that was absent in the fixture; exact edits failed.

These should be counted as agent/harness/protocol failures, not TMF semantic failures.

## Required reporting convention going forward

All TMF A/B benchmark summaries must separate:

1. Raw pass rate.
2. Protocol-clean pass rate.
3. Semantic-adjusted score / semantic failure count.

Edit failure, compile failure, no-effect false completion, and mistaken source-shape edits must not be counted as TMF semantic failures.

## Evidence files

- `TMF_ADJUSTED_SEMANTIC_REVIEW_B12_B13_ORIGINAL_RERUN.md`
- `NON_TMF_FAILURE_REVIEW_B12_B13_ORIGINAL_RERUN.md`
- `BOUNDARY_PRECISION_TARGETED_B12_B13_ORIGINAL_RERUN_V1_REPORT.md`
- `boundary_precision_targeted_B12_B13_original_rerun_v1.json`
- raw transcripts under `raw/boundary_precision_targeted_B12_B13_original_rerun_v1_*`
