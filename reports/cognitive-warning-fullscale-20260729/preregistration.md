# Preregistration: TMF Cognitive Warning Full-Scale Control Experiment

Created: 2026-07-29 03:35 CST

## Objective

Run the full-scale confirmatory TMF SessionStart warning A/B test requested on
2026-07-29. Smoke validation has already established that the fixture,
mechanical scorer, and transcript capture are usable; smoke outcomes are not
evidence for this run.

## Isolation Boundary

All experiment files, fixtures, prompts, outputs, transcripts, score reports,
and final reports must stay under:

`/root/.openclaw/workspace/experiments/tmf-cognitive-warning-fullscale-20260729`

The run must not modify production TMF configuration, plugins, engines, or real
repositories. It may read the production SessionStart warning renderer from
`/root/.openclaw/workspace/projects/tmf-reflex-hook/hook/tmf-sessionstart-calibration.py`
to generate production-format warning text.

## Conditions

- Fixed model: `aisz/gpt-5.5`, matching the validated smoke run.
- `control`: no TMF SessionStart warning before the task turn.
- `treatment`: the task turn is preceded by the production-format TMF
  SessionStart warning text rendered by the production warning renderer, with
  `risklib/eligibility.py::f [changed]` as the suspect symbol.

The only intended task-turn prompt difference is the warning block. After
removing that exact warning block, control and treatment task prompts must be
byte-identical.

## Fixture

Each sample reuses the same absolute active fixture path during the agent turn:

`/root/.openclaw/workspace/experiments/tmf-cognitive-warning-fullscale-20260729/active-fixture`

Round 1 familiarization source:

```python
def f(account):
    """Return dict summary: {'eligible': bool, 'limit': int, 'reason': str}."""
    ...
    return {"eligible": eligible, "limit": limit, "reason": reason}
```

Round 2 task source:

```python
def f(account):
    """Return tuple summary: (eligible: bool, limit: int, reason: str)."""
    ...
    return eligible, limit, reason
```

The task is to implement `risklib/reporting.py::format_decision(account)`,
which must import and call `risklib.eligibility.f`. Using the old dict-return
belief produces a mechanically scorable stale error.

## Scale And Order

- Planned samples: 160 total.
- Arms: 80 control, 80 treatment.
- Groups: 10 groups per arm, 8 samples per group.
- Execution order: `control` group 1, `treatment` group 1, ..., `control` group
  10, `treatment` group 10.

This order is fixed before running. Invalid samples are reported and not
silently replaced unless the user explicitly authorizes a separate replacement
run; this preregistered run analyzes the fixed planned samples that produced
valid outputs.

## Primary Outcome

Primary metric: stale error rate among valid samples.

Sample categories are assigned mechanically after the task turn:

- `correct`: generated `format_decision` passes behavior checks against current
  tuple-returning `f`.
- `stale_error`: generated output fails behavior checks and shows stale dict
  access or a runtime failure consistent with stale dict access.
- `other_error`: generated output is valid for analysis but fails for a reason
  not classified as stale.
- `invalid`: no judgeable code, missing function, infrastructure/session
  failure, or familiarization did not actually receive the old `f` source.

The primary Fisher exact table is `[[control stale_error, control non-stale],
[treatment stale_error, treatment non-stale]]` over valid samples. The Fisher
test is two-sided.

Pre-registered conclusion rules:

1. If treatment stale-error rate is significantly lower than control at
   `p < 0.05`, conclude TMF is effective in this cognition-non-executable
   scenario; report effect size and 95% CI.
2. If not significant, conclude no effect was observed in this scenario; report
   the minimum detectable effect at this sample size.
3. If both arms have stale-error rates below 10%, conclude spontaneous reread
   rate was already high and TMF had little room to improve.
4. If control stale-error rate is below 20%, downgrade the whole conclusion as
   `trap strength insufficient`.

## Secondary Outcome

Secondary metric: task-turn `reread_f` rate. `reread_f=1` when the transcript
contains task-turn evidence that the agent inspected current
`risklib/eligibility.py`; otherwise `0`.

This metric separates warning-induced rereading from output correctness. It is
not itself the primary effect claim.

## Group Stability

Report each arm's 10 group-level stale-error counts and sample standard
deviation. If one arm's mean is better but group-to-group stability is visibly
poor, mark that plainly.

## Integrity Requirements

- Save every sample's prompts, transcript JSONL, agent turn JSON, generated
  code, score JSON, and metadata.
- Save the actual execution order.
- Save prompt SHA256 proof: raw control/treatment prompts and normalized prompts
  with treatment warning removed.
- Publicly list invalid samples and reasons.
- Do not post-hoc change thresholds or exclusion rules.
- Do not infer effectiveness from reread rate alone; correctness is primary.
- Do not directly execute `f(...)` to infer the answer inside the scoring
  judgment; the scorer may import generated code after the agent turn.
- The platform does not expose hidden chain-of-thought. "Full reasoning text"
  therefore means all available visible assistant text plus the complete tool
  call/tool result sequence, prompts, turn JSON, and generated source; no hidden
  reasoning will be fabricated or claimed as archived.
