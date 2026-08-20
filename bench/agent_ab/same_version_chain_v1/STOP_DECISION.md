# same_version_chain_v1 STOP_DECISION

Date: 2026-08-20 Asia/Shanghai
Status: **SMOKE FAILED — full run not started**

## What ran

Smoke run `smoke-n2`: B01 + B02 across all 3 arms (`SOURCE_ONLY`, `TMF_CLAIMS`, `DOC_CONTROL`) on the same Guava EventBus source, no version mutation.

Artifacts:
- `results/smoke-n2.json`
- `results/SMOKE_REPORT.md`
- full raw transcripts under `results/raw/smoke-n2/*.raw.json`

## Gate result

Failed.

- Valid answers: 4/6 overall
- B01 valid answers: 3/3
- B02 valid answers: 1/3 (**fails >=2/3 valid-answer gate**)
- Trap differentiation: yes for B02, no for B01
- Harness/runtime errors: 0

## Failure modes

1. B02 SOURCE_ONLY and DOC_CONTROL returned plausible final answers but made no file edits (`modified_files=[]`). They were marked invalid despite compile passing because the task is a coding modification task.
2. B01 did not differentiate arms: all three arms found the Subscriber-layer solution and passed the syntactic trap check.
3. Verification is not yet a full behavioral Guava/JUnit test suite. The runner performs compilation and machine audit over diffs/transcripts for expected layer/chain coverage. It does not prove runtime rate limiter/retry/log semantics exhaustively.

## Decision

Per protocol, stop after smoke failure. Do not run full 3-task x 3-arm matrix unless the harness/task protocol is revised.
