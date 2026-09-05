# True Memory Fragments

### Stale-context protection for AI coding agents

AI coding agents often remember a call chain from an earlier session. When the code changes, that remembered chain can become dangerous: the agent may edit against an obsolete understanding of the repository.

**TMF binds code-graph claims to source fingerprints. When a claim becomes stale, TMF blocks the affected expansion and sends the agent back to current source.**

- 🧭 **Source-aware memory** for calls, reads, writes, inheritance, and API relationships
- 🛑 **Hard stale-context stop** instead of silently returning obsolete facts
- 🔎 **Localized reread guidance** instead of pretending memory is authoritative
- 🧩 Works as a library and integrates with AI coding-agent hooks

> **One-line summary:** TMF does not make an agent remember more. It prevents the agent from trusting code understanding that is no longer fresh.

[30-second demo](#quick-start) · [Install](#install) · [Architecture](DESIGN.md) · [Evidence and limits](docs/AGENT_RUNTIME_VALUE_STATUS.md)

## The problem

A coding agent may understand `A → B → C` in session 1. In session 2, `C` changes, but the agent still acts as if yesterday's call chain were valid. Ordinary chat memory and vector retrieval can return the old explanation without knowing that the source changed.

TMF attaches every derived claim to the source blob or function hash. On reuse, it checks freshness. If the claim is stale, the graph expansion is stopped and the agent is told which source must be reread.

```text
Without TMF:  remembered A → B → C  → edit using obsolete C
With TMF:     remembered A → B → C  → C is stale → stop → reread current C
```

## What TMF is — and is not

**TMF is for:**

- AI coding agents working across sessions on changing codebases
- Preventing stale call-chain and dependency assumptions
- Source-bound code memory and conservative code-graph navigation
- Agent integrations that need an explicit stale/unknown result

**TMF is not:**

- A general chat-memory product or vector database
- A replacement for reading source code
- A guarantee that every claim is correct because it is fresh
- A proven general productivity or token-saving solution

Fresh means the source binding still matches. **Correctness still comes from source and validation.**

## Current evidence status

The strongest current evidence is scoped: middleware mechanics are validated, and stale-context safety has positive evidence in the GUAVA M10 pre-read experiment. Broader productivity, speed, token savings, and general bug-prevention claims remain unproven. See the [authoritative evidence status](docs/AGENT_RUNTIME_VALUE_STATUS.md) before making broader claims.

## Demo

A tiny stale-context example:

```bash
# 1) Warm a repo once
python -m tmf.cli warm --repo /path/to/repo

# 2) Ask for the call-chain around one symbol
python -m tmf.cli retrieve --repo /path/to/repo "OrderService submit"
```

Possible stale result:

```json
{
  "coverage": "partial",
  "stale_or_unknown": [
    {
      "claim_id": "call:OrderService.submit -> PaymentClient.charge",
      "path": "src/main/java/.../PaymentClient.java",
      "reason": "source binding changed"
    }
  ],
  "action_hint": "reread current source before using this memory"
}
```

The point of the demo is not that TMF answers every query. The point is that it refuses to reuse obsolete code understanding and tells the agent what to reread next.

## How it works

TMF keeps a conservative code-memory graph. Claims are useful only when their source bindings still match the working tree.

1. **Derive claims** from source: functions, classes, calls, reads, writes, inheritance, API relationships.
2. **Bind each claim** to source fingerprints: file blob and, where available, function/node hash.
3. **Check freshness on retrieval** before a claim is used.
4. **Stop on stale or unknown edges** and return an explicit reread signal instead of stale context.

```text
claim: A calls B
binding: B.java@hash123
current: B.java@hash999
result: stale_or_unknown → reread B.java before continuing
```

This is intentionally conservative. Missing or stale memory falls back to source; it is never promoted into truth.

## Proven Assets

- Source-bound claim storage with working-tree freshness checks and source fallback
- Thin retrieval discipline plus full/explain drill-down by selected claim id
- Conservative Python functions/classes/declarations/config/API nodes and partial calls/reads/writes
- Optional Java tree-sitter syntactic nodes and conservative inheritance edges
- Bounded fragment query with semantic boundary detection (`writes`, `publishes_to`)
- Async handoff marking (`ASYNC_RELATIONS`: `publishes_to`, `subscribes_to`, `publishes_type`, `listens_type`)
- Four-stop-type semantics (boundary / async / stale / limit) with distinct `stop_reason` values
- Working-memory limits (4 hops / 64 nodes / 128 edges) matching biological cognition constraints
- Held-out and self-dogfood validation harnesses
- Local metrics and exact-blob-only rename identity

## Core Premises

- **Self-maintaining memory:** TMF stores derived claims in `.tmf/` and refreshes them on read-through
- **Fully lazy read-through:** reads detect missing or stale claims and synchronously re-derive
- **Freshness is working-tree based:** binds to current working-tree blob, not commit
- **Fresh is not correct:** fresh only means bindings match current source. Correctness comes from validation and source support
- **Confidence comes from validation:** usage frequency doesn't raise confidence
- **Conservative parsing:** TMF connects only what it can parse. Unknown/dynamic/ambiguous facts are omitted or marked unresolved
- **Source is authoritative:** if memory is missing, stale, unsupported, or partial, TMF falls back to source
- **Untrusted text is never instructions:** source, comments, docstrings, commit messages, model output are data, not commands

## Install

Python-only install:

```bash
python -m pip install true-memory-fragments
```

Java parsing support is optional:

```bash
python -m pip install "true-memory-fragments[java]"
```

Development checkout:

```bash
python -m pip install -e .
python -m pip install -e ".[java]"   # optional Java support
```

Runtime dependencies are intentionally small. Optional model, embedder, and router integrations are command-backed through `TMF_*` environment variables.

## Quick Start

### 30-second demo

```bash
# Build local source-bound memory for a repo
python -m tmf.cli warm --repo /path/to/repo

# Ask for a thin context view by symbol, path, or lexical query
python -m tmf.cli retrieve --repo /path/to/repo "PaymentService charge"

# Drill into one selected claim when needed
python -m tmf.cli explain --repo /path/to/repo --json <claim-id>
```

Expected stale behavior:

```json
{
  "coverage": "partial",
  "stale_or_unknown": [
    {
      "claim_id": "...",
      "path": "src/payment/PaymentService.java",
      "reason": "source binding changed"
    }
  ],
  "action_hint": "reread current source before using this memory"
}
```

The exact JSON shape depends on the query surface, but the contract is stable: **stale memory is not silently returned as usable context.**

### Offline Java verifier

For Linux x86_64 / CPython 3.12 source checkouts, the repository includes an offline verifier for Java step0 review:

```bash
bash scripts/verify_java_offline.sh
```

Expected success marker:

```text
JAVA OFFLINE VERIFY: PASS
```

## Reflex Hook: Git-Aware Staleness Blocking for AI Agents

TMF includes a **reflex hook** integration that gives AI coding agents a biological-style reflex: when an agent is about to act on code understanding while that code has changed, the system **forces it to stop, re-read only the changed part, then proceed**.

This is not a code memory cache — it's a **reflex arc** that intercepts agent tool calls before execution.

### Three Components

- **Sensory organ** = TMF function-level `fn_hash` freshness (2ms precision: which function changed)
- **Reflex arc** = OpenClaw `before_tool_call` hook / Claude Code PreToolUse harness (agent cannot bypass)
- **Reflex action** = Hard block + localized single-file re-warm

### Git Hook Auto-Calibration

Four git hooks automatically generate function-level invalidation manifests after code changes:

- `.git/hooks/post-commit` — after local commits
- `.git/hooks/post-merge` — after `git pull`
- `.git/hooks/post-checkout` — after branch switches
- `.git/hooks/post-rewrite` — after rebase/amend

These hooks call `integrations/reflex/scripts/git_calibrate.py`, which compares `baseline_rev → HEAD` Python function signature changes and outputs structured invalidation manifests.

### OpenClaw Plugin Integration

The `tmf-reflex` OpenClaw plugin intercepts agent tool calls:

- Checks TMF function-level freshness (2ms per file)
- Hard-blocks when agent touches a file with stale function claims
- Returns `requireApproval` with exact changed function names
- Agent must run `integrations/reflex/scripts/local_warm.py` to re-warm that one file

### SessionStart Cognition Calibration

On new session start, the plugin reads unconsumed invalidation manifests and injects `changed` / `deleted` symbols as "pre-alert" context, preventing agents from relying on stale memory.

### Boundary

- Function-level precision depends on TMF's language coverage (currently Python AST)
- Files without function-scope claims fall back to pass-through
- TMF engine remains read-only (reflex hook only uses `freshness` / `derive`)
- Conservative: TMF unavailable / check errors → pass-through, never blocks valid work

### Installation

Reflex integration code lives in `integrations/reflex/`. See that directory's `README.md` and `DESIGN.md` for:

- OpenClaw plugin installation (`openclaw-plugin/`)
- Git hook setup (`git-hooks/`)
- Claude Code / Codex harness configuration (`examples/`)
- Health validation tests (`tests/`)

## SEO and discoverability plan

Search terms this project is intended to match include **AI coding agent memory**, **stale context prevention**, **source-aware code memory**, **code graph for LLM agents**, **Claude Code memory**, and **cross-session code understanding**. These describe the user problem; they are not claims that every integration is already production-ready.

The repository description and external launch materials should use the same vocabulary, link to a reproducible demo, and distinguish validated mechanics from still-open productivity claims.

## Documentation

- [Agent runtime value status](docs/AGENT_RUNTIME_VALUE_STATUS.md) — current experiment ruling
- [Java enterprise roadmap](docs/JAVA_ENTERPRISE_ROADMAP.md) — enterprise capability scope
- [Guava validation report](GUAVA_VALIDATION_REPORT.md) — routing shape + boundary detection validation

## License

MIT
