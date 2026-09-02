#!/usr/bin/env python3
"""Mixed-language freshness oracle for TMF.

Creates a small Python+Java repo, derives claims for both languages, mutates one
Python function and one Java method, and verifies freshness invalidation remains
localized: changed symbols go stale while unrelated cross-language claims stay
fresh. This is an evidence script, not TMF engine code.
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

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_function_claim_id, stable_java_node_claim_id
from tmf.retrieve import refresh_path
from tmf.store import Store

OUT_JSON = ROOT / "reports" / "mixed-language-freshness-20260902.json"
OUT_MD = ROOT / "TMF_MIXED_LANGUAGE_FRESHNESS_20260902.md"


def run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def write_fixture(repo: Path) -> None:
    (repo / "app.py").write_text(
        """
def changed_py(x):
    return x + 1

def stable_py(y):
    return y * 2
""".lstrip()
    )
    src = repo / "src/main/java/demo"
    src.mkdir(parents=True)
    (src / "Service.java").write_text(
        """
package demo;
public class Service {
    public int changedJava(int x) { return x + 1; }
    public int stableJava(int y) { return y * 2; }
}
""".lstrip()
    )


def git_init(repo: Path) -> None:
    run(["git", "init", "-q", "-b", "main"], repo)
    run(["git", "config", "user.email", "tmf@example.invalid"], repo)
    run(["git", "config", "user.name", "TMF Test"], repo)
    run(["git", "add", "."], repo)
    run(["git", "commit", "-q", "-m", "initial"], repo)


def status(repo: GitRepo, store: Store, claim_id: str) -> dict[str, Any]:
    claim = store.get_claim(claim_id)
    if claim is None:
        return {"exists": False, "fresh": False, "reason": "missing"}
    f = check_freshness(repo, claim)
    return {"exists": True, "fresh": f.fresh, "stale_bindings": f.stale_bindings}


def evaluate_case(actual_fresh: bool, expected_fresh: bool) -> dict[str, Any]:
    return {"expected_fresh": expected_fresh, "actual_fresh": actual_fresh, "pass": actual_fresh is expected_fresh}


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="tmf-mixed-freshness-") as td:
        repo_path = Path(td)
        write_fixture(repo_path)
        git_init(repo_path)
        refresh_path(repo_path, "app.py")
        refresh_path(repo_path, "src/main/java/demo/Service.java")
        repo = GitRepo(repo_path)
        store = Store(repo_path)
        ids = {
            "changed_py": stable_function_claim_id("app.py", "changed_py"),
            "stable_py": stable_function_claim_id("app.py", "stable_py"),
            "service_class": stable_java_node_claim_id("src/main/java/demo/Service.java", "Service", "class"),
            "changed_java": stable_java_node_claim_id("src/main/java/demo/Service.java", "Service.changedJava", "method"),
            "stable_java": stable_java_node_claim_id("src/main/java/demo/Service.java", "Service.stableJava", "method"),
        }
        initial = {name: status(repo, store, cid) for name, cid in ids.items()}

        # Mutate one Python function and one Java method, then commit to make git
        # blob comparisons authoritative for TMF freshness.
        (repo_path / "app.py").write_text(
            """
def changed_py(x):
    return x + 42

def stable_py(y):
    return y * 2
""".lstrip()
        )
        (repo_path / "src/main/java/demo/Service.java").write_text(
            """
package demo;
public class Service {
    public int changedJava(int x) { return x + 42; }
    public int stableJava(int y) { return y * 2; }
}
""".lstrip()
        )
        run(["git", "add", "."], repo_path)
        run(["git", "commit", "-q", "-m", "mutate localized symbols"], repo_path)
        repo2 = GitRepo(repo_path)
        store2 = Store(repo_path)
        after = {name: status(repo2, store2, cid) for name, cid in ids.items()}
        expected = {
            "changed_py": False,
            "stable_py": True,
            "service_class": False,  # Java class span includes member body changes; this over-invalidates by design today.
            "changed_java": False,
            "stable_java": True,
        }
        cases = {name: evaluate_case(after[name]["fresh"], fresh) for name, fresh in expected.items()}
        passed = sum(1 for c in cases.values() if c["pass"])
        summary = {
            "cases": len(cases),
            "passed": passed,
            "failed": len(cases) - passed,
            "verdict": "PASS" if passed == len(cases) else "FAIL",
            "localized_changed_stale": cases["changed_py"]["pass"] and cases["changed_java"]["pass"],
            "cross_language_unrelated_fresh": cases["stable_py"]["pass"] and cases["stable_java"]["pass"],
            "java_class_overinvalidates_on_member_body_change": after["service_class"]["fresh"] is False,
        }
        result = {"schema": "tmf.mixed_language_freshness_oracle.v1", "summary": summary, "ids": ids, "initial": initial, "after_mutation": after, "cases": cases}
        OUT_JSON.parent.mkdir(exist_ok=True)
        OUT_JSON.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
        lines = [
            "# TMF Mixed-Language Freshness Oracle — 2026-09-02",
            "",
            f"Verdict: **{summary['verdict']}**.",
            "",
            "Scope: small Python+Java repository. The oracle mutates one Python function and one Java method after deriving claims, then verifies changed symbols are stale while unrelated Python/Java method/function claims remain fresh.",
            "",
            "## Summary",
            "",
            f"- Cases: {summary['passed']}/{summary['cases']} pass.",
            f"- Localized changed symbols stale: {summary['localized_changed_stale']}.",
            f"- Cross-language unrelated function/method claims remain fresh: {summary['cross_language_unrelated_fresh']}.",
            f"- Java class over-invalidates on member body change: {summary['java_class_overinvalidates_on_member_body_change']} (documented current behavior, not counted as failure in this oracle).",
            "",
            "## Cases",
            "",
        ]
        for name, case in cases.items():
            lines.append(f"- {name}: {'PASS' if case['pass'] else 'FAIL'}; expected_fresh={case['expected_fresh']}; actual_fresh={case['actual_fresh']}.")
        lines += [
            "",
            "## Interpretation",
            "",
            "This validates a bounded mixed-language freshness property: Python and Java claims can coexist, localized function/method mutations stale the relevant symbols, and unrelated function/method claims in either language remain fresh. The Java class-level claim still stales when a member body changes; this is current conservative over-invalidation and should not be marketed as class-level precision.",
        ]
        OUT_MD.write_text("\n".join(lines) + "\n")
        print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
