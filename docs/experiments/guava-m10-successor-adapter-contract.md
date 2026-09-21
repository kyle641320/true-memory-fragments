# Successor broker contract: offline candidate, not model admission

This is the next repository-only step after the
[scripted protocol](guava-m10-successor-protocol.md). The implementation has **no
transport**: no HTTP, socket, subprocess, credential lookup, provider call or
callable injected broker. `execute_model` always raises, and the existing
runner still admits only the exact `ScriptedAdapter` type. Nothing here upgrades
the deployed broker, changes a host configuration, or authorizes a model pilot.

## Why a separate protocol

The historical `tmf-agent-broker-v1` request has a prompt and call-count budget,
not a provider-token contract. Its model-name echo and `stateless` declaration
cannot establish immutable model identity or measured token usage. Keep the old
adapter unchanged for historical reproducibility; reject v1 at the new boundary
rather than silently reducing the successor's output allowance.

The new `tmf-successor-broker-v2` is a **candidate specification implemented as
pure request/receipt codecs plus a durable offline ledger**. No compatible
deployed broker is claimed. Fixture receipts demonstrate how the repository
handles a statement; they do not demonstrate that an upstream provider made it.

## Frozen contract and model-visible representation

`BrokerContract` requires explicit, non-secret pins for:

- the original experiment seal; provider and HTTPS Chat Completions endpoint;
- requested model, expected **original response** model, deployment revision;
- broker build/runtime and tokenizer identity/material hashes;
- inference parameters, input/output/context/whole-run token limits, call limit;
- serialized request/response bytes and deadline limits.

There is no default model/provider or inferred context-window size. A model
alias, a hash of a local broker source file, or `system_fingerprint` alone does
not prove an immutable running model. Operator-supplied pins and matching
self-reported receipt fields remain claims until independently validated.

The four inference fields (`temperature`, `top_p`, `seed`, `reasoning_effort`)
must be present in canonical JSON. Explicit `null` means omit that field on the
wire, **not** that the provider default is known or deterministic. A future
deployment must validate support and resolve such defaults before freezing its
actual pilot contract. This implementation selects no new scientific settings.

The sealed rendering `text-actions-chat-v1` preserves the existing system/user
messages and assistant text. It appends the complete action-schema JSON to the
system message. Protocol-local tool messages have no native tool-call ID, so
they become user messages containing a fixed prefix and their JSON-quoted text.
It does not fabricate native tool calls. This is an explicit common rendering
choice requiring future conformance review, not proof of equivalence to native
function calling. It supplies no condition, schedule position, run ID, absolute
workspace, evaluator result or broker metadata to the model. Opaque call IDs
and contract/receipt metadata stay outside the submitted provider payload.

All history and schemas are included in both the byte cap and the token-count
payload hash. The codec fixes `n=1`, `stream=false`, `store=false`; it supplies
no native tools, fallback model, continuation ID or automatic context truncation.
Changing content, schemas, rendering, inference settings, implementation bytes
or budget pins invalidates the candidate seal. The seal includes the protocol,
codec, ledger, this document and the local Python version. It is not an OS
sandbox or an attestation of a running remote deployment.

## Required request/receipt lifecycle

1. **Prepare locally.** Validate the action request and freeze its canonical
   Chat Completions payload; enforce byte and requested output-token bounds.
2. **Check capability bytes.** Require v2, pinned identity/tokenizer, full exact
   input counting, one attempt, no fallback/truncation/native tools, and broker
   ownership of network/credentials. This operation consumes supplied bytes;
   it does not query any broker.
3. **Check token-count bytes.** Require an exact count tied to the complete
   payload hash, tokenizer and candidate seal, with zero generation calls.
   Estimates such as characters divided by four, or a count of just the newest
   user message, are not accepted. There is no implemented tokenizer or provider
   count service here; that remains a deployment prerequisite.
4. **Reserve durably.** Check per-call input/output, their sum against context,
   total input/output and call caps. Append/fsync the admission, including the
   complete-request hash, before returning a candidate completion request.
   This is an offline contract admission, not an experiment/model admission.
5. **Future broker submission (not implemented).** The broker would submit the
   exact prepared body once, with no hidden retry, fallback or rewriting.
6. **Validate receipt bytes.** Match call/request/payload hashes, original
   response model, provider/deployment/runtime, submitted output cap and exactly
   one attempt. Validate nonnegative integer input/output/total usage, sum and
   optional cached/reasoning components. Boolean "counts" are invalid.
7. **Settle once.** Account for known usage even when content is a refusal,
   truncated, empty, malformed or oversize. Invalid/ambiguous receipts preserve
   the full reservation as a conservative charge and mark provider usage unknown.
   Mismatched token counts/caps retain at least the reservation or larger observed
   use and halt. No timeout, malformed output or accounting failure triggers a
   replacement call or removes an admitted attempt from the ledger.

`max_completion_tokens` is the selected Chat Completions wire field, and counts
visible **and reasoning** output. Provider `prompt_tokens`, `completion_tokens`
and `total_tokens` are checked; cached prompt tokens still count toward context
and input budgets. This is a token budget, not a monetary-cost estimator. See
the [official Chat Completions API reference](https://developers.openai.com/api/reference/resources/chat/subresources/completions/methods/create)
and [usage/response types](https://developers.openai.com/api/reference/resources/chat).
OpenAI's documented semantics do not prove that a third-party compatible
endpoint implements them. Do not substitute visible text length for usage.

The append-only ledger holds an exclusive process lock and validates its history
on reopening. An interrupted/pending reservation stays charged and terminal;
missing completion is not zero usage. Malformed/truncated records fail closed.
Checksums detect accidental corruption, not malicious rewriting by the file
owner. A future dispatcher must use the same admission-before-send ordering,
retain all admitted attempts in experiment ITT, and reconcile uncertain upstream
outcomes separately; killing a client does not prove upstream cancellation.

## Offline acceptance and remaining live blockers

```sh
python -m unittest discover -s tests -p 'test_m10_successor_adapter_contract.py' -v
python -m unittest discover -s tests -p 'test_m10_successor_token_budget.py' -v
```

These run without credentials, sockets or provider access. Existing full
successor regression discovery also includes them. Positive results may be
reported only as `offline_adapter_contract_conformance`; preserve
`model_execution_enabled=false`, `model_pilot_admitted=false` and
`provider_token_limits_verified=false`.

Before a live protocol pilot, still required:

1. A separately deployed broker implementing this contract, with tested actual
   identity, cap forwarding, usage, exact input counting, deadlines and absence
   of hidden retries/fallbacks; if exact counts or immutable identity cannot be
   obtained, reject admission rather than inventing them.
2. Verified runtime/isolation boundaries, plus a complete experiment-and-adapter
   seal consumed by the eventual live runner; neither a standalone codec nor a
   matching self-report supplies these guarantees.
3. Explicit authorization for real conformance calls and the protocol-only
   pilot. Keep exploratory results out of confirmatory arm-effect claims.

Passing these offline tests does not remove any of those live blockers.

The separate [process rehearsal](guava-m10-successor-process-rehearsal.md) now
tests this codec and ledger across actual child-process I/O with a fixed,
fictional peer. It does not connect this codec to a live provider or relax the
experiment runner's execution gate.
