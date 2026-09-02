# Java Real Stale A/B v4 — three-fixture deterministic gate

Status: **DETERMINISTIC_FIXTURES_VALID__AGENT_RUNS_NOT_STARTED**.

This extends the v3 single Petclinic event smoke into three independent real-repo stale-contract fixtures. No correctness/productivity claim is made yet; this report only freezes and validates the next experiment objects.

## What was built

Base real repository: `/root/.openclaw/workspace/experiments/tmf-java-validation-20260806/spring-petclinic-modulith`.

Controlled mutated copies under `/root/.openclaw/workspace/experiments/tmf-java-real-v4/`:

1. `petclinic-api-route`: `OwnerController.showOwner` old GET `/owners/{ownerId}` becomes GET `/owners/{ownerId}/profile`.
2. `petclinic-cache-name`: `VetRepository` old `@Cacheable("vets")` declarations become `@Cacheable("activeVets")`.
3. `petclinic-transaction-readonly`: no-arg `VetRepository.findAll` old `@Transactional(readOnly = true)` becomes `@Transactional(readOnly = false)` while the pageable overload remains unchanged.

Each copy was initialized as a git repo, warmed through repo-local TMF before mutation, then committed with a controlled stale-contract mutation.

## Deterministic gate

`results/deterministic_eval.json` validates all three tasks:

- `RV4F01`: 1 relevant old route claim, 1 stale, current target route present.
- `RV4F02`: 2 relevant old cache claims, 2 stale, current cache name present.
- `RV4F03`: 2 relevant old transaction claims, 2 stale, current no-arg `findAll` transaction annotation present.

Summary: `valid_tasks=3`, `all_valid=true`.

## Interpretation

This is the right next gate after RV3F01: v3 proved one real stale fixture and showed equal-budget SOURCE_ONLY can also answer correctly. v4 now provides three additional real stale fixtures across different Spring contract types: API route, cache declaration, and transaction declaration.

Next step is not to overclaim from deterministic validation. The next valid experiment is repeated SOURCE_ONLY vs TMF_MAP runs on these three fixtures, scoring:

- stale note trusted vs blocked,
- current source citation correctness,
- files/lines/tool calls/wall time,
- transport/protocol failures separately from semantic failures.
