# Successor process transport: offline conformance, not provider validation

The [candidate data contract](guava-m10-successor-adapter-contract.md) now has a
separate process-level rehearsal. It executes real child processes with stdin,
stdout and stderr, validates their v2-shaped receipts through the existing
codec, and applies the existing durable token ledger. It does not replace or
enable the experiment runner: that runner still requires the exact scripted
adapter type, and `execute_model` still unconditionally rejects execution.

## Public boundary

`offline_contract` and `rehearse_turn` support only a bundled, fictional peer:

- Provider/model `tmf-offline-fixture`, endpoint `https://offline.invalid/...`.
- Fixed peer source; no user-supplied command, executable, script, network
  callback, host broker path, credentials or configuration source.
- All input counts (6000) and output usage (32) are **fictional test values**.
  The count receipt uses the wire protocol's required fields solely as a test
  fixture; it is not a tokenizer or measured provider count.
- Fixed source snapshot executed with resolved Python `-I -S -B -c`, no shell,
  no site packages, no inherited credential environment, and an empty private
  working directory. The peer imports only stdlib JSON/hash/time/system code
  and contains no network/model path.

The private I/O primitive accepts source bytes to permit isolated fault tests;
it is not a public broker-launching API or a security sandbox for hostile code.
Environment stripping and a temporary cwd are **not** filesystem or network
namespace isolation. Python executable bytes/version and repository materials
are sealed; this is not a complete OS/runtime-library attestation.

## Runtime guarantees under test

1. Reject non-fictional identities, invalid requests, existing halted/pending
   ledgers, changed materials and oversized IPC frames before a new exchange.
2. Carry one absolute process-I/O deadline across capabilities, counting and
   completion, including setup, serialization, request writes, simultaneous
   stdout/stderr reads, process exit and pipe EOF. Never restart the allowance
   after serialization or launch a completion child after expiry. This is not a
   preemptive timeout for arbitrary filesystem/OS calls or final ledger fsync.
3. Enforce an independent cap on the entire IPC frame, not just the submitted
   model payload. Check stdout/stderr caps while reading, never after unbounded
   buffering. Do not let a non-reading child deadlock a large stdin write.
4. Start each child in a new session/process group. On timeout or transport
   failure, kill the group and reap the child with a separate allowance of at
   most one second for the direct-child wait. This verifies
   local cleanup only; it would not prove remote cancellation of a real request.
5. Do not treat valid JSON followed by an abnormal process exit as a successful
   response. Do not accept multiple JSON frames or unbounded stderr output.
   Reports retain only stderr byte counts, not potentially sensitive contents.
6. Fsync the reservation **before** starting the completion child. Pre-admission
   failures retain their failure records but have no candidate-call reservation.
   After reservation, any transport/receipt uncertainty retains the full charge,
   unknown usage and a terminal ledger; there is no replacement child/retry.
7. Refusal/truncation with a valid usage receipt remains a failed outcome with
   known fictional usage. Corruption/write failures cannot become certified
   success or free capacity. An already halted/pending ledger cannot launch
   another rehearsal turn.

The token ledger counts candidate calls, not whole experimental runs. A future
live runner would still need its independent admission/ITT record **before any
adapter work**, including capability/count failures. This rehearsal does not
satisfy that live integration requirement by renaming candidate calls as runs.

## Reproduction and evidence

```sh
python -m unittest discover -s tests -p 'test_m10_successor_process*.py' -v
python -m bench.agent_ab.same_version_chain_v1.m10_successor_process_rehearsal --output /tmp/tmf-process-rehearsal
```

The output directory must be new. The command records all 16 fixed scenarios,
including intentional faults; a PASS means each scenario produced its expected
protocol/accounting outcome, **not** that all responses succeeded. Each scenario
gets a separate ledger because it is a separate conformance test, never a retry
used to replace a bad experimental result. The summary distinguishes candidate
admission from observed errors and labels usage as fictional throughout. It
requires exact requested/returned scenario coverage and distinct call IDs;
duplicate results cannot overwrite missing negative scenarios into a PASS.

The transport seal includes the existing codec seal, process caps, transport,
facade, peer, this document and Python executable identity. Runtime durations,
random correlation IDs and temporary paths are operational provenance rather
than model-visible information or deterministic protocol identity. All statuses
retain `model_calls=0`, `model_pilot_admitted=false` and
`provider_token_limits_verified=false`.

## Still not ready for a live model pilot

This proves the repository's process boundary against a known fixture. It does
not implement/deploy a live broker, establish exact provider token counting or
immutable provider identity, demonstrate cap enforcement or hidden-retry policy,
or validate actual runtime isolation. Those remain the deployment prerequisites
listed in the candidate contract, followed by explicit authorization for actual
conformance calls and the protocol-only pilot. Existing host broker, TMF engine,
README, release versions and published channels are unchanged.
