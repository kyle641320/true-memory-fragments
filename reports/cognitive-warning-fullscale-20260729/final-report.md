# TMF Cognitive Warning Full-Scale Experiment Report

## Scope

- Planned order: 10 paired groups; each group runs 8 control samples then 8 treatment samples.
- Planned total: 160 samples.
- Valid total: 160 samples; invalid total: 0.
- Model: `aisz/gpt-5.5`.
- Hidden reasoning is not exposed by this OpenClaw run; archived transcripts preserve full visible assistant text, tool calls, tool results, turn JSON, prompts, and generated code.

## Prompt SHA256 Proof

- control task prompt: `4b24b1f0ea146dfa0cfdcd21a80662f1390aab4c4ea254c28de7c49b6523fd4a`
- treatment task prompt: `d0e8352bd9ddd98ee2a22606a4eb6a0fe791e256d81f687a918c08c55523bc3a`
- treatment without warning: `4b24b1f0ea146dfa0cfdcd21a80662f1390aab4c4ea254c28de7c49b6523fd4a`
- normalized prompts equal: `True`
- production warning renderer: `/root/.openclaw/workspace/projects/tmf-reflex-hook/hook/tmf-sessionstart-calibration.py`
- renderer sha256: `bb86fa4c0c163a3c8cd1f616cc4125165fa134d61fc74b5d3302a3570c843006`
- warning text sha256: `2ab2bfe029207aaf149604c82e6347e5d6b96e4871c0b21208e208a166f36770`

## Primary Metric

| arm | valid | stale_error | non_stale | stale_error_rate | correct |
|---|---:|---:|---:|---:|---:|
| control | 80 | 80 | 0 | 100.0% | 0 |
| treatment | 80 | 8 | 72 | 10.0% | 72 |

- Fisher exact two-sided p: `2.1326174722623323e-12`
- Absolute stale-error reduction, control minus treatment: `0.9` (90.0%)
- Newcombe 95% CI for absolute reduction: `(0.8033434772528575, 0.9484523844326191)` (80.3%, 94.8%)
- Relative risk, treatment/control: `0.1`
- Approximate minimum detectable absolute reduction at 80% power if needed: `None`

## Secondary Metric: reread_f

| arm | reread_f | valid | reread_rate | direct_probe_f |
|---|---:|---:|---:|---:|
| control | 31 | 80 | 38.8% | 0 |
| treatment | 80 | 80 | 100.0% | 0 |

## Group Stability

| arm | group stale-error counts g1-g10 | group valid counts g1-g10 | sample std |
|---|---|---|---:|
| control | [8, 8, 8, 8, 8, 8, 8, 8, 8, 8] | [8, 8, 8, 8, 8, 8, 8, 8, 8, 8] | 0.0 |
| treatment | [1, 1, 1, 0, 0, 1, 1, 2, 1, 0] | [8, 8, 8, 8, 8, 8, 8, 8, 8, 8] | 0.6324555320336759 |

## Invalid Samples

- none

## Archive Paths

- Runs and full transcript/code archive: `/root/.openclaw/workspace/experiments/tmf-cognitive-warning-fullscale-20260729/runs`
- Samples JSON: `/root/.openclaw/workspace/experiments/tmf-cognitive-warning-fullscale-20260729/results/samples.json`
- Summary JSON: `/root/.openclaw/workspace/experiments/tmf-cognitive-warning-fullscale-20260729/results/final-summary.json`
- Prompt proof: `/root/.openclaw/workspace/experiments/tmf-cognitive-warning-fullscale-20260729/results/prompt-sha256-proof.json`
- Execution order: `/root/.openclaw/workspace/experiments/tmf-cognitive-warning-fullscale-20260729/results/execution-order.json`

## Pre-Registered Conclusions

- ① 主指标：treatment 显著低于 control，按预注册判定 TMF 在本认知不可执行场景有效。
- ② 次指标：reread_f 为 control 31/80，treatment 80/80；该指标只解释机制，不替代正确性主指标。
- ③ 组间稳定：control counts [8, 8, 8, 8, 8, 8, 8, 8, 8, 8] std 0.0；treatment counts [1, 1, 1, 0, 0, 1, 1, 2, 1, 0] std 0.6324555320336759。
- ④ 健全性：control stale-error rate 100.0%；control 错误率不低于 20%，陷阱强度健全性通过。

Conclusion: In this run, warning changed stale-error rate from 100.0% to 10.0% (Fisher exact p=2.1326174722623323e-12); reread rate changed from 38.8% to 100.0%.
