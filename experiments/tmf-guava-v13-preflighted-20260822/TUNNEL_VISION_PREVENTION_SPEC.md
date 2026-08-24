# Tunnel Vision Prevention Experiment Spec (Guava)

## Goal

Evaluate TMF as a correctness / bug-prevention mechanism, not as a token-saving or read-minimization mechanism.

Primary question:
- Does TMF reduce tunnel-vision bugs when an agent edits code in file A after a stale dependency in file C has changed?

## Hypothesis

If TMF detects stale dependency fragments and forces a localized reread of the changed boundary, then agents will introduce fewer tunnel-vision bugs than a source-only baseline.

## Non-goals

- Not a benchmark for token efficiency.
- Not a benchmark for fewer reads.
- Not a benchmark for faster completion.
- Not a generic code-generation benchmark.

## Core design

### Arms

1. SOURCE_ONLY
   - Agent receives t0 chain understanding only.
   - No stale detection.
   - No forced local reread.
   - Agent edits file A directly.

2. TMF_PROTECT
   - Agent receives t0 chain understanding plus TMF fragment hooks.
   - When dependency C has drifted, TMF blocks stale continuation.
   - TMF forces reread of C fragment before allowing edit in A.

### Fixture shape

Use a real Guava / Java chain with 4-5 files and a meaningful causal dependency path.
The chain must be deep enough that a tunnel-vision bug is plausible.
Examples of dependency shape:
- A -> B -> C -> D
- C contains a transactional / publication / boundary decision.
- A is the file the agent is asked to modify.
- A local change can become wrong if C has drifted.

### Mutation principle

The mutation must be designed so that:
- Looking only at A is insufficient.
- Re-reading C changes the correct edit in A.
- The stale edit should be plausible and mechanically detectable.

## Three stages

### Stage 1: t0 chain understanding

Both arms read the full chain A->B->C->D.
The TMF arm also produces a bounded fragment for C.

Important:
- Keep only the fragment, not the final answer.
- The answer from this stage is discarded.

### Stage 2: t1 mutation

Mutate C so that a stale mental model becomes dangerous.
Examples:
- transaction propagation changes
- event ordering changes
- commit/publish ordering changes
- return-value semantics change

The mutation must create a case where an A-only edit would be wrong, but a reread of C would expose the correct edit.

### Stage 3: t2 modification task

Ask the agent to modify A, for example by adding a new call or message send.

- SOURCE_ONLY: agent edits A directly.
- TMF_PROTECT: stale fragment detection triggers a block, then TMF forces reread of C, then agent proceeds with the fresh C view.

## Oracle

Use a mechanical oracle, not an LLM judge.

Oracle should verify:
- Whether the edit preserves the causal / transactional / publication ordering guarantee.
- Whether the patch position is correct relative to the boundary in C.
- Whether the bug is tunnel-vision-shaped, i.e. caused by relying on A while ignoring the mutated C boundary.

Possible mechanical checks:
- static assertions over method call order
- source pattern checks around transaction annotations / publish calls / commit points
- unit tests that fail for the tunnel-vision patch and pass for the corrected patch

## Metrics

### Primary metric: correctness

- Bug rate per arm
- Whether the patch violates the mechanical oracle
- Whether TMF reduces tunnel-vision bugs versus SOURCE_ONLY

### Secondary metric: efficiency

- reread count
- token count
- tool-call count

Efficiency is secondary only.

## Success criteria

TMF is valuable if:
- TMF_PROTECT has materially lower bug rate than SOURCE_ONLY
- even if TMF uses more reads/tokens

## Failure diagnosis

If both arms have similar bug rates, diagnose:
- mutation did not create a true tunnel-vision trap
- stale detection did not trigger
- agent ignored the TMF fragment
- oracle was too weak

## Pre-registration rules

Before running:
- freeze the task list
- freeze the mutation list
- freeze the oracle
- do not rewrite the success criterion after seeing results

## Suggested minimum sample

Run 6-10 mutation scenarios, with both arms per scenario.

That is the minimum to distinguish:
- TMF really prevented bugs
- vs. the task just happened to be easy

## Important interpretation rule

A result where TMF is slightly slower but significantly less buggy is a win for TMF.
This experiment is about correctness first.
