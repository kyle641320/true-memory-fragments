# agent_middleware_value_v1 — frozen preregistration

Pre-registered before model execution on 2026-08-13. This is a real stateless coding-Agent paired comparison, not a supplied-evidence answer benchmark. `SOURCE_ONLY` and `TMF_MIDDLEWARE` use the same `gpt-5.6-sol`, raw-inference broker, prompts, task order, tools, source fixtures and budgets. The runner owns a constrained read/search/edit/test loop. The broker has no tools or repository access. Each arm starts from a fresh isolated fixture copy.

Each sequence has a common first visit that reads the real base source and derives a source-bound claim. That answer/transcript is discarded. Revisit agents are independent/stateless. SOURCE_ONLY receives no memory. TMF uses the unmodified middleware at base commit `45ab3e4`; immediately before the router-selected read, it injects a fresh allowlisted anchor or blocks final/edit on stale until the affected source region is reread. Unknown/unrelated controls must not false-inject. Semantic scenarios mutate source after familiarization.

Tasks are real understanding, local edit, cross-file trace, and test-fix tasks, at least two each, covering Python and Java. Understanding uses structured answer/citations; modifications use tests plus diff assertions. The Agent may autonomously read/search/edit/test through the controlled tool schema. No prebuilt source bundle is sent to the model.

Primary: task success/tests and citations. Secondary: machine-audited claim adoption, duplicate source reads, prompt/completion/injection token estimates, source files/lines/bytes, tool calls/tests and wall time. Adoption requires a correct final/patch dependency on an injected claim anchor without rereading that source; self-report never counts.

Attribution classes are `memory-caused`, `stale-memory-caused`, `post-reread-agent-failure`, `baseline-agent-failure`, `output-contract`, and `tool/runtime`; mechanism errors are reported separately. Infrastructure/schema failures are invalid and never used to tune prompt, golden, scorer, middleware, retrieval, packing, parser, or freshness. One symmetric schema repair is permitted and charged.

Smoke runs A01/A03. Full run proceeds only if both smoke pairs are valid and TMF demonstrates at least one machine-audited adoption without a success regression. Stop gates and value gates are frozen separately. Small N is descriptive only: report every paired row and do not claim significance.
