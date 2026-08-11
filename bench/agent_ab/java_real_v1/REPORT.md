# Java Real Agent A/B v1 Pilot Report

## Result
Pilot executed: 12 deterministic proxy runs (4 tasks × 3 arms), same frozen order and budgets. This is **not a successful real-model A/B**: two genuine ACP attempts failed (OpenClaw ACP session metadata/init failure; Codex ACP timed out at 120 s). Results therefore validate harness mechanics and expose likely retrieval effects only; they do not establish causal Agent value.

## Frozen inputs
- TMF worktree HEAD/origin master: `f6314c2056d474d819ae7788fdcf1cb375ba16e7`; no TMF core/parser/build-adapter edits.
- Petclinic: `58c3310e36c7d827959df6af4d64bdeb8d81f1ea`; JHipster: `f8da577c944ecc4db46fc961a1ba022d5bbf8964`.
- Both Java checkouts were source-clean but had untracked `.tmf/`; hashes/status are recorded in `REPORT.json`.
- Protocol and manifest hashes are in `REPORT.json`; task order: P02, P04, P01, P03.

## Proxy outcomes
- SOURCE_ONLY: accuracy 0/4; citation accuracy 1/4; mean 4.0 files / 421.75 lines / 5 calls.
- TMF_MAP: accuracy 1/4; citation accuracy 2/4; mean 4.0 files / 381.25 lines / 7 calls.
- TMF_FRESHNESS: accuracy 2/4; citation accuracy 2/4; stale conflict blocked 1/1; mean 4.0 files / 381.25 lines / 7 calls.

The apparent TMF gain is inseparable from the scripted symbol seeding and must not be presented as model performance. It reduced mean read lines by 9.6% but added two proxy calls. The freshness arm blocked the single injected stale conflict and reread the 53-line changed `VisitScheduler.java`; n=1 gives no reliable rate estimate.

## Historical audit and bias controls
The existing `bench/agent_ab` is explicitly a deterministic retrieval skeleton, budget 6, not LLM success. It fixes a git-backed source universe, isolates reports/scripts, validates goldens, and warns not to tune after results. No reusable source Phase-B runner remained—only stale `__pycache__` artifacts and an archived patch; the old value-proof archive itself was absent (only SHA256 sidecar), so old outcomes were treated as contaminated/unavailable. The new protocol retains deterministic budgets/universe hashes but adds real Java commits, three arms, stale paired conflict, blind goldens, fixed randomized order, line/token/time/adoption metrics, and explicit failure accounting.

## Failures / runner bias / statistical limits
1. Real agent execution did not complete; current numbers are proxy-only.
2. TMF_MAP proxy has privileged hand-coded Java seed paths; this mechanically favors TMF and is the dominant runner bias.
3. P03 is design-only rather than an applied patch because uncontrolled checkout edits were avoided; local-change correctness is weakly tested.
4. Four tasks, one repo used in execution, and one stale pair are far below inferential sample size; no confidence intervals or significance test are appropriate.
5. Wall time is local Python scan time and context tokens are byte/4 estimates, not provider usage.
6. Untracked `.tmf/` means checkout status is not fully clean, although pinned source commits are unchanged.

## Reproduction
`python3 bench/agent_ab/java_real_v1/runner.py`

Before any value claim, rerun with a working ACP/provider, identical model/temperature, at least six completed runs per arm, fresh isolated clones/worktrees, automatic trace accounting, and a second project (JHipster). Do not alter tasks after observing this pilot.
