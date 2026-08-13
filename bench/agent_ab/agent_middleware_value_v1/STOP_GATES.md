# Frozen stop gates

1. Hash mismatch, model mismatch, broker not stateless/raw, source escape, unequal budgets, or middleware base mismatch => invalid/stop.
2. Smoke: both pairs valid; TMF success >= SOURCE; at least one fresh adoption; no stale trust error. Otherwise stop and report.
3. Full: stop immediately on middleware false injection, stale fact leak, or inability to enforce stale reread. Ordinary Agent failures continue and are attributed.
4. Never substitute a mechanism simulation for a blocked real Agent loop.
