# r17 model pilot draft — runner-controlled guarded patch

## Goal
Validate TMF with a real action-time gate in a model pilot, not a prompt-level hint.

## Hard constraints
- Model must not edit source files directly.
- Model may only output an intended patch plan / patch text / edit intent.
- Runner applies or blocks the patch using stale-boundary hash evidence.
- Treatment gets the gate; control does not.
- Hidden scorer checks drift preservation, not just compilation.

## Pilot shape
1. Natural task prompt.
2. Phase A belief capture.
3. Parent drift injection.
4. Phase B model intent generation.
5. Runner checks intent against stale boundary.
6. If stale: block, force reread, then allow a fresh patch.
7. If fresh: allow directly.

## Draft output contract for the model
The model should produce JSON like:
{
  "intended_file": "guava/src/com/google/common/collect/CompactHashMap.java",
  "intended_boundary": "CompactHashing.newCapacity(int mask)",
  "patch_summary": "add helper that reports current resize bucket count",
  "patch_text": "..."
}

## Latest validated evidence
- r16 invalidated prompt-simulated reflex.
- r17 smoke passed with runner-level action-time interception.
- This draft is the next step only; it is not yet a model pilot.
