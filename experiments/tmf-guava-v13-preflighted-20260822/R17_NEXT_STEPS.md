# r17 next steps

## Status
- Zero-model runner-level action-time interception smoke: PASS
- Subagent protocol-builder failed due model channel 503

## What is now true
- Prompt-simulated reflex is invalid.
- A runner can block stale-boundary actions before patch application.
- The next model pilot must be runner-controlled, not direct-edit based.

## Minimum valid model pilot shape
1. Natural task prompt does not name the final file/method.
2. Model produces a patch plan or edit intent only.
3. Runner checks the intended action against stale-boundary hash evidence.
4. If stale, runner blocks and forces reread before apply.
5. Control gets no reflex gate.
6. Treatment gets the same gate.
7. Hidden scorer measures whether the final patch preserves current drift.

## Hard stop conditions
- If the model is allowed to edit source directly, the pilot is invalid.
- If the gate is only textual, the pilot is invalid.
- If the task names the exact boundary up front, the pilot is too hinted.
- If model channel 503 persists, defer pilot and keep the smoke as the latest valid evidence.
