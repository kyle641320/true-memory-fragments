# True Memory Fragments

> **Agent evidence status:** See the single authoritative [Agent runtime value status](docs/AGENT_RUNTIME_VALUE_STATUS.md). Current ruling: middleware mechanics qualify, but Agent outcome value remains unproven. Read the authority page before mixing modes. (TMF)

## Bionic Design Philosophy

TMF is designed around how biological memory and cognition actually work. The core premise: **AI and biological thinking are both electrical signal processing** — the memory-cognition-update-pain loop that works for organisms can be directly applied to AI systems.

### 1. Progressive Cognition (渐进认知)

Organisms don't understand things all at once. First encounter creates a coarse impression — "this book is on that shelf" — not every word on every page. Later encounters refine that impression as needed.

**TMF correspondence:**
- Agent's first pass through a codebase generates relationship claims: `calls`, `reads`, `writes`, inheritance edges, type uses
- These claims form a **cognitive map**, not a content cache
- Later tasks query the map to locate what needs closer reading
- Progressive refinement happens on-demand, not upfront

### 2. Fresh/Stale Comparison (新旧比对)

Every time an organism uses a memory, it compares "current observation" with "remembered impression". Mismatch triggers re-encoding.

**TMF correspondence:**
- Every claim binds to source blob hash
- Before using a claim, TMF checks: does the hash still match?
- Mismatch → claim marked `stale`
- Agent must re-read source to update

### 3. Pain Reflex — Multi-Alert Forced Attention (痛觉机制)

When an organism acts on stale memory and makes a mistake, pain isn't a gentle suggestion — it's a **strong, repeated neural signal** that forces you to stop.

**TMF correspondence: `bounded_fragment` forced stop**

When querying call chains, if TMF encounters a stale claim:

- **Does not return partial results**
- **Does not silently warn**
- **Immediately stops expansion** and returns:
  - `stale_or_unknown` list (multiple entries for multiple stale claims)
  - `stop_reason` (explicit: `"entry_stale_or_unknown"`, `"edge_stale_or_unverified"`)
  - `coverage: "partial"`

Three separate alert fields, all present simultaneously — this is the **pain reflex**. Not a soft "FYI, might be stale", but a hard **"this chain is broken, you cannot proceed"**.

Agent must acknowledge and re-read before continuing. Source is authoritative.

### 4. Four Types of Stop (Not All Are "Pain")

`bounded_fragment` stops expansion for four distinct reasons, each with different cognitive meaning:

#### Stop Type 1: Boundary (Semantic End-of-Chain)

```python
if is_semantic_boundary(node):
    boundaries.append({...})  # Report reached
    # But do not add to next_frontier
```

**What it means:** Chain reached a recognized semantic boundary:
- `writes` edge → persistence layer (database write)
- `publishes_to` edge → message queue

**Not a failure.** TMF knows this is where the synchronous call chain ends. Reporting the boundary as "reached" is success — it's like tracking money transfer to "payment confirmed", you don't need to follow the bank's internal ledger.

**Boundary detection:**
- `semantic_boundaries=True` (default): uses indexed `writes` / `publishes_to` edges
- `semantic_boundaries=False`: uses scope-based `boundary_types` (legacy)
- Declaration annotations like `@Transactional` / `@Async` are not currently indexed as reverse edges; too expensive to scan all claims

#### Stop Type 2: Async Handoff

```python
is_async = kind in ASYNC_RELATIONS  # publishes_to, subscribes_to, ...
edges.append({..., "async_handoff": is_async})
if not is_async:
    next_frontier.append(node)  # Only sync edges continue
```

**What it means:** Edge is async message-passing, not synchronous call flow.

**Not a failure.** The edge is recorded, marked `async_handoff: true`, but doesn't contribute to synchronous frontier expansion. This prevents TMF from pretending a Kafka producer → consumer flow is the same as a direct function call.

#### Stop Type 3: Stale (Cognitive Failure — PAIN)

```python
if not freshness.fresh or _foreign(edge):
    stale_or_unknown.append({...})
    continue  # Do not add to nodes, do not add to edges
```

**This is the pain reflex.** Node/edge doesn't enter result at all — only goes into `stale_or_unknown`. If entry itself is stale, `bounded_fragment` early-returns with empty `verified_hops`.

**Agent receives:**
- `stale_or_unknown`: list of broken claims
- `stop_reason`: explicit stale reason
- `coverage: "partial"`

**Must re-read source.** No workaround, no "use what you have". Stale memory is rejected completely.

#### Stop Type 4: Resource Limit

```python
HARD_MAX_HOPS = 4
HARD_MAX_NODES = 64
HARD_MAX_EDGES = 128

if len(nodes) + len(new_ids) > max_nodes:
    stop_reason = "max_nodes"
```

**What it means:** Working-memory capacity exhausted. Like biological cognition, TMF can only hold bounded context in one query.

**Not a failure of memory quality.** Just finite resources. Agent can:
- Make multiple bounded queries (split the work)
- Increase limits (if allowed)
- Refine the query to target a narrower subgraph

`stop_reason` will be `"max_nodes"`, `"max_edges"`, or `"hop_limit"`. Coverage marked `"partial"`.

### Summary: Pain vs Boundary vs Limit

| Stop Type | Meaning | What Agent Should Do | Appears in Result? |
|---|---|---|---|
| **Boundary** | Chain reached semantic end-point (persistence/async) | Accept boundary as valid terminus | ✅ nodes + edges + boundaries list |
| **Async** | Edge is message-passing, not sync call | Treat as architectural boundary | ✅ edges (marked `async_handoff: true`) |
| **Stale** | Memory failed freshness check — **PAIN** | Re-read source, update memory | ❌ only in `stale_or_unknown` |
| **Limit** | Working memory full (hop/node/edge limit) | Split query or increase limit | ✅ partial result up to limit |

## Core Value Proposition

TMF is a **cross-session call-chain continuity system** for AI coding agents. It solves the "tunnel vision bug" problem:

**The problem:** Agent understands a complete call chain `A → B → C → D` in session t₀. Code changes at t₁ (e.g., `C` logic modified). Agent receives task "modify A" at t₂. If the agent only looks at `A`, it may introduce bugs because it doesn't see the downstream impact on the changed `C`.

**TMF's solution:**
1. **Precise staleness detection:** When the agent queries the `A → B → C → D` chain from memory, TMF detects that `C` has changed and blocks stale memory (pain reflex)
2. **Localized reread:** Forces the agent to reread only `C` and its direct neighbors, not the entire codebase
3. **Complete chain understanding:** Ensures the agent sees the full call chain when making changes, avoiding "tunnel vision" bugs

**What TMF is for:**
- Preventing bugs caused by incomplete call-chain understanding
- Cross-session cognitive continuity through precise staleness detection
- Efficient localized rereads (only changed nodes, not entire codebase)
- Boundary-aware navigation (knows where sync chains end: DB writes, message queues)

**What TMF is NOT for:**
- Helping agents understand code on first encounter
- Reducing source rereads through cached "facts"
- Providing "remembered truths" for direct reuse

Fresh claims don't replace source — they tell you **which source to re-read** and **whether your remembered chain is still valid**.

**Current status:** Mechanics proven (freshness detection, stale blocking, boundary detection work). Value hypothesis **untested** — no valid experiment has measured cross-session call-chain continuity or bug prevention yet.

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

From PyPI:

```bash
python -m pip install true-memory-fragments
```

For development from a source checkout:

```bash
python -m pip install -e .
```

Runtime dependencies are intentionally empty. Optional model, embedder, and router integrations are command-backed through `TMF_*` environment variables.

Java step0 nodes are optional and dependency-isolated. Enable them with:

```bash
python -m pip install "true-memory-fragments[java]"
```

From a source checkout: `python -m pip install -e ".[java]"`. This installs `tree_sitter==0.25.2` and `tree_sitter_java==0.23.5`.

If those packages are absent, `.java` reads still return a file/source fallback claim plus a degrade hint; Python behavior remains unchanged.

### Offline Java verifier (Linux x86_64 / CPython 3.12)

This package vendors prebuilt MIT-licensed wheels for offline Java step0 review on Linux x86_64, CPython 3.12, glibc 2.39 / Ubuntu 24.04 compatible systems. MIT license texts are copied into `vendor/licenses/`.

The offline verifier never installs into system Python. It creates a repository-local venv and installs only from `vendor/wheels` with `--no-index`:

```bash
bash scripts/verify_java_offline.sh
```

Expected success marker:

```text
JAVA OFFLINE VERIFY: PASS
```

## Quick Start

### Store claims for a repository

```bash
tmf store /path/to/repo
```

Claims are written to `/path/to/repo/.tmf/`.

### Query a node

```bash
tmf get <claim-id>
```

Returns JSON with claim body, freshness, and blob bindings.

### Bounded fragment query

```bash
tmf fragment <entry-claim-id> --relations calls reads --hops 3
```

Returns a bounded call/read graph starting from `entry-claim-id`, expanding up to 3 hops, respecting semantic boundaries (persistence, async handoff), and reporting stale claims as `stale_or_unknown` with explicit `stop_reason`.

**Four stop types:**
- `boundaries`: reached semantic end-points (DB writes, message queues)
- `async_handoff: true`: edge is async, not sync call flow
- `stale_or_unknown`: memory failure — must re-read source
- `stop_reason: max_nodes/max_edges/hop_limit`: working memory full

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

## Documentation

- [Agent runtime value status](docs/AGENT_RUNTIME_VALUE_STATUS.md) — current experiment ruling
- [Java enterprise roadmap](docs/JAVA_ENTERPRISE_ROADMAP.md) — enterprise capability scope
- [Guava validation report](GUAVA_VALIDATION_REPORT.md) — routing shape + boundary detection validation

## License

MIT
