#!/usr/bin/env python3
"""Analyze full-scale TMF warning experiment results."""
from __future__ import annotations

import json
import math
from pathlib import Path
from statistics import stdev

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"


def log_choose(n: int, k: int) -> float:
    if k < 0 or k > n:
        return float("-inf")
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def fisher_two_sided(a: int, b: int, c: int, d: int) -> float:
    # Table [[a,b],[c,d]], fixed margins. Two-sided p sums tables with prob <= observed.
    r1 = a + b
    r2 = c + d
    col1 = a + c
    n = r1 + r2
    def prob(x: int) -> float:
        return math.exp(log_choose(col1, x) + log_choose(n - col1, r1 - x) - log_choose(n, r1))
    lo = max(0, r1 - (n - col1))
    hi = min(r1, col1)
    p_obs = prob(a)
    return min(1.0, sum(px for x in range(lo, hi + 1) if (px := prob(x)) <= p_obs + 1e-12))


def wilson(k: int, n: int, z: float = 1.959963984540054) -> tuple[float | None, float | None]:
    if n == 0:
        return None, None
    phat = k / n
    denom = 1 + z * z / n
    center = (phat + z * z / (2 * n)) / denom
    half = z * math.sqrt((phat * (1 - phat) + z * z / (4 * n)) / n) / denom
    return max(0.0, center - half), min(1.0, center + half)


def newcombe_diff_ci(k1: int, n1: int, k2: int, n2: int) -> tuple[float | None, float | None]:
    # CI for p1-p2 using Newcombe Wilson score method without continuity correction.
    l1, u1 = wilson(k1, n1)
    l2, u2 = wilson(k2, n2)
    if l1 is None or l2 is None or u1 is None or u2 is None:
        return None, None
    p1 = k1 / n1
    p2 = k2 / n2
    delta = p1 - p2
    lower = delta - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    upper = delta + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return max(-1.0, lower), min(1.0, upper)


def normal_power_two_prop(n: int, p_control: float, p_treatment: float, alpha: float = 0.05) -> float:
    # Approximate two-sided z-test power, used only for MDE reporting if Fisher not significant.
    if p_control == p_treatment:
        return alpha
    z_alpha = 1.959963984540054
    pooled = (p_control + p_treatment) / 2
    se0 = math.sqrt(2 * pooled * (1 - pooled) / n)
    se1 = math.sqrt((p_control * (1 - p_control) + p_treatment * (1 - p_treatment)) / n)
    if se0 == 0 or se1 == 0:
        return 1.0 if p_control != p_treatment else alpha
    mu = abs(p_control - p_treatment) / se1
    threshold = z_alpha * se0 / se1
    # Phi(mu-threshold) + Phi(-mu-threshold)
    phi = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
    return (1 - phi(threshold - mu)) + phi(-threshold - mu)


def detectable_effect(n: int, baseline: float, target_power: float = 0.8) -> float | None:
    lo, hi = 0.0, baseline
    if baseline <= 0:
        return None
    for _ in range(60):
        mid = (lo + hi) / 2
        power = normal_power_two_prop(n, baseline, max(0.0, baseline - mid))
        if power >= target_power:
            hi = mid
        else:
            lo = mid
    return hi


def pct(x: float | None) -> str:
    if x is None:
        return "NA"
    return f"{100 * x:.1f}%"


def main() -> int:
    samples_path = RESULTS / "samples.json"
    if not samples_path.exists():
        raise SystemExit("missing results/samples.json")
    rows = json.loads(samples_path.read_text(encoding="utf-8"))
    valid = [r for r in rows if r["valid"]]
    invalid = [r for r in rows if not r["valid"]]
    by = {"control": [r for r in valid if r["group"] == "control"], "treatment": [r for r in valid if r["group"] == "treatment"]}
    stale = {g: sum(r["stale_error"] for r in vals) for g, vals in by.items()}
    non_stale = {g: len(vals) - stale[g] for g, vals in by.items()}
    correct = {g: sum(r["correct"] for r in vals) for g, vals in by.items()}
    reread = {g: sum(r["reread_f"] for r in vals) for g, vals in by.items()}
    direct_probe = {g: sum(r["direct_probe_f"] for r in vals) for g, vals in by.items()}
    p = fisher_two_sided(stale["control"], non_stale["control"], stale["treatment"], non_stale["treatment"]) if all(by.values()) else None
    control_rate = stale["control"] / len(by["control"]) if by["control"] else None
    treatment_rate = stale["treatment"] / len(by["treatment"]) if by["treatment"] else None
    rd = (control_rate - treatment_rate) if control_rate is not None and treatment_rate is not None else None
    rd_ci = newcombe_diff_ci(stale["control"], len(by["control"]), stale["treatment"], len(by["treatment"])) if all(by.values()) else (None, None)
    rr = (treatment_rate / control_rate) if control_rate and treatment_rate is not None else None
    group_counts: dict[str, list[int]] = {"control": [], "treatment": []}
    group_valids: dict[str, list[int]] = {"control": [], "treatment": []}
    for group in ("control", "treatment"):
        for gi in range(1, 11):
            g_rows = [r for r in valid if r["group"] == group and r["group_index"] == gi]
            group_counts[group].append(sum(r["stale_error"] for r in g_rows))
            group_valids[group].append(len(g_rows))
    group_std = {g: (stdev(group_counts[g]) if len(group_counts[g]) > 1 else 0.0) for g in group_counts}
    both_below_10 = bool(control_rate is not None and treatment_rate is not None and control_rate < 0.10 and treatment_rate < 0.10)
    trap_weak = bool(control_rate is not None and control_rate < 0.20)
    significant_lower = bool(p is not None and p < 0.05 and treatment_rate is not None and control_rate is not None and treatment_rate < control_rate)
    mde = detectable_effect(min(len(by["control"]), len(by["treatment"])), control_rate) if control_rate is not None and not significant_lower else None
    summary = {
        "n_planned": len(rows),
        "n_valid": len(valid),
        "n_invalid": len(invalid),
        "by_arm": {
            g: {
                "valid": len(by[g]),
                "stale_error": stale[g],
                "non_stale": non_stale[g],
                "correct": correct[g],
                "reread_f": reread[g],
                "direct_probe_f": direct_probe[g],
                "stale_error_rate": stale[g] / len(by[g]) if by[g] else None,
                "reread_rate": reread[g] / len(by[g]) if by[g] else None,
                "group_stale_error_counts": group_counts[g],
                "group_valid_counts": group_valids[g],
                "group_stale_error_std": group_std[g],
            }
            for g in ("control", "treatment")
        },
        "fisher_two_sided_p": p,
        "effect_size": {
            "absolute_stale_error_reduction_control_minus_treatment": rd,
            "newcombe_95ci_for_control_minus_treatment": rd_ci,
            "relative_risk_treatment_over_control": rr,
        },
        "pre_registered_decisions": {
            "significant_treatment_lower": significant_lower,
            "both_arms_below_10_percent": both_below_10,
            "control_below_20_percent_trap_strength_insufficient": trap_weak,
            "approx_min_detectable_absolute_reduction_80pct_power_if_needed": mde,
        },
        "invalid_samples": invalid,
        "archive_paths": {
            "runs": str(ROOT / "runs"),
            "samples": str(RESULTS / "samples.json"),
            "prompt_sha256_proof": str(RESULTS / "prompt-sha256-proof.json"),
        },
    }
    (RESULTS / "final-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    invalid_lines = [f"- {r['sample_id']}: {r['reason']}" for r in invalid] or ["- none"]
    prompt_proof = json.loads((RESULTS / "prompt-sha256-proof.json").read_text(encoding="utf-8")) if (RESULTS / "prompt-sha256-proof.json").exists() else {}
    if not by["control"] or not by["treatment"]:
        conclusion_1 = "有效样本不足，不能执行预注册主指标判定"
    elif significant_lower:
        conclusion_1 = "treatment 显著低于 control，按预注册判定 TMF 在本认知不可执行场景有效"
    else:
        conclusion_1 = "无显著差异，按预注册判定本场景未观察到效果"
    if both_below_10:
        conclusion_1 += "；同时两臂错误率均低于 10%，说明 agent 自发重读率已高、TMF 无提升空间"
    if trap_weak:
        conclusion_1 += "；control 错误率低于 20%，整场结论降级为陷阱强度不足"
    report = f"""# TMF Cognitive Warning Full-Scale Experiment Report

## Scope

- Planned order: 10 paired groups; each group runs 8 control samples then 8 treatment samples.
- Planned total: {len(rows)} samples.
- Valid total: {len(valid)} samples; invalid total: {len(invalid)}.
- Model: `{(RESULTS / 'model.txt').read_text(encoding='utf-8').strip() if (RESULTS / 'model.txt').exists() else 'unknown'}`.
- Hidden reasoning is not exposed by this OpenClaw run; archived transcripts preserve full visible assistant text, tool calls, tool results, turn JSON, prompts, and generated code.

## Prompt SHA256 Proof

- control task prompt: `{prompt_proof.get('control_task_prompt_sha256')}`
- treatment task prompt: `{prompt_proof.get('treatment_task_prompt_sha256')}`
- treatment without warning: `{prompt_proof.get('treatment_task_prompt_without_warning_sha256')}`
- normalized prompts equal: `{prompt_proof.get('normalized_prompts_equal')}`
- production warning renderer: `{prompt_proof.get('production_warning_renderer')}`
- renderer sha256: `{prompt_proof.get('production_warning_renderer_sha256')}`
- warning text sha256: `{prompt_proof.get('warning_text_sha256')}`

## Primary Metric

| arm | valid | stale_error | non_stale | stale_error_rate | correct |
|---|---:|---:|---:|---:|---:|
| control | {len(by['control'])} | {stale['control']} | {non_stale['control']} | {pct(control_rate)} | {correct['control']} |
| treatment | {len(by['treatment'])} | {stale['treatment']} | {non_stale['treatment']} | {pct(treatment_rate)} | {correct['treatment']} |

- Fisher exact two-sided p: `{p}`
- Absolute stale-error reduction, control minus treatment: `{rd}` ({pct(rd)})
- Newcombe 95% CI for absolute reduction: `{rd_ci}` ({pct(rd_ci[0])}, {pct(rd_ci[1])})
- Relative risk, treatment/control: `{rr}`
- Approximate minimum detectable absolute reduction at 80% power if needed: `{mde}`

## Secondary Metric: reread_f

| arm | reread_f | valid | reread_rate | direct_probe_f |
|---|---:|---:|---:|---:|
| control | {reread['control']} | {len(by['control'])} | {pct(reread['control'] / len(by['control']) if by['control'] else None)} | {direct_probe['control']} |
| treatment | {reread['treatment']} | {len(by['treatment'])} | {pct(reread['treatment'] / len(by['treatment']) if by['treatment'] else None)} | {direct_probe['treatment']} |

## Group Stability

| arm | group stale-error counts g1-g10 | group valid counts g1-g10 | sample std |
|---|---|---|---:|
| control | {group_counts['control']} | {group_valids['control']} | {group_std['control']} |
| treatment | {group_counts['treatment']} | {group_valids['treatment']} | {group_std['treatment']} |

## Invalid Samples

{chr(10).join(invalid_lines)}

## Archive Paths

- Runs and full transcript/code archive: `{ROOT / 'runs'}`
- Samples JSON: `{RESULTS / 'samples.json'}`
- Summary JSON: `{RESULTS / 'final-summary.json'}`
- Prompt proof: `{RESULTS / 'prompt-sha256-proof.json'}`
- Execution order: `{RESULTS / 'execution-order.json'}`

## Pre-Registered Conclusions

- ① 主指标：{conclusion_1}。
- ② 次指标：reread_f 为 control {reread['control']}/{len(by['control'])}，treatment {reread['treatment']}/{len(by['treatment'])}；该指标只解释机制，不替代正确性主指标。
- ③ 组间稳定：control counts {group_counts['control']} std {group_std['control']}；treatment counts {group_counts['treatment']} std {group_std['treatment']}。
- ④ 健全性：control stale-error rate {pct(control_rate)}；{'陷阱强度不足' if trap_weak else 'control 错误率不低于 20%，陷阱强度健全性通过'}。

Conclusion: In this run, warning changed stale-error rate from {pct(control_rate)} to {pct(treatment_rate)} (Fisher exact p={p}); reread rate changed from {pct(reread['control'] / len(by['control']) if by['control'] else None)} to {pct(reread['treatment'] / len(by['treatment']) if by['treatment'] else None)}.
"""
    (RESULTS / "final-report.md").write_text(report, encoding="utf-8")
    print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
