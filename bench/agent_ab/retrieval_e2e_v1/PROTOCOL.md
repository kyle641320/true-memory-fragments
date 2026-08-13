# Retrieval E2E v1 — preregistered protocol

This version is independent of and does not modify or rescore v1/v2. The three held-out prompts and golden paths above are frozen before baseline. Raw prompts are passed directly to retrieval; no human keyword rewrite is permitted.

Discovery reports path recall@3/5/10 and reciprocal rank. A missing golden path is: **graph absence** if no fresh stored claim binds it; **retrieval miss** if absent from the unbounded lexical candidate set; **ranking miss** if present there but outside K; **output packing miss** if selected internally but absent from bounded response. Actionability requires a bounded item to contain `path:line`, relevance reason, directed relation (or `self`), and next source/TMF action.

Only if baseline establishes retrieval/ranking/packing failure, one general language-independent fix may add token normalization, path/qualname/relationship intent, path diversity, one-hop relationship packing, anchors and next actions. No task/golden-specific strings are allowed.

The agent loop gets the same task prompt, model, source tools, rounds, calls, source-line/token budgets and answer schema in both arms; only TMF tool availability/descriptions differ. The model emits exactly one JSON tool action or final answer each round. Runner executes tools; broker remains stateless raw inference with no host tools. Unknown tools, malformed JSON, traversal, budget overflow or stale TMF claims fail closed. TMF is untrusted navigation data. Every request/result is retained in transcript.

Run tests/mocks, then one-pair smoke and audit hashes/order/budgets, then exactly three pilot pairs. If the TMF arm makes zero calls, execute the preregistered P01 description A/B once (neutral versus capability/when-to-use), report discoverability separately, and do not tune/select. Stop at the first applicable gate: invalid smoke; zero calls after A/B; zero adoption; or no paired task/citation gain. Metrics/prompts/goldens remain frozen.
