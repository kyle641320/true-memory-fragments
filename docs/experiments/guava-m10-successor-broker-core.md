# Successor broker execution core: offline-verified, not deployed

This stage implements the **server side** of the candidate v2 protocol. It is
separate from the [client codec](guava-m10-successor-adapter-contract.md) and the
[earlier process rehearsal](guava-m10-successor-process-rehearsal.md), whose peer
produced canned v2 completion receipts. Here a real request-processing core
validates the request, obtains a fresh count, durably reserves its own budget,
calls a backend once, and constructs a receipt from the original backend JSON.
The exercised backend remains a fixed fictional fixture with no network path.

| Layer | Implemented evidence | Not established |
| --- | --- | --- |
| Client codec and ledger | Local request, identity/cap/usage checks and durable accounting | Truth of provider assertions |
| Bounded process I/O | Actual child processes, byte/deadline limits and cleanup | Remote request cancellation or OS sandboxing |
| Broker execution core | Independent server validation, count check, admission, replay protection and response accounting | Compatible deployed provider, tokenizer or runtime identity |
| Fixed backend fixture | Deterministic original-response and fault inputs | Any measured tokens or model behavior |

## Server-owned authority and lifecycle

`BrokerCore(contract, ledger, backend, max_request_frame_bytes=...).handle(request, deadline_monotonic=...)`
uses the contract and ledger supplied by its trusted owner. An incoming request
cannot select another provider, model, inference setting, budget, backend or
executable. The internal backend seam has three operations: capability bytes,
exact-count receipt bytes and original upstream completion JSON bytes. It has
no dynamic provider/plugin loader or credential configuration path.

The explicit full-frame byte cap is independent of the model-payload cap;
source history and JSON escaping in the outer request do not silently consume
the model's allowed payload capacity. Original response bytes and the wrapped
receipt are each bounded; wrapping a near-limit response may cause failure,
but must not erase already observed usage or trigger a replacement request.

The core validates bounded canonical UTF-8 requests, exact fields, protocol,
hashes, model/inference pins and output limits. A completion's source request
is independently re-rendered with the existing codec: recalculating a hash over
a changed provider payload does not grant authority. A count-only request has
no source transcript, so its submitted provider body has separate structural
and pinned-field validation; the later completion still requires the full
source re-rendering check.

Before backend work, the ledger must have the same limits, verified integrity,
no pending call and no terminal halt. A replayed completion call ID cannot
trigger even another capability/count operation. Completion performs a fresh
count for the exact payload and compares it with the client's count; it does
not trust the count merely because the client submitted it. Capability/count
receipts are assertions that must satisfy the contract, not independent proof
that a real deployment implements them.

The broker reserves and fsyncs its own journal before the single completion
dispatch. It never retries, falls back, silently truncates or repairs an invalid
request. Unknown outcomes stay charged and terminal. Valid observed usage must
remain accounted for even when the output is rejected for a wrong identity,
refusal or truncation; an invalid result is never made usable just to retain
its usage. The core preserves original response fields instead of fabricating
an expected model name or usage. Errors expose fixed categories, not backend
exception text. An unverified final journal cannot certify a success.

## Two journals, not one misleading success flag

The fixture process harness keeps **independent client and broker journals**.
Both reserve before their respective dispatch boundary. It reopens the broker
journal across worker processes, including replay and killed-worker cases.
An external process timeout is not proof that the broker or a future upstream
provider consumed zero resources.

The journals can honestly differ. For example, the broker may have received a
response with valid usage but a wrong model identity, while the client receives
only a failure and retains an unknown full reservation. A broker may also
settle durably just before the client process deadline expires. Keep both
records; do not rewrite known broker usage into unknown, refund the client, or
call local process termination proof of remote cancellation.

The core shares an absolute deadline across backend phases and checks returned
responses against it. A synchronous Python callback, filesystem operation or
fsync cannot be preempted by a timestamp check. The process harness supplies an
outer bounded process-I/O guard; this is not an OS sandbox or remote guarantee.
The existing process guard has a separate bounded direct-child cleanup wait.

## Fixed offline execution

```sh
python -m unittest discover -s tests -p 'test_m10_successor_broker*.py' -v
python -m bench.agent_ab.same_version_chain_v1.m10_successor_broker_rehearsal --output /tmp/tmf-broker-core-rehearsal
```

The output directory must be new. The harness executes actual child workers
with the broker core and a fixed local backend. All counts of 6000 input tokens
and 32 output tokens are **fictional fixture values**, never measured usage.
All test records retain `model_calls=0` and deny live-pilot/provider-verification
claims. The selected failure scenario and local paths are worker provenance,
not additions to the submitted model payload. Trace evidence records what the
backend received and whether another completion was attempted.

The scenarios cover success, legacy capabilities, inexact counting, count and
completion timeouts, backend exceptions, malformed/oversized responses,
missing usage, wrong original model, refusal and truncation. A negative test
passes only for the intended protocol/accounting outcome. The summary must
verify every requested scenario, distinct IDs and all saved records, rather
than replacing missing cases with repeated successes. A fresh worker must
reject a replayed completed request without a second backend dispatch.

Materials, runtime identity, caps and the candidate contract are sealed; source
drift must stop subsequent exchange. This local seal is not full OS/shared
library attestation and does not establish a remote deployment identity.

## Live work still outside this stage

The internal backend interface is a future integration seam, **not** a live
authorization service. The public rehearsal binds only the fixed fixture; the
scientific runner still only admits its exact scripted adapter, and the existing
`execute_model` remains disabled. No live HTTP/provider adapter, exact tokenizer
service, host deployment, credentials or gateway changes are supplied here.

Still required before any live protocol pilot:

1. A concrete provider/backend implementation and verified deployed identity,
   original response identity, inference settings, exact full-payload counting,
   output-cap forwarding, usage and no-hidden-retry behavior.
2. Live-runner admission before **any** adapter work, experiment-level ITT,
   actual runtime/network/credential/tool boundaries and a jointly consumed
   experiment-and-adapter seal. A broker call journal is not the run denominator.
3. Explicit authorization for a concrete real conformance/pilot plan and hard
   budget. Passing these tests does not provide that authorization.

No engine, README, release version, historical result or model-effect claim is
changed by this implementation. Readiness is limited to **offline broker-core
conformance**, not a live-model pilot.
