# Authoritative Agent runtime value status

**Single authoritative experiment ruling — 2026-08-13, base `45ab3e4`.** Read this page before interpreting any older A/B report. Older reports preserve their original observations; they are not interchangeable because they test different delivery modes.

## Current ruling

| Evidence | Result | What it proves |
|---|---|---|
| Tool-mode Java real v1/v2 | no observed advantage when the Agent must actively retrieve TMF | Negative only for proactive/tool retrieval; **not** evidence that forced middleware is ineffective. |
| Retrieval E2E v1 | smoke stopped on retrieval relevance/value gates | Negative within that lexical retrieval protocol; not a universal memory ruling. |
| `middleware_hardening_v1` | mechanism hard gates **5/5 pass** | Exact-target/freshness injection, stale blocking and localized reread mechanics work on those fixtures. It does **not** prove Agent adoption or task value. |
| `agent_middleware_value_v1` real Agent smoke | **2/2 valid pairs**, SOURCE 2/2 success, TMF 2/2 success, TMF adoption **0/2** | No task regression in smoke, but no demonstrated adoption, repeat-read reduction, token/cost or wall benefit. Frozen adoption stop gate fired; full 10-pair run was not executed. |

### Product decision

**Do not recommend TMF_MIDDLEWARE for production on an Agent-value, speed, token, or reread-reduction claim.** It may be used only as an experimental safety/navigation mechanism where users explicitly accept unproven outcome value and count injection cost. Continue to recommend source-authoritative fallback and the hard freshness/stale gate as a qualified mechanism, not as a productivity win.

Evidence level is **mechanism-qualified / Agent-outcome-unproven**. The real smoke was descriptive (N=2), not statistically significant. Semantic-mutation Agent outcome, stable adoption across task classes, Python/Java edit-and-fix breadth, and net economic value remain unproved because the pre-registered smoke gate correctly stopped the full run.

## Real Agent outcome details

The comparison used stateless `gpt-5.6-sol`, the same prompts/order/tool/source/turn and call budgets, a raw-inference safety broker, isolated fixture copies, and a controlled autonomous read/search/edit/test loop. Middleware was the unchanged `45ab3e4` implementation and was forced immediately before selected reads; it did not depend on proactive TMF calls.

| Task | Mode | SOURCE | TMF | Audited adoption | Reads S/T |
|---|---|---:|---:|---:|---:|
| A01 Python understanding | fresh revisit | pass | pass | no | 1/1 |
| A03 Python local edit + test | fresh revisit | pass | pass | no | 1/1 |

Aggregate: source bytes 173/173, tool calls 8/8, estimated prompt tokens 1406/1874, completion 168/181, TMF injection 0/236, wall seconds 25.68/33.98 (SOURCE/TMF). No memory, stale-memory, post-reread, baseline, output-contract, runtime, or middleware errors occurred. Adoption is machine-audited and does not rely on model self-report.

## Experiment index and non-mixing rule

- Real forced-middleware value: [`bench/agent_ab/agent_middleware_value_v1/`](../bench/agent_ab/agent_middleware_value_v1/) — protocol, frozen hashes, raw machine JSON, paired CSV, human audit.
- Mechanism only: [`middleware_hardening_v1`](../bench/agent_ab/middleware_hardening_v1/).
- Retrieval E2E: [`retrieval_e2e_v1`](../bench/agent_ab/retrieval_e2e_v1/).
- Active tool-mode Agent trials: [`java_real_v1`](../bench/agent_ab/java_real_v1/) and [`java_real_v2`](../bench/agent_ab/java_real_v2/).
- Historical revisit/path-injection studies are narrower simulated or mediated protocols.

**Never combine denominators or conclusions across tool retrieval, supplied-evidence broker answers, mechanism fixtures, and forced real-Agent middleware.** Commit under evaluation: `45ab3e43f8a8e3ef12b08c5c6bed76d1dade7d48`; experiment artifact commit is recorded in repository history after this page is committed.
