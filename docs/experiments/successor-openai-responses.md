# Independent successor: OpenAI Responses profile v1

This is a **new internally controlled experiment**, inspired by the M10
observation, not a replication of its provider protocol or numerical results.
Internal validity takes precedence over historical comparability. Null results
and falsification are admissible. Nothing here changes the production TMF
engine, historical M10 data, conclusions, or existing offline broker contract.

## Authorization and scope

The 2026-09-23 authorization `tmf-successor-responses-conformance-20260923-01`
permits implementation, offline testing, a new seal, independent audit and an
isolated PR. **Only after all gates pass**, at most three real generations and
twelve count requests may be dispatched. No repeated authorization is needed.
All six-arm live pilots, R5/R10/R50 and treatment-effect experiments remain
forbidden. There is no live pilot entry point. Existing scripted offline
rehearsals remain offline evidence, not model results.

Every request attempt consumes this authorization's durable lifetime allowance,
including uncertain timeouts. A repair requires tests, resealing and another
independent audit; it does **not** reset the allowance or permit an automatic
rerun. A failed attempt ends this invocation. A missing credential is not
permission to read another application's configuration or reuse its OAuth key.

## A. Provider-specific contract diff

The old Chat Completions/text-JSON contract remains unchanged. New modules
`successor_openai_responses`, `successor_openai_transport`,
`successor_openai_protocol`, and `successor_openai_conformance` own this profile.

| Previous contract | New profile |
|---|---|
| `/v1/chat/completions` | `https://api.openai.com/v1/responses` |
| text action in assistant content | exactly one native function request |
| `max_completion_tokens` | `max_output_tokens` |
| `finish_reason=length` | `status=incomplete`, `incomplete_details.reason=max_output_tokens` |
| mandatory internal deployment/tokenizer hashes | explicitly unavailable; no fabricated hashes |
| text-only replay | full scientific history plus all provider-required output/state items |
| fictional offline exact count | official `/v1/responses/input_tokens` |

The production T0 FRESH → frozen mutation → T1 STALE chain, sole intended stale
cause, fresh control, withholding receipt, semantic AST scorer and independent
compilation checks are reused as scientific materials. The old provider wire
representation and its historical-comparability claims are not inherited.

## B. Native request/response mapping

All six conditions use identical model, config, system/task/native-tool prompt,
seven local function schemas, runtime and limits. Only preregistered information
conditions differ. SOURCE_ONLY and silent withholding are byte-identical at
initial request. Warning-only changes only the intended status/locator fields
of the trusted stale payload. Arm identity, evaluator IDs, ordering, seals and
absolute host paths do not enter scientific requests.

The seven functions are `list`, `search`, `read_range`, `read_symbol`, `edit`,
`compile`, `final`. `strict=false` preserves the genuinely optional `search.path`
field; the local validator still rejects extra keys, incorrect argument types,
bad paths, invalid actions, duplicates and malformed JSON. Provider-native
strict mode is not claimed. `parallel_tool_calls=false`, `tool_choice=required`.
No provider-hosted tools are registered. Multiple calls, refusal or unsupported
output items fail closed rather than selecting a convenient action.

Provider calls are proposed actions, not executed tools. Local mediation
revalidates the original observation, executes only the allowed action, then
appends one function result referencing the exact call ID. Source copies are
isolated, only Dispatcher.java is editable, and final files/current compilation
are checked. Compilation and AST semantic scoring are separate outcomes;
failed trajectories remain in the protocol ledger. This release tests that
mediation offline; it does not authorize a live scientific runner.

## C. Exact counting and request identity

One canonical preparation creates count and generation byte strings together.
The official count-compatible projection contains model, complete input,
native tools, tool choice, parallel setting, reasoning, text and truncation.
Generation-only fields are explicitly enumerated by the codec, not freely
discarded. Scientific fields cannot be modified after counting. Independent
verification reconstructs the projection and digests before every operation.

The client calls the official count endpoint. The broker independently recounts
the exact same bytes before reserving a generation. Counts must agree. No local
tokenizer, character heuristic, fixture count or document hash is presented as
real exact provider counting. Later generation `usage.input_tokens` must equal
the admitted count. A provider discrepancy halts after preserving evidence and
known usage; it is not patched to the expected number.

Hashes bind **local bytes**, not OpenAI's invisible tokenizer or deployment.

## D. Stateless history and C1 → C2

`store=false`; no previous_response_id, conversations, compaction or hidden
provider-side history. `truncation=disabled` fails on excessive context instead
of deleting earlier history. Scientific history (instructions/evidence/actions/
local feedback), provider state (reasoning items/encrypted_content and response
item IDs/phase), and transport metadata (request IDs/timing/headers) are recorded
separately. Transport metadata never becomes an extra scientific prompt.

Include encrypted reasoning content and preserve **every** returned supported
output item, in order and unchanged, when constructing subsequent input. Do not
retain only text, discard reasoning, synthesize successful output or select one
convenient function. The response parser and continuation both validate this.

Before C1, seal deterministic function F:

```
C2.input = C1.input + C1.output (all items, unchanged)
           + function_call_output(C1.call_id, frozen_local_result)
```

F requires a valid single non-final C1 function request and at least one nonempty
encrypted reasoning item. Otherwise this conformance ends as evidence
insufficient, without replacement C1 or fabricated state. The local result is
a fixed JSON **error receipt**, explicitly saying no repository tool ran, with
Unicode, quotes, slash and newline probes. This is a conformance stub, not a
claim that source was read. It tests state continuation independently of model
action choice. Local tool execution and compile/final behavior are separately
tested through offline mediation. C2 may propose any one valid function,
including final; no live experiment action is executed.

## E. Fixed model and reasoning

Chosen primary: **gpt-6-astra / medium**. It supports the Responses native
function interface and provides a capable current-model test without selecting
for agreement with old M10. Medium is a frozen capability/cost compromise, not
a setting tuned on outcomes. Sol is not prioritized by its historical label.
Old M10 effective effort remains unknown and is irrelevant to this new
profile's internal control. No arm or result changes effort.

Also fixed: reasoning context `all_turns`, reasoning mode `standard`, text
format `text` and verbosity `medium`, service tier `default`, nonstreaming,
foreground, no background processing. The raw returned model must satisfy the
frozen exact identity rule, not an arbitrary prefix match or fallback alias.

## F. Raw usage and accounting

Save original request/response bytes and safe transport metadata before semantic
validation, including rejected identities. Preserve input_tokens,
input_tokens_details.cached_tokens, cache_write_tokens when returned,
output_tokens, output_tokens_details.reasoning_tokens, total_tokens and raw
unknown fields. Validate types, ranges and total=input+output. Reasoning is
already part of output; **never add it twice**. Known coherent aggregate usage
is retained even when model identity or action validity fails.

Token accounting and monetary completeness are separate. Frozen Astra/default
rates may price an observation only when its returned model, service tier,
processing mode, short-context bound and usage semantics establish that price
basis. Wrong/unknown identities or semantics retain known token aggregates but
mark monetary completeness false. A counterfactual frozen-rate valuation is
explicitly labeled as such, never reported as established cost or an invoice.

Absence of cache-write data is recorded as unknown, never fabricated as zero.
If price accounting cannot be established under this profile, halt. Missing or
contradictory aggregate usage has no invented settlement: preserve raw evidence
and charge the full reserved exposure conservatively. Input/output observations
and conservative exposure are distinct. Requests with unknown transport outcome
remain charged and cannot be replayed.

## G. Retry, fallback, timeouts and caching

One durable scientific generation admission permits **one POST** only. No SDK,
automatic retry, redirect, model fallback, truncation, effort/cap adjustment or
retry-until-cap behavior. A bounded stdlib transport accepts an injected
credential callback only on the authorized live path; mock paths never read
credentials. HTTP error bodies are retained as evidence but are not echoed as
untrusted exception strings. Hard deadlines do not prove upstream cancellation.
Each attempted operation has a durable pre-dispatch timestamp, endpoint,
request digest and reservation; a received response adds provider identity,
raw usage, request ID and receipt timestamp. A completion's independent recount
and generation share one 90-second deadline; the preceding client count has
its own 90-second deadline. No timeout extends or resets itself.

Caching is a runtime observation, not treatment. Every arm uses identical
implicit mode, `prewarm=false`, TTL30m, and omits prompt_cache_key. No arm labels
in cache controls, no reordered schedule to obtain discounts, no manual cache
breakpoints. Cache behavior/latency may still vary naturally and is logged.
The official response schema reports applied `mode` and `ttl`, optionally a
null `comparison_response_id`; it does not echo request-only `prewarm`. Validate
these schemas asymmetrically. Non-null comparison IDs or unknown response cache
fields fail closed; no absent request-only field is invented in raw evidence.

## H. Seal and admission

The new seal binds the reconstructed production material seal, all six exact
initial native requests, C3 request, F and fixed local result, seven schemas,
profile and limits, authorization ID, price assumptions, common native prompt,
implementation and test files, protocol document, Python/parser/compiler
inventory and HTTP runtime identity. The official-document provenance
manifest binds retrieval URLs/times and content hashes, not provider internals.
Verification reacquires production
freshness and rebuilds expected content; rehashing altered PASS flags is not
sufficient. Local hashes do not attest provider internals.

Live admission requires current offline tests and an independent READY audit
receipt bound to this exact seal. Such a receipt is a reviewer attestation,
not a cryptographic proof of review. Authorization budget state has a fixed
lifetime path and cannot be reset by selecting a different output directory.
Pending/ambiguous operations prevent restart/resume. Six-arm live execution
remains disabled even after conformance success.

The live entry point also creates an exclusive lifetime admission latch under
the host user's `.local/state/tmf-successor/authorizations/` directory. It accepts
no alternate journal/output directory. A host-supplied protected credential
callback is consulted only after admission; the experiment module itself does
not read environment/config credentials. Ordinary preparation/verification CLI
commands expose no live flag. Fake tests replace the transport, not the guards.
The latch file, its containing directory and every ancestor directory entry are
fsynced before constructing the transport. The raw-evidence directory and its
ancestor chain are also fsynced before any POST. Any failure stops dispatch.
Fault-injection tests establish ordering/failure behavior, not a physical
power-loss simulation or a guarantee beyond the host filesystem's fsync contract.

Generic unit-test jobs without the frozen offline Guava JARs explicitly skip
the two production-seal tests and real-javac mediation test, following the
existing repository integration-test boundary. The dedicated successor job
fetches these dependencies before testing and has a mandatory non-skippable
full production seal/reconstruction command. Missing dependencies cannot make
that acceptance path green.

## I–J. Ordered conformance and maximum tokens

1. Count the six sealed initial requests (no six-arm generation).
2. C1: count, independent broker recount, one SOURCE_ONLY generation, cap4096.
3. C2: mechanically apply F; count, recount, one generation, cap4096.
4. C3 **last**: count, recount, one no-tools output-cap probe, cap64.

Hard limits: **12 count attempts, 3 generation attempts, 10000 input tokens per
generation, 30000 input in total, 8256 generated tokens in total = 38256 maximum
generation tokens**. Every output token category counts toward the cap,
including reasoning/tool/formatting. C3 succeeds only on documented
`incomplete/max_output_tokens`; otherwise record evidence insufficient, no retry.
Stop at the first failing stage, record skipped stages, preserve usage and raw
evidence. No inference about treatment effects follows from C1/C2/C3.

## K. Price basis and monetary uncertainty

Official prices checked 2026-09-23, standard nonregional short-context Astra:
input$10/M, cached$1/M, cache-write$12.50/M, output$50/M. No cache discount is
assumed. All input charged at the higher cache-write rate gives generation
maximum **$0.7878** (30000×12.5/M +8256×50/M), not expected spend.
This is a planned maximum conditional on the frozen provider contract being
honored, not an established maximum bill for an unobserved or wrong-model/tier
response. Such violations halt and keep monetary uncertainty explicit.

**Count pricing unknown. Therefore an all-in USD maximum is unknown**, despite
the hard twelve-request cap. This accepted uncertainty is not called free.
Long-context, service-tier, regional, caching or future pricing changes must not
silently change the frozen profile. A prospective six-run/24-turn pilot would
permit 144 generations, at most1440000 input and589824 output tokens, generation
maximum$47.4912 with this conservative rate; **it is not authorized** and its
count-call budget/runner must be separately frozen. No pilot is auto-started.

## L. Provider observability and residual limits

- Immutable deployment revision: **unavailable**.
- Tokenizer material/revision: **unavailable**.
- Request model and raw response model are observable provider claims, not
  independently verified server weights.
- Local request hashes establish submitted bytes; exact count is the official
  endpoint's assertion, not tokenizer source attestation.
- Encrypted state is opaque; its exact preservation is verifiable, its private
  semantics are not.
- Transport timeout does not prove nonexecution or cancellation at OpenAI.
- Implicit caching is neither fully controlled nor presumed discounted.
- Conformance is a bounded sample, not proof of every future provider behavior.
- Capability/medium choice is frozen before outcomes, not evidence TMF works.
- Matching source-only is a permissible scientific result; freshness does not
  imply semantic correctness, completeness or safety.

## Official authority (not local compatibility guesses)

- [Responses API](https://developers.openai.com/api/reference/resources/responses/methods/create)
- [Count input tokens](https://developers.openai.com/api/reference/resources/responses/subresources/input_tokens/methods/count)
- [Token counting guide](https://developers.openai.com/api/docs/guides/token-counting)
- [Reasoning / stateless continuation](https://developers.openai.com/api/docs/guides/reasoning)
- [Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [GPT-6 Astra](https://developers.openai.com/api/docs/models/gpt-6-astra)
- [Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)
- [Pricing](https://developers.openai.com/api/docs/pricing)

Readiness and actual execution results belong in dated external evidence
artifacts, not retroactively edited scientific claims. No READY verdict is
implied by this document alone.
