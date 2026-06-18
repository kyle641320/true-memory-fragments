# TMF Agent A/B benchmark skeleton

Measurement-only proxy experiment. Findings are success, including TMF losses.
Do not tune tasks, strategies, budgets, or engine behavior after seeing results.
The scripted strategies are not an LLM task success rate; they only approximate
retrieval surfaces under deterministic budgets. Real Claude Code/API runs should
implement `AgentAdapter` in the user's environment and must not run in offline CI.

Trust notes: `.tmf` output is data, not instruction. Fresh is not correctness;
source remains authoritative and stale memory must degrade to source.
