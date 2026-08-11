# Java Real-Agent A/B v2 Protocol (FROZEN)

Frozen 2026-08-11 before agent execution. This is an expansion only: v1 P01-P04 artifacts/results are immutable and excluded. No TMF engine, parser, extractor, retrieval, or global MCP configuration changes are permitted.

## Corpus and isolation

Petclinic is pinned to `58c3310e36c7d827959df6af4d64bdeb8d81f1ea`; JHipster is pinned to `f8da577c944ecc4db46fc961a1ba022d5bbf8964`. Each repository has its own repository-local `.tmf` store. `repo_tmf_locator.py` verifies the manifest commit before creating `McpService(repo)`, bypassing the globally registered Zhihu locator. The three-query alternating-repository pollution gate must pass before runs. Golden files are held outside prompts and loaded only by evaluation.

## Tasks and pairing

Seven ordinary tasks were manually selected from source: Petclinic location, impact, and local-change; JHipster location, two impacts, and local-change. Two independently mutated freshness pairs cover method rebind (JHipster helper rename) and event type change (Petclinic event rename across producer/consumer). Natural prompts contain neither golden paths nor golden symbols. Every task is paired SOURCE_ONLY/TMF_MAP with the same model, tool/source budget, task text, and fixed randomized order. SOURCE_ONLY is explicitly forbidden from TMF. TMF_MAP must begin with the repo-pinned locator and treat it only as a locator.

Freshness arms receive the identical old claim. Their source copies are warmed before mutation. TMF_MAP must call `check_freshness` against that old store before local source reread; SOURCE_ONLY compares the old claim with current source. A valid freshness answer must block stale memory and cite the minimal current neighborhood.

## Execution and metrics

Runner: native `openclaw agent`, unique isolated session id per arm, model `aisz/gpt-5.6-sol`, thinking off, 240-second model timeout, max 14 tool calls, 8 files, and 900 source lines. The SHA256-randomized order is in `manifest.json`; arms are adjacent and fixed to avoid post-result selection. Raw CLI JSON, stderr, prompt hash, exit code, and wall time are retained. Transport/service failures are renamed `*.invalid.*`, excluded, and retried in a new isolated session.

Metrics: correctness, citation correctness, source files/lines, tool calls, wall time, stale trust/block, and local reread lines. Evaluation requires held-out required citation neighborhoods and fact-key evidence. Missing self-reported operational metrics remain null, never imputed. This small sample is descriptive, not a causal claim.
