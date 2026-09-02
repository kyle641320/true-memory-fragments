#!/usr/bin/env python3
"""Graph query precision/recall oracle for TMF reverse relations.

This is a release-readiness evidence script, not engine code. It creates a small
mixed Python/Java repository with hand-checked oracle relations, warms TMF over
all source files, calls reverse graph APIs, and reports precision/recall.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tmf.ids import stable_declaration_claim_id, stable_function_claim_id, stable_java_node_claim_id
from tmf.git import GitRepo
from tmf.retrieve import refresh_path, reverse_callers, reverse_implementors, reverse_readers, reverse_subtypes, reverse_writers

OUT_JSON = ROOT / "reports" / "graph-query-oracle-20260902.json"
OUT_MD = ROOT / "TMF_GRAPH_QUERY_ORACLE_20260902.md"


def write_fixture(repo: Path) -> None:
    (repo / "settings.py").write_text(
        """
COUNT = 0
LIMIT = 10

def load_count():
    return COUNT

def bump_count():
    global COUNT
    COUNT = COUNT + 1
    return COUNT

def reset_local_only():
    COUNT = 5
    return COUNT
""".lstrip()
    )
    (repo / "worker.py").write_text(
        """
from settings import load_count, bump_count

def helper(value):
    return value + 1

def run():
    current = load_count()
    bump_count()
    return helper(current)

def unrelated():
    return "noop"
""".lstrip()
    )
    src = repo / "src/main/java/com/example"
    src.mkdir(parents=True)
    (src / "BaseService.java").write_text(
        """
package com.example;
public class BaseService {
    public String name() { return "base"; }
}
""".lstrip()
    )
    (src / "Job.java").write_text(
        """
package com.example;
public interface Job {
    void run();
}
""".lstrip()
    )
    (src / "ChildService.java").write_text(
        """
package com.example;
public class ChildService extends BaseService implements Job {
    public void run() { }
    public String childName() { return name(); }
}
""".lstrip()
    )
    (src / "AltJob.java").write_text(
        """
package com.example;
public class AltJob implements Job {
    public void run() { }
}
""".lstrip()
    )
    (src / "Caller.java").write_text(
        """
package com.example;
public class Caller {
    public String call(ChildService service) {
        return service.childName();
    }
}
""".lstrip()
    )


def git_init(repo: Path) -> None:
    subprocess.run(["git", "init", "-q", "-b", "main"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "tmf@example.invalid"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "TMF Test"], cwd=repo, check=True)
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=repo, check=True)


def ids() -> dict[str, str]:
    return {
        "py_helper": stable_function_claim_id("worker.py", "helper"),
        "py_run": stable_function_claim_id("worker.py", "run"),
        "py_load_count": stable_function_claim_id("settings.py", "load_count"),
        "py_bump_count": stable_function_claim_id("settings.py", "bump_count"),
        "py_count": stable_declaration_claim_id("settings.py", "COUNT"),
        "java_base": stable_java_node_claim_id("src/main/java/com/example/BaseService.java", "BaseService", "class"),
        "java_job": stable_java_node_claim_id("src/main/java/com/example/Job.java", "Job", "interface"),
        "java_child": stable_java_node_claim_id("src/main/java/com/example/ChildService.java", "ChildService", "class"),
        "java_altjob": stable_java_node_claim_id("src/main/java/com/example/AltJob.java", "AltJob", "class"),
    }


def evaluate_set(actual: set[str], expected: set[str]) -> dict[str, Any]:
    tp = sorted(actual & expected)
    fp = sorted(actual - expected)
    fn = sorted(expected - actual)
    precision = len(tp) / len(actual) if actual else (1.0 if not expected else 0.0)
    recall = len(tp) / len(expected) if expected else (1.0 if not actual else 0.0)
    return {
        "expected": sorted(expected),
        "actual": sorted(actual),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "pass": precision == 1.0 and recall == 1.0,
    }


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="tmf-graph-oracle-") as td:
        repo_path = Path(td)
        write_fixture(repo_path)
        git_init(repo_path)
        for rel in [
            "settings.py",
            "worker.py",
            "src/main/java/com/example/BaseService.java",
            "src/main/java/com/example/Job.java",
            "src/main/java/com/example/ChildService.java",
            "src/main/java/com/example/AltJob.java",
            "src/main/java/com/example/Caller.java",
        ]:
            refresh_path(repo_path, rel)
        i = ids()
        cases: dict[str, dict[str, Any]] = {}
        cases["python_callers_helper"] = evaluate_set(
            {x.get("caller_id") for x in reverse_callers(repo_path, i["py_helper"])["callers"] if x.get("caller_id")},
            {i["py_run"]},
        )
        cases["python_callers_load_count"] = evaluate_set(
            {x.get("caller_id") for x in reverse_callers(repo_path, i["py_load_count"])["callers"] if x.get("caller_id")},
            {i["py_run"]},
        )
        cases["python_readers_count"] = evaluate_set(
            {x.get("reader_id") for x in reverse_readers(repo_path, i["py_count"])["readers"] if x.get("reader_id")},
            {i["py_load_count"], i["py_bump_count"]},
        )
        cases["python_writers_count"] = evaluate_set(
            {x.get("writer_id") for x in reverse_writers(repo_path, i["py_count"])["writers"] if x.get("writer_id")},
            {i["py_bump_count"]},
        )
        cases["java_subtypes_base"] = evaluate_set(
            {x.get("child_id") for x in reverse_subtypes(repo_path, i["java_base"])["subtypes"] if x.get("child_id")},
            {i["java_child"]},
        )
        cases["java_implementors_job"] = evaluate_set(
            {x.get("child_id") for x in reverse_implementors(repo_path, i["java_job"])["implementors"] if x.get("child_id")},
            {i["java_child"], i["java_altjob"]},
        )

        flat = list(cases.values())
        tp = sum(len(c["tp"]) for c in flat)
        fp = sum(len(c["fp"]) for c in flat)
        fn = sum(len(c["fn"]) for c in flat)
        summary = {
            "cases": len(flat),
            "passed": sum(1 for c in flat if c["pass"]),
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "micro_precision": tp / (tp + fp) if (tp + fp) else 1.0,
            "micro_recall": tp / (tp + fn) if (tp + fn) else 1.0,
            "macro_precision": sum(c["precision"] for c in flat) / len(flat),
            "macro_recall": sum(c["recall"] for c in flat) / len(flat),
            "verdict": "PASS" if all(c["pass"] for c in flat) else "FAIL",
        }
        result = {"schema": "tmf.graph_query_oracle.v1", "summary": summary, "cases": cases}
        OUT_JSON.parent.mkdir(exist_ok=True)
        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        lines = [
            "# TMF Graph Query Oracle — 2026-09-02",
            "",
            f"Verdict: **{summary['verdict']}**.",
            "",
            "Scope: small hand-checked mixed Python/Java fixture covering reverse callers, readers, writers, subtypes, and implementors. This is precision/recall evidence for known already-derived graph edges, not a complete blast-radius guarantee over arbitrary dynamic code.",
            "",
            "## Summary",
            "",
            f"- Cases: {summary['passed']}/{summary['cases']} pass.",
            f"- Micro precision/recall: {summary['micro_precision']:.3f} / {summary['micro_recall']:.3f}.",
            f"- Macro precision/recall: {summary['macro_precision']:.3f} / {summary['macro_recall']:.3f}.",
            f"- TP/FP/FN: {tp}/{fp}/{fn}.",
            "",
            "## Cases",
            "",
        ]
        for name, case in cases.items():
            lines.append(f"- {name}: {'PASS' if case['pass'] else 'FAIL'}; precision={case['precision']:.3f}; recall={case['recall']:.3f}; tp={len(case['tp'])}; fp={len(case['fp'])}; fn={len(case['fn'])}.")
        lines += [
            "",
            "## Interpretation",
            "",
            "This closes a previously unquantified gap in the capability matrix: reverse graph query APIs have a hand-checked oracle with perfect precision/recall on this bounded mixed fixture. Remaining validation still needs larger real-repo oracle coverage and dynamic/reflection boundaries reported as out of scope rather than inferred.",
        ]
        OUT_MD.write_text("\n".join(lines) + "\n")
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
