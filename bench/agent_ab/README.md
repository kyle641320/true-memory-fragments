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

## GUAVA_M10_PREREAD_R50 — scoped stale-context safety evidence (2026-08-28)

Formal 4-arm real-Guava run under `same_version_chain_v1` with 50 repeats per arm (200 raw runs).

Artifacts:
- Runner report: `same_version_chain_v1/results/GUAVA_M10_PREREAD_R50_REPORT.md`
- Independent audit: `same_version_chain_v1/results/GUAVA_M10_PREREAD_R50_INDEPENDENT_AUDIT.md`
- Machine summary: `same_version_chain_v1/results/GUAVA_M10_PREREAD_R50_INDEPENDENT_AUDIT.json`
- Raw transcripts: `same_version_chain_v1/results/raw/guava_m10_preread_r50/`

Headline: stale pre-read/doc controls collapsed by anchoring the agent to an obsolete inline queue-drain boundary (`wrong_inline_loop_site` 43/50 and 45/50). `TMF_STALE_GATED` avoided wrong-inline placements (0/50) and raw-passed 42/50, close to SOURCE_ONLY 40/50. Interpret raw pass rates with attribution: SOURCE_ONLY/TMF failures are mostly protocol/no-final noise, not semantic boundary failures; stale arms contain both true stale-boundary failures and protocol noise. This is positive evidence for stale-context safety, not broad productivity or token-saving proof.
