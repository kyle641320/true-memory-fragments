# r17 model pilot requirements

- Model must emit intent/patch plan, not edit source directly.
- Runner must check stale-boundary evidence before any patch application.
- If stale boundary is touched, block first, reread, then apply.
- Treatment gets the gate; control does not.
- Per-arm artifacts isolated.
- Hidden scorer checks current drift preservation.
- If a pilot cannot enforce these rules, do not run it.
