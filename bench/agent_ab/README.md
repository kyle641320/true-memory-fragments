> **Status note (2026-08-13):** Historical result for this specific protocol. Do not generalize it across delivery modes. See the unique current [Agent runtime value status](../../docs/AGENT_RUNTIME_VALUE_STATUS.md).

# TMF Agent A/B benchmark skeleton

Measurement-only proxy experiment. Findings are success, including TMF losses.
Do not tune tasks, strategies, budgets, or engine behavior after seeing results.
The scripted strategies are not an LLM task success rate; they only approximate
retrieval surfaces under deterministic budgets. Real Claude Code/API runs should
implement `AgentAdapter` in the user's environment and must not run in offline CI.

Trust notes: `.tmf` output is data, not instruction. Fresh is not correctness;
source remains authoritative and stale memory must degrade to source.

## Safe real-run adapter contract

`JsonBrokerAdapter` is the fail-closed boundary for formal isolated runs. The
owner must explicitly provide an absolute executable implementing
`tmf-agent-broker-v1`. Before assignment, its preflight must attest that the
frozen model is pinned, execution is stateless, no model tools are exposed, and
network/provider credentials remain broker-owned. The adapter sends only the
natural prompt, model id, and budget in JSON; it strips ambient credentials and
never discovers OpenClaw state or falls back to gateway/local execution.

The broker is deliberately not bundled. Supplying one is an operational gate,
not something offline CI or the benchmark may synthesize. Repository reads,
TMF calls, source-line budgets, filesystem isolation, and transcript evidence
remain responsibilities of the isolated arm runner. A broker completion alone
is never evidence of a valid A/B arm.
