# R21 4-arm report

Guava-only benchmark under max 4 files/220 lines/8 calls. Raw, protocol-clean, and semantic statuses are separated.

| Arm | Protocol | Oracle | Semantic |
|---|---:|---|---|
| a1_stale_note | False | fail | fail |
| a2_entry_hints | True | pass_completion_listener_after_publication | pass |
| a3_locator_min | True | pass_completion_listener_after_publication | pass |
| a4_locator_full | True | pass_completion_listener_after_publication | pass |

Mechanical checker exit code: 0. No SOURCE_ONLY-vs-TMF superiority claim; this is locator/budget effect only.
