# Human audit — cognitive_continuity_v2 resumed smoke

Decision: **STOP — frozen smoke adoption gate failed; no full run.** The broker runtime was restored without changing the frozen experiment, and `smoke-2pair-resumed` completed with 2/2 valid pairs. SOURCE and TMF each succeeded on 2/2 pairs, but qualified TMF adoption was 0/2; `STOP_GATES.md` requires at least 1/2, so full execution is prohibited.

The earlier `HUMAN_AUDIT.md` and `audit.json` remain the historical record of the broker-blocked attempt. Their runtime-blocked status is superseded by this resumed audit, not deleted or retroactively rewritten.

| Task | SOURCE success / phase-B repeat | TMF success / phase-B repeat | TMF task claim coverage | Tokens SOURCE / TMF |
|---|---|---|---|---:|
| B01 | yes; 1 read / 91 bytes | yes; 1 read / 91 bytes | one structural call-edge claim | 1,376 / 6,894 |
| B03 | yes; 2 reads / 102 bytes | yes; 2 reads / 102 bytes | none | 2,500 / 7,420 |

B01 demonstrates structural claim coverage, but the Agent still reread `flow.py`; the claim was not used to avoid the repeat read. B03's derived claims did not cover the behavior needed by phase B. Likewise, preflight coverage of 2/10 tasks means structural claims were present, not that those claims were sufficient to answer specific implementation semantics. Current TMF-derived claim content therefore cannot generally replace a second source read.

This is **not a middleware mechanism failure**: the previously qualified freshness, stale-blocking, and delivery mechanics remain intact. It is a stopped Agent-value smoke: claim content/adoption/value remain unproved, and TMF used more tokens on both pairs. Source remains authoritative.
