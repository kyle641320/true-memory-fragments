# Cognitive-warning full-scale A/B evidence (2026-07-29)

This directory preserves the reproducible summary package for a pre-registered
TMF cognitive-warning experiment. The raw run archive remains local because it
contains 160 full agent transcripts and generated working trees; the committed
package includes the protocol, runner/analyzer, prompt proof, execution order,
per-sample scores, final report, and an independent audit result.

## Question

Can a source-bound TMF SessionStart warning reduce stale agent cognition when a
previously learned function contract changes from a dict return to a tuple
return?

## Design

- Model: `aisz/gpt-5.5`.
- Fixture: `risklib/eligibility.py::f` changes from returning
  `{"eligible": ..., "limit": ..., "reason": ...}` to returning
  `(eligible, limit, reason)`.
- Task: implement `risklib/reporting.py::format_decision(account)` by importing
  and calling `f(account)`.
- Arms:
  - `control`: no TMF warning before the task turn.
  - `treatment`: production-format TMF warning naming
    `risklib/eligibility.py::f [changed]` before the task turn.
- Planned order: 10 paired groups; each group runs 8 control samples then 8
  treatment samples.
- Planned total: 160 samples.
- Primary metric: stale-error rate among valid samples.
- Test: Fisher exact two-sided over
  `[[control stale, control non-stale], [treatment stale, treatment non-stale]]`.

The only intended task-turn prompt difference is the warning block. After
removing that exact warning block, control and treatment task prompts are
byte-identical; see `prompt-sha256-proof.json`.

## Result

Independent audit status: **PASS**.

| arm | valid | stale_error | correct | stale_error_rate |
|---|---:|---:|---:|---:|
| control | 80 | 80 | 0 | 100.0% |
| treatment | 80 | 8 | 72 | 10.0% |

- Absolute stale-error reduction: `0.900`.
- Newcombe 95% CI: `[0.8033434772528575, 0.9484523844326191]`.
- Fisher exact two-sided p: `2.1326174722623323e-12`.
- Group stale-error counts:
  - control: `[8, 8, 8, 8, 8, 8, 8, 8, 8, 8]`
  - treatment: `[1, 1, 1, 0, 0, 1, 1, 2, 1, 0]`

Secondary mechanism metric from archived runner score:

- `reread_f`: control `31/80`; treatment `80/80`.
- `direct_probe_f`: control `0/80`; treatment `0/80`.

## Audit scope

The independent audit re-derived the primary result from each archived generated
`risklib/reporting.py` and the archived tuple-returning fixture, then compared
primary fields against `samples.json`.

Audit checks:

- 160 run directories / 160 sample rows / 160 execution-order rows.
- Missing required archived files: 0.
- Order mismatches: 0.
- Primary field mismatches vs runner: 0.
- Frozen SHA mismatches: 0.
- Prompt unique-variable proof: OK.

Caveat: exact task-start timestamps were not persisted separately, so the audit
keeps runner-provided `reread_f` / `direct_probe_f` as secondary metrics. The
primary stale-error/correctness conclusion does not depend on those secondary
metrics.

## Files

- `preregistration.md` — pre-registered protocol and decision rules.
- `run_fullscale.py` — original runner used for the 160-sample run.
- `analyze_results.py` — original analyzer/statistics script.
- `samples.json` — per-sample archived runner scores.
- `execution-order.json` — fixed execution order.
- `prompt-sha256-proof.json` — prompt equality and warning-renderer proof.
- `final-report.md` / `final-summary.json` — runner report.
- `independent-audit.md` / `independent-audit.json` — independent audit output.
- `warning-text.txt` — warning block used in treatment.

## Interpretation

This validates TMF's core agent-facing value in this scoped scenario: a
source-bound freshness warning can sharply reduce stale cognition errors without
requiring the agent to trust memory as authoritative. Source remains the final
authority; the warning changes the agent's behavior by causing a current-source
reread.

It does **not** by itself prove universal productivity gains across all coding
tasks. Broader value still needs real-repository cross-session A/B tasks and
negative-boundary tests.
