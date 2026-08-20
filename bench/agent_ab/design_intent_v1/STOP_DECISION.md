# design_intent_v1 STOP_DECISION

Date: 2026-08-20 (Asia/Shanghai)
Status: **STOPPED — do not continue A/B implementation or full runs**

## Decision

Stop the current `design_intent_v1` A/B experiment implementation.

After deeper scenario analysis (`SCENARIOS.md`) and one real-Guava smoke run, the core TMF "call-chain continuity" value hypothesis appears poorly suited to this standard automated A/B protocol.

## Core issue

TMF's proposed value here is not simply "answer code questions faster." It is avoiding tunnel-vision bugs during real coding work after a prior cross-chain understanding has become partially stale.

That creates an experimental design conflict:

1. Tunnel-vision bugs require realistic coding/editing tasks, not simple explanation questions.
2. Realistic coding tasks are harder to standardize and score automatically.
3. Cross-version memory is difficult to compare fairly:
   - `TMF_FRESH` and `SOURCE_ONLY` need the same code version for fair A/B comparison.
   - But if both use the same version, the cross-version continuity/staleness value largely disappears.
   - If `TMF_*` uses cross-version memory while `SOURCE_ONLY` does not, the comparison measures a different setup rather than a clean A/B treatment.

## Scenario attempts and failure modes

See `SCENARIOS.md` for details. Summary:

- Scenario 1: Event dispatch chain mutation did not actually break the call chain enough to expose continuity value.
- Scenario 2: Function rename/delete mostly measured call-site search, not chain understanding.
- Scenario 3: Async-boundary movement made old claims stale; `TMF_FRESH` was conceptually mismatched with mutated code.
- Scenario 4: Exception handling repair had the same cross-version fairness problem.

## Real Guava smoke evidence

The latest smoke used real Guava EventBus source directly:

- Result: `results/smoke-n2-real-guava.json`
- Report: `results/SMOKE_REPORT.md`

Observed:

- Stale detection worked: 2/2.
- Stale trust errors: 0.
- But `SOURCE_ONLY` scored highly because real Guava source/comments already expose enough design intent.
- `TMF_STALE` reread reduction did not meet the <50% gate.

This supports the conclusion that the current A/B task format is not isolating the intended value.

## Recommendation

Do not continue full A/B runs for `design_intent_v1` in this form.

Recommended alternatives:

### Option A — Case study

Use 1-2 real agent coding failure cases where tunnel vision caused a bug. Analyze manually whether TMF call-chain claims and freshness gates would have prevented the failure.

### Option B — Document verification limits

Explicitly state in project docs that this value claim is difficult to validate with automated A/B experiments and likely requires qualitative evidence or long-term real usage feedback.

## Implementation status at stop

The following artifacts remain for audit/reuse:

- `tasks.json`
- `make_fixtures.py`
- `runner.py`
- `validate.py`
- `score.py`
- `fixtures/`
- `preflight.json`
- `FROZEN.sha256`
- `results/smoke-n2-real-guava.json`
- `results/SMOKE_REPORT.md`
- `EXECUTION_NOTES.md`

No further experiment execution should be started unless the main agent/user explicitly chooses a revised direction.
