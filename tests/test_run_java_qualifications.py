from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


RUNNER_PATH = Path(__file__).resolve().parents[1] / "tools" / "run_java_qualifications.py"
SPEC = importlib.util.spec_from_file_location("run_java_qualifications", RUNNER_PATH)
assert SPEC is not None and SPEC.loader is not None
runner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(runner)


class JavaQualificationRunnerTest(unittest.TestCase):
    def _write_verifier(self, tools: Path, name: str, corpus: str) -> Path:
        path = tools / f"verify_java_{name}_qualification.py"
        path.write_text(f'FIX = "fixtures/{corpus}"\n', encoding="utf-8")
        return path

    def _write_builds(self, root: Path, corpus: str, *, split: bool = True) -> None:
        fixture = root / "fixtures" / corpus
        maven = fixture / ("maven/pom.xml" if split else "pom.xml")
        gradle = fixture / ("gradle/build.gradle" if split else "build.gradle")
        maven.parent.mkdir(parents=True, exist_ok=True)
        gradle.parent.mkdir(parents=True, exist_ok=True)
        maven.touch()
        gradle.touch()
        source = fixture / "src/main/java/Fixture.java"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text(f"class {corpus.replace('-', '_')} {{}}\n", encoding="utf-8")

    def test_verifier_paths_discovers_only_matching_files_in_name_order(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            tools = Path(directory)
            for name in (
                "verify_java_z_qualification.py",
                "verify_java_a_qualification.py",
                "verify_python_x_qualification.py",
                "verify_java_incomplete.py",
            ):
                (tools / name).touch()
            with mock.patch.object(runner, "TOOLS", tools):
                self.assertEqual(
                    [path.name for path in runner.verifier_paths()],
                    ["verify_java_a_qualification.py", "verify_java_z_qualification.py"],
                )

    def test_fixture_corpus_audit_accepts_independent_split_and_root_layouts(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tools = root / "tools"
            tools.mkdir()
            paths = [
                self._write_verifier(tools, "alpha", "java-alpha-heldout"),
                self._write_verifier(tools, "beta", "java-beta-heldout"),
            ]
            self._write_builds(root, "java-alpha-heldout")
            self._write_builds(root, "java-beta-heldout", split=False)
            with mock.patch.object(runner, "ROOT", root):
                runner.validate_fixture_corpora(paths, {"shared_fixture_corpora": {}})

    def test_fixture_corpus_audit_rejects_cross_adapter_borrowing(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tools = root / "tools"
            tools.mkdir()
            path = self._write_verifier(tools, "alpha", "java-beta-heldout")
            self._write_builds(root, "java-beta-heldout")
            with mock.patch.object(runner, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "fixture mismatch for alpha"):
                    runner.validate_fixture_corpora([path], {"shared_fixture_corpora": {}})

    def test_fixture_corpus_audit_requires_auditable_shared_reason(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tools = root / "tools"
            tools.mkdir()
            path = self._write_verifier(tools, "alpha", "java-common-heldout")
            self._write_builds(root, "java-common-heldout")
            manifest = {"shared_fixture_corpora": {"alpha": {"corpus": "java-common-heldout", "reason": "too short"}}}
            with mock.patch.object(runner, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "auditable reason"):
                    runner.validate_fixture_corpora([path], manifest)

    def test_fixture_corpus_audit_rejects_renamed_mechanical_copy(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            tools = root / "tools"
            tools.mkdir()
            paths = [
                self._write_verifier(tools, "alpha", "java-alpha-heldout"),
                self._write_verifier(tools, "beta", "java-beta-heldout"),
            ]
            self._write_builds(root, "java-alpha-heldout")
            self._write_builds(root, "java-beta-heldout")
            alpha = root / "fixtures/java-alpha-heldout/src/main/java/Fixture.java"
            beta = root / "fixtures/java-beta-heldout/src/main/java/Fixture.java"
            beta.write_bytes(alpha.read_bytes())
            with mock.patch.object(runner, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "identical evidence"):
                    runner.validate_fixture_corpora(paths, {"shared_fixture_corpora": {}})

    def test_verifiers_with_fixture_git_init_choose_branch_explicitly(self) -> None:
        verifier_names = (
            "verify_java_feign_qualification.py",
            "verify_java_kafka_qualification.py",
            "verify_java_persistence_qualification.py",
        )
        for name in verifier_names:
            source = (runner.TOOLS / name).read_text()
            compact = source.replace(" ", "")
            self.assertTrue(
                "['git','init','-b','master']" in compact
                or '["git","init","-b","master"]' in compact,
                name,
            )

    def test_manifest_declares_machine_readable_output_contract(self) -> None:
        manifest = json.loads(runner.MANIFEST.read_text(encoding="utf-8"))
        self.assertEqual(manifest["output_contract"], runner.OUTPUT_CONTRACT)
        self.assertEqual(manifest["verifier_timeout_seconds"], runner.VERIFIER_TIMEOUT_SECONDS)
        self.assertEqual(manifest["release_status"], "unreleased")
        self.assertEqual(manifest["expected_count"], 46)
        self.assertEqual(manifest["expected_checks"], 731)
        self.assertEqual(manifest["full_unittest_count"], 478)
        root = runner.ROOT
        qualifier_baseline = (
            f'{manifest["expected_count"]}/{manifest["expected_count"]} qualifiers'
        )
        check_baseline = (
            f'{manifest["expected_checks"]}/{manifest["expected_checks"]} checks'
        )
        unittest_baseline = (
            f'{manifest["full_unittest_count"]}/{manifest["full_unittest_count"]} tests'
        )
        for document in ("README.md", "RELEASE_EVIDENCE.md", "CHANGES.md"):
            text = (root / document).read_text(encoding="utf-8")
            self.assertIn(qualifier_baseline, text, document)
            self.assertIn(check_baseline, text, document)
            self.assertIn(unittest_baseline, text, document)
            self.assertIn("unreleased", text.lower(), document)

    def test_every_manifest_verifier_emits_valid_contract(self) -> None:
        paths = runner.verifier_paths()
        manifest = runner.validate_manifest(paths)
        results, failures = runner.run_all(paths)
        self.assertEqual(failures, 0, results)
        runner.validate_result_baseline(results, manifest)
        self.assertEqual(len(results), manifest["expected_count"])
        self.assertEqual(sum(result["checks_total"] for result in results), manifest["expected_checks"])
        self.assertTrue(all(result["checks_passed"] == result["checks_total"] for result in results))

    def test_successful_check_count_drift_fails_closed(self) -> None:
        results = [{
            "name": "demo",
            "passed": True,
            "returncode": 0,
            "checks_passed": 2,
            "checks_total": 2,
        }]
        with self.assertRaisesRegex(ValueError, "expected=3, actual=2"):
            runner.validate_result_baseline(results, {"expected_checks": 3})

    def test_failed_verifier_preserves_primary_failure_over_baseline_check(self) -> None:
        results = [{"name": "demo", "passed": False, "returncode": 1}]
        runner.validate_result_baseline(results, {"expected_checks": 3})

    def test_list_prints_names_without_running_verifiers(self) -> None:
        paths = [Path("verify_java_a_qualification.py"), Path("verify_java_b_qualification.py")]
        output = io.StringIO()
        with (
            mock.patch.object(runner, "verifier_paths", return_value=paths),
            mock.patch.object(runner, "run_all") as run_all,
            mock.patch.object(sys, "argv", [str(RUNNER_PATH), "--list"]),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(runner.main(), 0)
        run_all.assert_not_called()
        self.assertEqual(output.getvalue(), "verify_java_a_qualification.py\nverify_java_b_qualification.py\n")

    def test_success_summary_includes_aggregate_and_check_counts(self) -> None:
        completed = subprocess.CompletedProcess(
            [],
            0,
            '{"checks":{"a":true,"b":true,"c":true},"passed":3,"total":3}\n',
            "hint: Using 'master' as the name for the initial branch.\n",
        )
        with mock.patch.object(runner.subprocess, "run", return_value=completed):
            results, failures = runner.run_all([Path("verify_java_demo_qualification.py")])
        self.assertEqual(failures, 0)
        self.assertEqual(results, [{
            "name": "demo",
            "passed": True,
            "returncode": 0,
            "checks_passed": 3,
            "checks_total": 3,
        }])
        self.assertNotIn("stderr", results[0])

    def test_opt_in_timings_record_each_verifier_duration(self) -> None:
        completed = subprocess.CompletedProcess(
            [], 0, '{"checks":{"a":true},"passed":1,"total":1}\n', ""
        )
        with (
            mock.patch.object(runner.subprocess, "run", return_value=completed),
            mock.patch.object(runner.time, "perf_counter_ns", side_effect=[1_000_000, 13_345_678]),
        ):
            results, failures = runner.run_all(
                [Path("verify_java_demo_qualification.py")], include_timings=True
            )
        self.assertEqual(failures, 0)
        self.assertEqual(results[0]["duration_ms"], 12)

    def test_failure_preserves_trimmed_stdout_and_stderr(self) -> None:
        completed = subprocess.CompletedProcess([], 7, " details on stdout \n", " failure details \n")
        with mock.patch.object(runner.subprocess, "run", return_value=completed):
            results, failures = runner.run_all([Path("verify_java_bad_qualification.py")])
        self.assertEqual(failures, 1)
        self.assertEqual(results[0]["stdout"], "details on stdout")
        self.assertEqual(results[0]["stderr"], "failure details")
        self.assertEqual(results[0]["returncode"], 7)

    def test_non_json_success_output_violates_contract(self) -> None:
        completed = subprocess.CompletedProcess([], 0, "legacy verifier: PASS\n", "")
        with mock.patch.object(runner.subprocess, "run", return_value=completed):
            results, failures = runner.run_all([Path("verify_java_legacy_qualification.py")])
        self.assertEqual(failures, 1)
        self.assertFalse(results[0]["passed"])
        self.assertIn("not one JSON object", results[0]["contract_error"])

    def test_mismatched_check_counts_violate_contract(self) -> None:
        completed = subprocess.CompletedProcess(
            [], 0, '{"checks":{"a":true,"b":false},"passed":2,"total":2}\n', ""
        )
        with mock.patch.object(runner.subprocess, "run", return_value=completed):
            results, failures = runner.run_all([Path("verify_java_bad_counts_qualification.py")])
        self.assertEqual(failures, 1)
        self.assertIn("counts do not match checks", results[0]["contract_error"])

    def test_zero_exit_with_failed_checks_violates_contract(self) -> None:
        completed = subprocess.CompletedProcess(
            [], 0, '{"checks":{"a":true,"b":false},"passed":1,"total":2}\n', ""
        )
        with mock.patch.object(runner.subprocess, "run", return_value=completed):
            results, failures = runner.run_all([Path("verify_java_bad_exit_qualification.py")])
        self.assertEqual(failures, 1)
        self.assertEqual(results[0]["contract_error"], "verifier exited zero with failed checks")

    def test_timeout_is_a_deterministic_failure(self) -> None:
        expired = subprocess.TimeoutExpired([], runner.VERIFIER_TIMEOUT_SECONDS, output=" partial \n", stderr=b" stuck \n")
        with mock.patch.object(runner.subprocess, "run", side_effect=expired) as run:
            results, failures = runner.run_all([Path("verify_java_hung_qualification.py")])
        self.assertEqual(failures, 1)
        self.assertEqual(results, [{
            "name": "hung",
            "passed": False,
            "returncode": None,
            "contract_error": f"verifier timed out after {runner.VERIFIER_TIMEOUT_SECONDS} seconds",
            "stdout": "partial",
            "stderr": "stuck",
        }])
        self.assertEqual(run.call_args.kwargs["timeout"], runner.VERIFIER_TIMEOUT_SECONDS)

    def test_opt_in_timings_record_timeout_duration(self) -> None:
        expired = subprocess.TimeoutExpired([], runner.VERIFIER_TIMEOUT_SECONDS)
        with (
            mock.patch.object(runner.subprocess, "run", side_effect=expired),
            mock.patch.object(runner.time, "perf_counter_ns", side_effect=[2_000_000, 23_000_000]),
        ):
            results, failures = runner.run_all(
                [Path("verify_java_hung_qualification.py")], include_timings=True
            )
        self.assertEqual(failures, 1)
        self.assertEqual(results[0]["duration_ms"], 21)

    def test_main_prints_machine_readable_success_summary(self) -> None:
        result = {"name": "demo", "passed": True, "returncode": 0}
        output = io.StringIO()
        with (
            mock.patch.object(runner, "verifier_paths", return_value=[Path("demo.py")]),
            mock.patch.object(runner, "run_all", return_value=([result], 0)),
            mock.patch.object(sys, "argv", [str(RUNNER_PATH)]),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(runner.main(), 0)
        self.assertEqual(json.loads(output.getvalue()), {
            "failed": 0,
            "passed": 1,
            "results": [result],
            "total": 1,
        })

    def test_main_timings_are_opt_in_and_aggregated(self) -> None:
        results = [
            {"name": "a", "passed": True, "returncode": 0, "duration_ms": 7},
            {"name": "b", "passed": True, "returncode": 0, "duration_ms": 11},
        ]
        output = io.StringIO()
        with (
            mock.patch.object(runner, "verifier_paths", return_value=[Path("a.py"), Path("b.py")]),
            mock.patch.object(runner, "run_all", return_value=(results, 0)) as run_all,
            mock.patch.object(sys, "argv", [str(RUNNER_PATH), "--timings"]),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(runner.main(), 0)
        run_all.assert_called_once_with([Path("a.py"), Path("b.py")], include_timings=True)
        self.assertEqual(json.loads(output.getvalue())["duration_ms"], 18)

    def test_main_rejects_successful_check_count_drift(self) -> None:
        result = {
            "name": "demo",
            "passed": True,
            "returncode": 0,
            "checks_passed": 2,
            "checks_total": 2,
        }
        output = io.StringIO()
        with (
            mock.patch.object(runner, "verifier_paths", return_value=[runner.TOOLS / "demo.py"]),
            mock.patch.object(runner, "validate_manifest", return_value={"expected_checks": 3}),
            mock.patch.object(runner, "run_all", return_value=([result], 0)),
            mock.patch.object(sys, "argv", [str(RUNNER_PATH)]),
            contextlib.redirect_stdout(output),
        ):
            self.assertEqual(runner.main(), 2)
        self.assertEqual(json.loads(output.getvalue()), {
            "error": "Java qualification check baseline mismatch: expected=3, actual=2"
        })


if __name__ == "__main__":
    unittest.main()
