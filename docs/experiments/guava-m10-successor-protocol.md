# Guava M10 successor: frozen information-condition protocol

This protocol concerns a single bounded Guava fixture. It is not evidence that
TMF is generally reliable, that a host reflex is armed, or that freshness means
semantic correctness. Historical M10 results remain historical, confounded
observations; this work does not replace or reinterpret those records.

## Scope and operational task

The boundary is the handoff **out of the queued per-thread Dispatcher
implementation and into the Subscriber implementation**. It is not the final
framework-to-user-listener boundary: Subscriber still performs executor and
reflection work. The common task defines ownership, not a correct helper name.

The permitted change is one invocation of the existing no-op `hook()` in
`Dispatcher.java`. Do not add/remove definitions or change other executable
code. Ordinary whitespace and comments do not affect placement scoring; Java
Unicode escape sequences are explicitly outside the accepted subset because
javac expands them before lexing, unlike the scoring parser. Other fixture
sources remain readable but immutable. These constraints are identical for all
conditions and keep this a placement task, not a general Java refactoring task.

## Six conditions and intended differences

| Condition (harness only) | Model-visible evidence |
| --- | --- |
| SOURCE_ONLY | None |
| STALE_WITHHELD_VISIBLE_RECEIPT | Actual failed-binding receipt; no old payload |
| PREREAD_STALE_SOURCE | Frozen old source and recorded boundary conclusion |
| STALE_DOC_CONTROL | Declarative historical documentation; no placement command |
| STALE_WARNING_ONLY | Same old source/conclusion/provenance as trusted source, with stale status and the same failed-binding locator |
| STALE_WITHHELD_SILENT | None; byte-identical to SOURCE_ONLY |

All conditions use the same system/task text, source files, tool schemas,
workspace display name, budgets, feedback and stopping rules. No arm label,
schedule, seal, claim store, repository metadata, evaluator output or absolute
workspace path is exposed through a model-facing tool. The common prompt does
not describe the existence of experimental arms. A status label is the intended
treatment, not a license to add commands to trust, ignore, reread or prefer a
particular patch site.

## Production binding and gate

1. Verify the complete frozen T0 fixture and deterministic Git identity.
2. Derive the target and unchanged control through `derive_claims_for_path`.
   Freeze only the bench clock input, not production extraction or freshness.
3. Keep the complete serialized production claims, including derivation versions.
4. Validate the separate historical memory against T0 source. Production's
   structural claim does not itself derive the richer semantic conclusion.
5. Bind that exact frozen memory to the target claim and attest its bytes.
6. Require target/control FRESH at T0, with no stale reasons.
7. Apply only the frozen mutation; compare the exact diff and all T1 file hashes.
8. Require the target's sole stale reason to be the intended Java hash mismatch;
   the control must remain FRESH. Check compilation independently at both phases.
9. Evaluate the same bound memory through production freshness. This actual gate
   decision supplies the receipt. Exposure conditions deliberately expose the
   verified candidate payload; withholding conditions use the gate's exclusion.

Unknown states are not admitted as the intended stale treatment. The general
memory gate may withhold unknown evidence, but this fixture specifically requires
the registered Java-hash transition. No arm may synthesize a receipt independently
of the validated memory and gate event.

## Scoring and reporting

The oracle identifies the complete enclosing class and method signature, target
receiver and arguments, and direct executable statement order. It compares the
remaining executable AST with the frozen T1 reference after removing the single
added hook call. Deferred/dead code, changed call chains, added overloads, wrong
arguments and unrelated executable changes cannot masquerade as correct placement.

Report separately:

- placement: current, obsolete per-thread queue loop, other, no effect, invalid
  source/constraint violation;
- compilation, including compiler failure or unavailability;
- protocol: final/no-final, invalid actions, edit errors, timeouts and budget stops;
- source acquisition: reads/files/bytes and order; and operational usage.

Every admitted attempt remains in the intent-to-treat denominator. An admission
record precedes workspace or adapter work. Crashes and missing completion records
remain incomplete admitted attempts. Score the final available source even when
there is no final message or the protocol is noisy. Never replace ITT with a
protocol-clean subset; such subsets, if later approved, are sensitivity analyses.
Scoring is post-run only and its answer is never returned by `compile`.
The obsolete-loop diagnostic means insertion anywhere in that old inner loop,
not necessarily immediately before its current call. Only the current-boundary
success criterion requires exact adjacency.

## Runtime and execution boundary

The current deliverable is a deterministic **scripted protocol rehearsal**. It
uses the real source tools, edit mediation, compiler and scorer, with prewritten
responses instead of a subject model. Scripted results are not agent results and
cannot support H1/H2/H3.

Live/paid model execution is disabled. The protocol's UTF-8 byte budgets are
enforced byte budgets, not tokenizer measurements. A future live adapter must
demonstrate actual provider token-limit propagation and trustworthy usage
accounting, pin model/provider/version and runtime, and receive separate explicit
authorization before any model call. A placeholder or mock transport is not that
evidence. Offline readiness never implies live-model admission.

## Sealing and randomization

The stable seal covers all T0/T1 source files, full claims and memory, mutation,
gate receipts, rendered condition inputs, source-tool schemas and budgets,
implementation/dependency bytes, actual compiler inputs, interpretation rules,
and randomized schedule. Runtime timestamps, random temporary paths and timing
measurements are not scientific protocol identity. Retain their provenance
separately when needed. Store canonical claim bytes, not only their hashes.
The compiler uses the same resolved executable and an explicit minimal
environment for version discovery and compilation. No inherited Java options or
classpath variables reach it. Seal the complete modular JDK runtime libraries,
`lib/modules`, configuration and release identity, not merely the javac launcher.
This runner supports a complete modular POSIX JDK. It is not an OS container
reproducibility claim; seals bind the measured Python/parser/JDK environment and
must be regenerated after an environment change.

Use a fixed schedule seed and shuffle all six conditions once per block. Opaque
run IDs are harness metadata only. Store the mapping for reproducibility but do
not expose it to the model. Validate the seal and recompute deterministic
preflight, arm and oracle checks before admitting any run; failure means zero
adapter calls. Changes to frozen inputs require a new seal, not in-place repair
of old records. Never rerun only an unfavorable condition to replace its result.

## Interpretation commitments before model results

- Trusted stale source versus SOURCE_ONLY tests induced stale-context poisoning.
- Warning versus visible withholding tests their **incremental** difference; a
  null or imprecise result is not proof of equivalence.
- Visible versus silent withholding tests the receipt/locator treatment as a
  whole. Read telemetry can support reorientation, not prove hidden cognition or
  a separate causal mediation mechanism.
- Silent withholding versus SOURCE_ONLY is a negative-control check of hidden
  harness effects; their model-visible inputs must be identical.
- The documentary condition is supplementary: it differs in representation and
  length from prior-source exposure and cannot isolate those factors.
- If warning is sufficient, do not claim added value for hard withholding. If
  silent withholding suffices, do not credit a visible reflex signal. If stale
  exposure is harmless, report that result. Matching SOURCE_ONLY can be useful;
  small numerical superiority is not a superiority claim.

A future model pilot is for protocol failures only. Outcomes must not be used to
tune task wording, mutation or scoring direction. Before any main model run,
freeze sample size, primary contrasts, uncertainty/multiplicity rules and any
equivalence/non-inferiority margins. Do not choose these after seeing pilot arm
outcomes. No such model run is authorized by this protocol or by an offline PASS.

## Reproduction (no model credentials or network execution)

Install the project's pinned Java parser extra and prepare the five Maven JARs
listed in `m10_successor_fixture_spec.json`. CI explicitly fetches these locked
coordinates; the runner itself never downloads dependencies. The historical
classpath is relocated to the current home Maven repository if needed, or set
`TMF_M10_SUCCESSOR_CLASSPATH` to the ordered local files; their bytes must match
the specification. No model or broker credentials are needed.

```sh
python -m unittest discover -s tests -p 'test_*m10_successor*.py' -v
python -m bench.agent_ab.same_version_chain_v1.guava_m10_successor_runner prepare-seal --output /tmp/successor-seal.json
python -m bench.agent_ab.same_version_chain_v1.guava_m10_successor_runner protocol-rehearsal --manifest /tmp/successor-seal.json --output /tmp/successor-rehearsal
```

Output paths must be new; existing evidence is never replaced. The six-condition
rehearsal deliberately supplies a known-answer script in every condition. Its
pass rate is infrastructure evidence only, not an estimate of subject-model
accuracy or an arm comparison. Keep `model_pilot_admitted=false` until the
separate real-adapter/token-contract and authorization gate has been satisfied.
