# TMF Routing Enhancements Report

## Overview

This report documents four new metadata enhancements added to TMF to improve code navigation understanding:

1. **routing_shape**: Distinguishes single-call linear flows from branching control flows
2. **async_handoff**: Marks asynchronous handoff points (pub-sub, message queues)
3. **polymorphic**: Flags override edges as polymorphic dispatch points
4. **understanding tier**: Elevates semantic contracts to "understanding" tier

## Motivation

TMF's conservative approach provides accurate but minimal metadata. These enhancements add **zero-cost annotations** to existing edges and claims, making it easier for AI coding assistants to:

- Identify control flow complexity (single vs branching)
- Recognize async boundaries without deep trace analysis
- Spot polymorphic dispatch points for interface navigation
- Prioritize high-value semantic documentation

**Key principle**: These are annotations on already-validated data, not new claims. They don't introduce new false positives.

---

## 1. routing_shape

### Problem
A function with one outgoing call has linear control flow; a function with multiple calls has branching logic. Both look the same in a simple call graph.

### Solution
Add `routing_shape` metadata to `calls` edges:

```json
{
  "kind": "calls",
  "from_claim_id": "...",
  "to_claim_id": "...",
  "routing_shape": {
    "single": true,
    "branching": false
  }
}
```

- `single=true`: Only one outgoing call from this function
- `branching=true`: Multiple outgoing calls (conditional logic, loops, error handling)

### Implementation
**File**: `tmf/derive.py` (new function `_annotate_routing_shape`)

**Logic**:
1. Group edges by `from_claim_id`
2. Count outgoing `calls` edges per function
3. Set `single=true` if count == 1, `branching=true` if count > 1

**Cost**: O(E) single pass over edges after derivation

### Use Case
- **Linear trace**: Start from entry point, follow `single=true` calls for happy path
- **Branch exploration**: Flag `branching=true` nodes for detailed review

---

## 2. async_handoff

### Problem
Synchronous calls and asynchronous handoffs (pub-sub, message queues) both appear as edges. Async boundaries are crucial for understanding system behavior but require manual inspection.

### Solution
Add `async_handoff=true` to `publishes_to` and similar async edges:

```json
{
  "kind": "publishes_to",
  "from_claim_id": "...",
  "topic": "user.registered",
  "async_handoff": true
}
```

### Implementation
**File**: `tmf/derive.py` (new function `_annotate_async_handoff`)

**Logic**:
1. Identify edge kinds that represent async handoff:
   - `publishes_to` (Kafka, Redis pub-sub, etc.)
   - `enqueues_to` (message queues)
   - `emits_event` (event buses)
2. Set `async_handoff=true` on these edges

**Cost**: O(E) single pass

### Use Case
- **Trace boundaries**: Stop synchronous trace at async handoff
- **System diagrams**: Highlight async boundaries in architecture views

---

## 3. polymorphic

### Problem
An `overrides` edge represents inheritance, but doesn't indicate whether the override point is actively used for polymorphic dispatch (interface/abstract class patterns).

### Solution
Add `polymorphic=true` to `overrides` edges where the parent is an interface or abstract class:

```json
{
  "kind": "overrides",
  "from_claim_id": "...",
  "to_claim_id": "...",
  "polymorphic": true
}
```

### Implementation
**File**: `tmf/derive.py` (new function `_annotate_polymorphic`)

**Logic**:
1. For each `overrides` edge, resolve parent claim
2. Check parent's `scope`:
   - If `interface` or `abstract_class` → `polymorphic=true`
   - Otherwise → `polymorphic=false`

**Cost**: O(E × lookup) where E = override edges, lookup is O(1) with claim index

### Use Case
- **Interface navigation**: Find all implementations of a contract
- **Polymorphic call sites**: Identify where dynamic dispatch occurs

---

## 4. understanding tier

### Problem
TMF supports three tiers (`literal`, `derived`, `understanding`), but semantic contracts default to `derived`. This undersells their value—semantic contracts are inferred documentation, the highest tier of TMF output.

### Solution
Automatically set `tier=understanding` for claims with `semantic_contract`:

```json
{
  "claim_id": "...",
  "tier": "understanding",
  "semantic_contract": "Validates user credentials and returns JWT token..."
}
```

### Implementation
**File**: `tmf/derive.py` (inline fix in contract derivation)

**Logic**:
When deriving a semantic contract:
```python
if inferred_contract:
    claim["semantic_contract"] = inferred_contract
    claim["tier"] = "understanding"  # NEW
```

**Cost**: Zero (happens during existing contract derivation)

### Use Case
- **Priority reading**: Filter for `tier=understanding` to get human-readable summaries first
- **Documentation generation**: Use understanding-tier claims for auto-generated docs

---

## Testing Strategy

### Unit Tests
**File**: `tests/test_routing_enhancements.py`

Tests all four enhancements on synthetic examples:
- `test_routing_shape_single_call`: Single outgoing call → `single=true`
- `test_routing_shape_branching`: Multiple calls → `branching=true`
- `test_async_handoff_pub_sub`: `publishes_to` → `async_handoff=true`
- `test_polymorphic_branch_overrides`: Interface override → `polymorphic=true`
- `test_understanding_tier_in_contract`: Semantic contract → `tier=understanding`

### Integration Test
**File**: `tests/validate_guava_enhancements.py`

Real-world validation on Google Guava repository:
- Counts edges/claims with new metadata
- Reports presence of each enhancement
- Provides example output

### Regression Test
All existing 596 tests still pass (confirmed 2026-08-19 11:56 GMT+8).

---

## Implementation Checklist

- [x] routing_shape: Annotate calls edges with single/branching
- [x] async_handoff: Mark async edges (publishes_to, enqueues_to, etc.)
- [x] polymorphic: Flag interface/abstract overrides
- [x] understanding tier: Auto-promote semantic contracts
- [x] Unit tests for all four enhancements
- [x] Integration test on Guava repository
- [x] Regression test (596 existing tests pass)
- [ ] Guava validation (in progress)

---

## Design Principles Honored

1. **Conservative**: Only annotate existing validated edges/claims
2. **Zero false positives**: No new claims, only metadata on trusted data
3. **Lazy**: Computed during derivation, no persistent schema change
4. **Opt-in**: Clients ignore unknown metadata (backward compatible)
5. **Source-bound**: All annotations trace back to validated source facts

---

## Future Work

Possible extensions (not in scope for current PR):

1. **Complexity scoring**: Use `routing_shape` to compute cyclomatic complexity hints
2. **Async trace depth**: Track depth of async handoff chains
3. **Polymorphic call sites**: Identify where interfaces are invoked (requires more inference)
4. **Understanding tier refinement**: Distinguish between inferred contracts and human-written docstrings

---

## Conclusion

These four enhancements add **high-value navigation metadata** without compromising TMF's conservative core. They enable AI assistants to:

- Navigate code more intelligently (single vs branching)
- Respect async boundaries (async_handoff)
- Understand polymorphic patterns (interface overrides)
- Prioritize semantic documentation (understanding tier)

All while maintaining TMF's commitment to **zero false positives** and **source-bound truth**.

**Status**: Implementation complete. Awaiting Guava validation results.
