# TMF Real-Repo A/B Status — 2026-09-02

Verdict: **REAL-REPO BOUNDED EVIDENCE EXISTS; REAL-REPO STALE-CONTEXT SUPERIORITY NOT YET PROVEN.**

This note audits retained real-repo A/B evidence before starting any new expensive agent run. It prevents overclaiming from the newer synthetic/bounded product ROI scorecard.

## Evidence inspected

- `bench/agent_ab/java_real_v2/PROTOCOL.md`
- `bench/agent_ab/java_real_v2/manifest.json`
- `bench/agent_ab/java_real_v2/REPORT.md`
- `bench/agent_ab/java_real_v2/REPORT.json`
- `bench/agent_ab/java_real_v2/raw/`
- `bench/agent_ab/java_real_v2/artifacts/`

The protocol uses real Java repositories:

- Petclinic pinned to `58c3310e36c7d827959df6af4d64bdeb8d81f1ea`.
- JHipster pinned to `f8da577c944ecc4db46fc961a1ba022d5bbf8964`.

The protocol also records independent repository-local `.tmf` stores and a pollution gate.

## Retained java_real_v2 result summary

From `REPORT.md` / `REPORT.json`:

- Native isolated agent runs: 17 valid arms.
- Valid ordinary pairs: 6, meeting the target.
- Valid freshness pairs: 2, meeting the target.
- JHipster/Petclinic independent-store pollution gate: PASS 3/3.
- SOURCE_ONLY: n=9; conservative lexical-rubric accuracy 0.889; citation accuracy 1.000; mean wall 101.7s; freshness stale-block 1.000.
- TMF_MAP: n=8; conservative lexical-rubric accuracy 0.750; citation accuracy 1.000; mean wall 113.5s; freshness stale-block 1.000.
- Manual audit in the retained report says V2J02's sole ordinary-pair machine-score difference is a lexical-rubric false negative rather than a demonstrated answer error; defensible conclusion is no observed accuracy difference after audit, not TMF underperformance.

Freshness rows:

- V2F01 SOURCE_ONLY: correct=True; stale_blocked=True; stale_trusted=False; local_reread_lines=90.
- V2F01 TMF_MAP: correct=True; stale_blocked=True; stale_trusted=False; local_reread_lines=101.
- V2F02 SOURCE_ONLY: correct=False; stale_blocked=True; stale_trusted=False; local_reread_lines=218.
- V2F02 TMF_MAP: correct=False; stale_blocked=True; stale_trusted=False; local_reread_lines=92.

## What this proves

Fair claims:

1. TMF can be run against pinned real Java repositories through isolated native agent protocols.
2. Real-repo store isolation/pollution controls were exercised and passed in java_real_v2.
3. Real-repo freshness pairs show stale memory can be blocked in both SOURCE_ONLY and TMF_MAP arms under that protocol.
4. TMF_MAP preserved citation correctness in valid rows.
5. The retained real-repo v2 evidence does not contradict the synthetic/bounded ROI result, but it also does not prove it transfers to real repos.

## What this does not prove

Not fair to claim:

1. Broad real-repo agent productivity superiority.
2. Real-repo stale-context ROI superiority over SOURCE_ONLY.
3. Lower latency or fewer rereads in real repos overall.
4. General enterprise runtime correctness.

Reason: under java_real_v2, after audit the ordinary paired result is best read as no observed accuracy difference; mean wall time was slower for TMF_MAP; both freshness arms blocked stale memory; V2F02 failed in both arms.

## Relationship to 2026-09-02 product ROI scorecard

The 2026-09-02 product scorecard proves scoped product ROI for repeat-qualified bounded stale-context fixtures:

- SOURCE_ONLY 18/28 = 0.643.
- TMF_REFRESHED_MAP 23/28 = 0.821.
- uplift +0.179.
- verdict `STRONG_PRODUCT_ROI_PASS`.

That is a valid product ROI result for its segment. It should not be silently generalized to real Java repositories without a new real-repo stale-context A/B.

## Minimal next real-repo validation

To close this gap, run a new real-repo stale-context A/B that is intentionally discriminating:

1. Use a pinned real repo with an independently prepared mutation that changes a previously true architectural/path claim.
2. Warm TMF before mutation; mutate source; do not expose goldens to prompts.
3. Compare SOURCE_ONLY vs TMF refreshed-map/stale-gated arms under identical budgets.
4. Required success metrics:
   - stale claim is withheld or explicitly blocked;
   - answer cites the minimal current neighborhood;
   - hidden/held-out oracle checks semantic correctness;
   - report raw pass, protocol-clean pass, semantic-adjusted pass, source reads/lines, tool calls, wall time;
   - separate agent/protocol failures from TMF semantic failures.
5. Minimum target: at least 2 real repos or 4 discriminating real-repo stale tasks before claiming transfer beyond bounded fixtures.

Recommended current label:

`REAL_REPO_AB_BASELINE_AUDITED__STALE_CONTEXT_TRANSFER_PENDING`
