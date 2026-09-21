# Successor runner–broker bridge: offline integration only

This stage connects the scientific action loop to the actual broker execution
core through real bounded worker processes. The backend is still a fixed,
fictional five-action script, identical for every condition. It is **not** a
provider adapter, live pilot, model-effect result, or operating-system sandbox.

## Three independent accounting boundaries

1. Full production preflight and joint-seal verification happen before any
   adapter state is constructed. The entire six-run randomized plan is then
   admitted in one durably recoverable, fsynced batch event. This fixes the
   intention-to-treat denominator before the first possible broker request.
2. Each run starts durably before its adapter factory. It uses the existing
   private source workspace, action schemas, byte/turn budgets and independent
   semantic/compilation evaluations. The old public scripted entry still
   rejects custom or live adapters.
3. All runs and turns share one persistent client token journal and a separate
   broker token journal. They enforce explicit aggregate limits rather than
   resetting the budget for each run. Their call admissions are **not** the
   scientific run denominator.

The batch stops on its first protocol, accounting or integrity failure. All
scheduled run IDs remain in ITT, including interrupted and not-started runs.
There is no retry, replacement run, successful-only denominator or automatic
resume. Reopening the run journal is inspection-only. File corruption is
reported, never silently interpreted as a shorter successful batch.
Observed integrity uncertainty is sticky even if a later reopening reads valid
bytes. The live snapshot and each integrity observation remain in the report.
A process interruption may leave no summary: that is a fatal incomplete batch,
not a batch to omit. Reopen the existing run journal for inspection to recover
every admitted ID; the CLI aborts instead of filtering it out or resuming it.

## Joint seal and dispatch guard

The joint seal binds the complete scientific manifest, fixed broker contract,
process limits, run-ledger policy, global token limits, fault scenario and all
bridge implementation materials. The model receives none of the run IDs,
absolute paths, arm labels, scores, fault settings or seal metadata.

Full deterministic freshness/arm/oracle preflight runs at sealing and each run
admission. Before every capability/count/completion subprocess, the guard
rechecks the joint digest, the scientific implementation and parser/runtime
inventories, actual compiler/JAR fingerprints, immutable T1 template and exact
schedule/input/budget bindings. Recompilation on every frame is unnecessary
when those sealed inputs are unchanged. The guard checks the immutable
template, not the deliberately edited private workspace.

One absolute broker-turn deadline starts before these checks and serialization.
Its effective value is the minimum of the scientific request budget and the
fixed **10-second** offline broker cap, identical across arms and recorded
outside model context. Guard time is not free or a reason to restart a timer.
Byte budgets and fictional token accounting remain distinct.

## Offline evidence and limits

The known-answer script performs list, source read, one correct hook edit,
compile and final. The original backend JSON is validated and wrapped by the
real BrokerCore; the fixture does not synthesize successful v2 receipts. Full
history and action schemas are re-rendered on every turn. The fixture's counts
of 6000 input and 32 output tokens are **fictional**, not tokenizer measurements.

Success requires six included runs, six protocol completions, independent
semantic/compile results, intact run/client/broker journals and the expected
five-action trace per run. SOURCE_ONLY and silent-withholding payloads must be
byte-identical across the whole resulting trajectory. Positive infrastructure
scores do not support any claim about TMF improving a model.

Fault batches exercise wrong identity, missing usage, timeout, invalid action
and aggregate-budget exhaustion. A valid broker cost can coexist with unknown
client usage. Keep both journals; local process termination does not prove
upstream cancellation. Unknown charges are not refunded.

Still required for a live pilot: a selected real provider/model and deployed
backend, verified original identity/inference/count/output-cap/usage semantics,
actual credential/network/runtime isolation, a jointly verified live execution
path and explicit authorization of a concrete call plan and hard budget.
This bridge has no CLI live unlock, provider selection or arbitrary executable.
The existing execute_model remains disabled. No engine or release is changed.

## Reproduce

With the frozen compilation dependencies already installed (the mandatory CI
job installs them explicitly), run:

    python -m bench.agent_ab.same_version_chain_v1.guava_m10_successor_runner prepare-seal --output /tmp/tmf-scientific-seal.json
    python -m bench.agent_ab.same_version_chain_v1.m10_successor_runner_bridge --manifest /tmp/tmf-scientific-seal.json --output /tmp/tmf-bridge-evidence

The output directory must be new. All six batches run, including the five
negative cases; an unrelated early failure does not satisfy their oracle.
The verifier reopens all three journals, independently aggregates all admitted
IDs, reconstructs full-history model payloads and verifies original response,
wire and backend trace files. Expected totals are 36 admitted scientific runs,
44 fictional completion callbacks and 134 real worker attempts, with zero
model calls. These are infrastructure outcomes, not scientific arm results.
