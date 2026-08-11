# Java Real Agent A/B v1 Protocol (FROZEN)

Status: pilot protocol frozen 2026-08-11; no TMF engine/parser/build-adapter changes; no commit/push.

## Scope and arms
Three treatment arms use the same current model, prompt, temperature, timeout, task order random seed, and tool budget. SOURCE_ONLY has filesystem/search/build tools but no TMF. TMF_MAP additionally has `retrieve`, `context`, and relation lookups, with no preloaded task-specific memory. TMF_FRESHNESS starts with an old claim snapshot, then must inspect freshness after a prescribed code mutation and locally reread changed source. A stale-conflict paired task is analyzed separately; it is not mixed into ordinary accuracy.

## Fixed corpus
Primary corpus is local `spring-petclinic-modulith` commit `58c3310e36c7d827959df6af4d64bdeb8d81f1ea`; secondary candidate `jhipster-sample-app` commit `f8da577c944ecc4db46fc961a1ba022d5bbf8964`. Both checkouts currently contain untracked `.tmf/` generated state, so workspace cleanliness is recorded and is a pilot limitation. Goldens are outside the runner's prompt input and are never shown to agents.

## Tasks
P01定位: trace booking from controller/service through event listener; cite source lines. P02影响分析: identify consumers and transaction/event boundary of `VisitBooked`. P03局部修改/验证: propose a minimal validation change for booking and name targeted tests/build command; no uncontrolled edits in pilot. P04 stale-memory conflict: old claim says booking publishes before flush; mutation changes ordering to publish-before-flush; detect stale claim, reject it, reread only VisitScheduler and direct listener/test neighborhood. Each core type has at least one sample; pilot n=4 task instances per arm (12 runs), because external model execution was unavailable within timeout, so deterministic harness proxy is explicitly labeled non-LLM.

## Randomization/blinding
Task IDs are assigned by SHA256(seed `java_real_v1:2026-08-11`) permutation and each arm receives the same permutation. No task/golden changes after results. Prompts contain no golden symbols beyond natural user request. Manifest pins all hashes.

## Metrics
Record correctness, source citation correctness, source files and line ranges read, approximate input/output tokens, wall time, tool calls, TMF adoption, stale error/block rate, and local reread span. Correctness is judged against held-out goldens by the evaluator, not agent self-report. Build/verification outcomes are recorded separately.

## Reproducibility and limits
Runner records git commits, workspace status, protocol/manifest hashes, model settings, and tool budget. This pilot uses a deterministic source/TMF retrieval proxy because ACP model invocation failed (session init / timeout); it cannot establish LLM task success or causal net benefit. Full real-agent rerun is required before a go/no-go conclusion.
