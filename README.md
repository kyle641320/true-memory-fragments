# True Memory Fragments

> **Agent evidence status:** See the single authoritative [Agent runtime value status](docs/AGENT_RUNTIME_VALUE_STATUS.md). Current ruling: middleware mechanics qualify, but Agent outcome value remains unproven. Cognitive-continuity v1 is **INVALID_PROTOCOL**; v2 stopped at smoke (0/2 adoption). V3 (guava_cognitive_v1) **INVALID_PROTOCOL** — task design did not test core hypothesis. Read the authority page before mixing modes. (TMF)

True Memory Fragments is a **cross-session call-chain continuity system** for AI coding agents. It solves the "tunnel vision bug" problem:

**The problem:** Agent understands a complete call chain `A → B → C → D` in session t₀. Code changes at t₁ (e.g., `C` logic modified). Agent receives task "modify A" at t₂. If the agent only looks at `A`, it may introduce bugs because it doesn't see the downstream impact on the changed `C`.

**TMF's solution:**
1. **Precise staleness detection:** When the agent retrieves the `A → B → C → D` chain from memory, TMF detects that `C` has changed and blocks stale memory
2. **Localized reread:** Forces the agent to reread only `C` and its direct neighbors, not the entire codebase
3. **Complete chain understanding:** Ensures the agent sees the full call chain when making changes, avoiding "tunnel vision" bugs

TMF is **not** a tool to help agents understand code faster on first read. It is a memory invalidation + call-chain tracking system for agents working on the same codebase across multiple sessions.

## Core value proposition (corrected 2026-08-20)

**What TMF is for:**
- Preventing bugs caused by incomplete call-chain understanding
- Cross-session cognitive continuity through precise staleness detection
- Efficient localized rereads (only changed nodes, not entire codebase)

**What TMF is NOT for:**
- ❌ Helping agents understand code on first encounter
- ❌ Reducing source rereads through cached "facts"
- ❌ Providing "remembered truths" for direct reuse

**Current status:** Mechanics proven (freshness detection, stale blocking work). Value hypothesis **untested** — no valid experiment has measured cross-session call-chain continuity or bug prevention.

## Proven assets so far

- Source-bound claim storage with working-tree freshness checks and source fallback.
- Thin retrieval discipline plus full/explain drill-down by selected claim id.
- Conservative Python functions/classes/declarations/config/API nodes and partial calls/reads/writes.
- Optional Java tree-sitter syntactic nodes and conservative inheritance edges, with offline verifier wheels vendored under `vendor/wheels`.
- Java enterprise capability scope and release gates are tracked in `docs/JAVA_ENTERPRISE_ROADMAP.md`.
- The cumulative Java extractor has an AST structural guard against shadowed duplicate top-level definitions; the remaining single-module registry is still large and should be consolidated before broad adapter expansion.
- Bounded Resilience4j `@CircuitBreaker` declaration metadata is documented in `docs/JAVA_CIRCUIT_BREAKER_COMPATIBILITY.md`; runtime resilience behavior is not inferred.
- Mechanical contract facts with low confidence caps; semantic/model output remains attributed/inferred and sanitizer-clamped.
- Held-out and self-dogfood validation harnesses that report precision/recall instead of asserting correctness.
- Local metrics and exact-blob-only rename identity migration from completion window 1.
- Generic method overload resolution enhanced to handle JDK built-in types (2026-08-19).

## Core premises

- **Self-maintaining memory:** TMF stores derived claims in the repository-local `.tmf/` directory and refreshes them on read-through.
- **Fully lazy read-through:** reads detect missing or stale claims and synchronously re-derive; writes and commits do not run hooks or background work.
- **Freshness is working-tree based:** freshness binds to the current working-tree blob plus node-specific hashes, not to `HEAD` or commit identity.
- **Fresh is not correct:** a fresh claim only means its bindings still match the current source. Correctness is established by validation and source support.
- **Confidence comes from validation, not frequency:** usage/read frequency does not raise confidence. Model self-report is clamped by verification.
- **Conservative parsing:** TMF connects only what it can parse and support. Unknown, dynamic, shadowed, or ambiguous facts are omitted or marked unresolved rather than guessed.
- **Source is authoritative:** if memory is missing, stale, unsupported, or partial, TMF falls back to source.
- **Untrusted text is never instructions:** source, comments, docstrings, commit messages, model output, and future PR text are data, not commands for the agent.

## Install

From PyPI:

```bash
python -m pip install true-memory-fragments
```

For development from a source checkout:

```bash
python -m pip install -e .
```

Runtime dependencies are intentionally empty: `dependencies = []`. Optional model, embedder, and router integrations are command-backed through `TMF_*` environment variables and are not package dependencies.

Java step0 nodes are optional and dependency-isolated. Enable them with the standard extra:

```bash
python -m pip install "true-memory-fragments[java]"
```

From a source checkout, use `python -m pip install -e ".[java]"`. This installs the pinned/known-good grammar bindings `tree_sitter==0.25.2` and `tree_sitter_java==0.23.5`.

If those packages are absent, `.java` reads still return a file/source fallback claim plus a degrade hint; Python behavior remains unchanged.

### Offline Java verifier (Linux x86_64 / CPython 3.12)

This package vendors prebuilt MIT-licensed wheels for offline Java step0 review on Linux x86_64, CPython 3.12, glibc 2.39 / Ubuntu 24.04 compatible systems:

- `vendor/wheels/tree_sitter-0.25.2-cp312-cp312-manylinux2014_x86_64...whl`
- `vendor/wheels/tree_sitter_java-0.23.5-cp39-abi3-...manylinux2014_x86_64.whl`
- MIT license texts are copied into `vendor/licenses/`.

Because Ubuntu 24.04 uses PEP 668 externally-managed system Python, the offline verifier never installs into system Python. It creates a repository-local venv and installs only from `vendor/wheels` with `--no-index`:

```bash
bash scripts/verify_java_offline.sh
```

Expected success marker:

```text
JAVA OFFLINE VERIFY: PASS
```

The script verifies that Java tests run without skips, then warms a minimal Java fixture and checks both freshness directions: comment/trivia and formatting edits stay fresh; method body/literal and annotation edits stale; deleted Java nodes reconcile away. The network install command above remains the fallback for online environments.

## Quick start

Run the commands from the repository root after `pip install -e .`:

```bash
# 1. Warm a repository into .tmf/
tmf warm --repo .

# 2. Query: show me Python functions that call 'process_data'
tmf retrieve --query "functions that call process_data" --repo .

# 3. Inspect one claim by ID
tmf explain <claim-id> --repo .

# 4. Check status and freshness
tmf status --repo .
```

The `warm` step is fully lazy — it does nothing until a later `retrieve`, `explain`, or explicit `--refresh` forces derivation. After that, claims are cached until source changes make them stale.

## CLI

```bash
tmf {warm,retrieve,explain,status} [options]
```

### `warm`

Indexes a repository but does **not** derive or persist claims until needed.

```bash
tmf warm --repo /path/to/repo [--refresh]
```

- `--repo`: path to the repository root
- `--refresh`: force immediate derivation/write (optional; otherwise lazy)

### `retrieve`

Semantic search over TMF claims.

```bash
tmf retrieve --query "..." --repo . [--limit N] [--min-score S]
```

- `--query`: natural-language search query
- `--limit`: max results (default 10)
- `--min-score`: minimum similarity score (0.0–1.0)

### `explain`

Detailed view of one claim, including source anchors and derivation context.

```bash
tmf explain <claim-id> --repo .
```

### `status`

Shows claim counts, freshness summary, and cache health.

```bash
tmf status --repo .
```

## Python API

```python
from tmf import TMFRepository

repo = TMFRepository("/path/to/repo")

# Lazy warm (no work until needed)
repo.warm()

# Retrieve claims
results = repo.retrieve("functions that call process_data", limit=5)
for hit in results:
    print(hit.claim_id, hit.score, hit.summary)

# Explain one claim
claim = repo.explain(claim_id)
print(claim.content, claim.anchors, claim.freshness)

# Check status
status = repo.status()
print(status.total_claims, status.stale_count)
```

## MCP server (for OpenClaw/Claude Desktop/etc.)

Expose TMF through the Model Context Protocol:

```bash
# Start MCP server on stdio
tmf mcp --repo /path/to/repo

# Or configure in your MCP client (e.g., OpenClaw):
{
  "mcpServers": {
    "tmf": {
      "command": "tmf",
      "args": ["mcp", "--repo", "/path/to/repo"]
    }
  }
}
```

The MCP server provides `tmf_retrieve`, `tmf_explain`, `tmf_status` tools for LLM agents.

## Environment variables

Optional model/embedder/router configuration:

- `TMF_MODEL_COMMAND`: shell command for LLM inference (used by semantic/inferred claims)
- `TMF_EMBEDDER_COMMAND`: shell command for embedding generation (used by retrieval)
- `TMF_ROUTER_COMMAND`: optional routing/fallback coordinator

All three are optional. If unset, TMF operates in pure-syntactic mode (no semantic claims, no embedding retrieval).

## Testing

Run the test suite:

```bash
python -m pytest tests/
```

For Java tests (requires `tree_sitter` and `tree_sitter_java`):

```bash
python -m pip install -e ".[java]"
python -m pytest tests/test_java*.py
```

Offline Java validation (Linux x86_64 only):

```bash
bash scripts/verify_java_offline.sh
```

## Documentation

- [Agent runtime value status](docs/AGENT_RUNTIME_VALUE_STATUS.md) — authoritative experiment results
- [Java enterprise roadmap](docs/JAVA_ENTERPRISE_ROADMAP.md) — scope/completion gates for Java support
- [Circuit breaker compatibility](docs/JAVA_CIRCUIT_BREAKER_COMPATIBILITY.md) — Resilience4j annotation metadata
- [Field test plan](FIELD_TEST.md) — deferred reconnaissance protocol (plan-only)

## Experiments

All experiments live under `bench/agent_ab/`:

- `middleware_hardening_v1` — mechanism validation (5/5 gates pass)
- `agent_middleware_value_v1` — cold-start smoke (2/2 valid, 0/2 adoption, stopped)
- `cognitive_continuity_v1` — **INVALID_PROTOCOL** (fixture/task/golden contradiction)
- `cognitive_continuity_v2` — smoke completed (2/2 valid, 0/2 adoption, stopped)
- `guava_cognitive_v1` — **INVALID_PROTOCOL** (task design did not test call-chain hypothesis)
- `design_intent_v1` — **DESIGN PHASE** (call-chain continuity + bug prevention test)

See [AGENT_RUNTIME_VALUE_STATUS.md](docs/AGENT_RUNTIME_VALUE_STATUS.md) for full adjudication.

## License

MIT. See `LICENSE` for details.

## Contributing

Contributions welcome. Before submitting PRs:

1. Run `python -m pytest tests/` and ensure all tests pass
2. If adding Java features, run `bash scripts/verify_java_offline.sh` on Linux x86_64
3. Update relevant docs under `docs/`
4. Follow conservative parsing discipline: omit rather than guess

## Acknowledgments

Built with:
- `tree-sitter` and `tree-sitter-java` for Java parsing
- Standard library only for Python parsing (no dependencies)
- Optional model/embedder commands for semantic/retrieval features
