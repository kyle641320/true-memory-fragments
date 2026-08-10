from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "tools" / "verify_java_gradle_integration.py"
SPEC = importlib.util.spec_from_file_location("verify_java_gradle_integration", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
verifier = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(verifier)


class JavaGradleIntegrationVerifierTest(unittest.TestCase):
    def test_manifest_has_bounded_current_batch(self) -> None:
        self.assertEqual(
            verifier.fixture_names(),
            ["autowired", "resource", "inject", "singleton", "named", "post_construct", "pre_destroy"],
        )

    def test_manifest_keys_map_to_hyphenated_fixture_paths(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "fixtures/java-post-construct-heldout/gradle"
            project.mkdir(parents=True)
            (project / "settings.gradle").touch()
            (project / "build.gradle").touch()
            completed = subprocess.CompletedProcess([], 0, "BUILD SUCCESSFUL in 1s\n", "")
            with (
                mock.patch.object(verifier, "ROOT", root),
                mock.patch.object(verifier.subprocess, "run", return_value=completed) as run,
            ):
                result = verifier.run_build("post_construct", "/real/gradle", 17)
            self.assertTrue(result["passed"])
            self.assertEqual(run.call_args.kwargs["cwd"], project)

    def test_real_build_command_is_fixed_and_requires_success_marker(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "fixtures/java-demo-heldout/gradle"
            project.mkdir(parents=True)
            (project / "settings.gradle").touch()
            (project / "build.gradle").touch()
            completed = subprocess.CompletedProcess([], 0, "BUILD SUCCESSFUL in 1s\n", "")
            with (
                mock.patch.object(verifier, "ROOT", root),
                mock.patch.object(verifier.subprocess, "run", return_value=completed) as run,
            ):
                result = verifier.run_build("demo", "/real/gradle", 17)
            self.assertTrue(result["passed"])
            self.assertEqual(
                run.call_args.args[0],
                ["/real/gradle", "--no-daemon", "--max-workers=1", "--console=plain", "clean", "build"],
            )
            self.assertEqual(run.call_args.kwargs["cwd"], project)
            self.assertEqual(run.call_args.kwargs["timeout"], 17)

    def test_zero_exit_without_gradle_success_marker_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            project = root / "fixtures/java-demo-heldout/gradle"
            project.mkdir(parents=True)
            (project / "settings.gradle").touch()
            (project / "build.gradle").touch()
            completed = subprocess.CompletedProcess([], 0, "tasks listed only\n", "")
            with (
                mock.patch.object(verifier, "ROOT", root),
                mock.patch.object(verifier.subprocess, "run", return_value=completed),
            ):
                result = verifier.run_build("demo", "gradle", 17)
            self.assertFalse(result["passed"])
            self.assertIn("tasks listed only", result["output"])


if __name__ == "__main__":
    unittest.main()
