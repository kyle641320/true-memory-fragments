"""Falsification tests for the frozen M10 fixture/bound-memory chain."""

from __future__ import annotations

import json
import os
import shutil
import tempfile
import unittest
from dataclasses import asdict, replace
from pathlib import Path
from unittest.mock import patch

from bench.agent_ab.same_version_chain_v1 import m10_successor_fixture as fixture
from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.schema import Claim


def compiler_available() -> bool:
    if shutil.which("javac") is None:
        return False
    try:
        fixture.compiler_environment()
        return True
    except (OSError, fixture.PreflightInvariantError):
        return False


class FrozenFixtureTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="m10-fixture-test-")
        self.root = Path(self.temp.name)
        self.addCleanup(self.temp.cleanup)

    def test_default_maven_paths_relocate_before_probing_foreign_home(self) -> None:
        home = self.root / "local-user"
        raw = (fixture.GUAVA / "classpath.txt").read_text().strip().split(os.pathsep)
        expected = []
        for entry in raw:
            path = home / ".m2/repository" / entry.split("/.m2/repository/", 1)[1]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(b"only testing path resolution; inventory still verifies JAR bytes")
            expected.append(path.resolve())
        real_is_file = Path.is_file
        def deny_foreign_home(path: Path) -> bool:
            if str(path).startswith("/root/.m2/"):
                raise PermissionError("inaccessible historical developer home")
            return real_is_file(path)
        with patch.object(Path, "home", return_value=home), \
             patch.object(Path, "is_file", deny_foreign_home), \
             patch.dict(os.environ):
            os.environ.pop("TMF_M10_SUCCESSOR_CLASSPATH", None)
            resolved, _ = fixture._compiler_classpath()
        self.assertEqual(expected, resolved)

    def test_both_complete_eleven_file_states_match_static_spec(self) -> None:
        spec = fixture.load_fixture_spec()
        for phase in ("t0", "t1"):
            root = self.root / phase
            result = fixture.prepare_fixture(root, phase)
            self.assertEqual(11, len(result["file_sha256"]))
            self.assertEqual(spec["file_sha256"][phase], result["file_sha256"])
            self.assertFalse((root / ".git").exists())
        changed = [name for name in fixture.PKG_FILES
                   if spec["file_sha256"]["t0"][name] != spec["file_sha256"]["t1"][name]]
        self.assertEqual([fixture.FILE], changed)

    def test_exact_mutation_diff_is_preregistered_not_merely_rehashed(self) -> None:
        before = (fixture.source_base() / fixture.FILE).read_text()
        after = fixture.mutate_dispatcher(before)
        spec = fixture.load_fixture_spec()
        self.assertEqual(spec["mutation"]["unified_diff"], fixture.mutation_diff(before, after))
        self.assertEqual(spec["mutation"]["unified_diff_sha256"],
                         fixture.sha256_text(fixture.mutation_diff(before, after)))
        with self.assertRaises(fixture.PreflightInvariantError):
            fixture.mutate_dispatcher(before + "\n// unrelated drift\n")

    def test_unrelated_fixture_drift_and_added_file_are_rejected(self) -> None:
        fixture.prepare_fixture(self.root, "t0")
        other = self.root / "Subscriber.java"
        original = other.read_bytes()
        other.write_bytes(original + b"\n// drift\n")
        with self.assertRaisesRegex(fixture.PreflightInvariantError, "frozen bytes"):
            fixture.validate_fixture(self.root, "t0")
        other.write_bytes(original)
        (self.root / "unreviewed.java").write_text("class Other {}")
        with self.assertRaisesRegex(fixture.PreflightInvariantError, "allowlist"):
            fixture.validate_fixture(self.root, "t0")

    def test_nonempty_destination_is_preserved_and_symlink_is_refused(self) -> None:
        sentinel = self.root / "keep.txt"
        sentinel.write_text("keep")
        with self.assertRaises(fixture.PreflightInvariantError):
            fixture.prepare_fixture(self.root)
        self.assertEqual("keep", sentinel.read_text())
        destination = self.root / "source"
        fixture.prepare_fixture(destination)
        source = destination / fixture.FILE
        source.unlink()
        source.symlink_to(fixture.source_base() / fixture.FILE)
        with self.assertRaisesRegex(fixture.PreflightInvariantError, "symlinks"):
            fixture.fixture_hashes(destination)

    def test_semantic_memory_fact_is_checked_independently_from_hash_freshness(self) -> None:
        source = (fixture.source_base() / fixture.FILE).read_text()
        proof = fixture.verify_t0_boundary(source)
        memory = fixture.frozen_bound_memory()
        self.assertEqual(fixture.canonical_json(proof), memory.t0_fact_proof_json)
        self.assertEqual(proof["source_snapshot"], memory.payload["source_snapshot"])
        self.assertIn("not the final user-callback boundary", proof["scope"])
        for wrong in (
            source.replace("nextEvent.subscribers.next().dispatchEvent(nextEvent.event)",
                           "nextEvent.subscribers.next().dispatchEvent(event)"),
            fixture.mutate_dispatcher(source),
            source.replace("private static final class PerThreadQueuedDispatcher",
                           "private static final class OtherDispatcher"),
        ):
            with self.assertRaises(fixture.PreflightInvariantError):
                fixture.verify_t0_boundary(wrong)

    def test_complete_frozen_claim_is_replayable_through_production_freshness(self) -> None:
        memory = fixture.frozen_bound_memory()
        claim = Claim.from_dict(json.loads(memory.claim_json))
        for phase, expected in (("t0", True), ("t1", False)):
            root = self.root / phase
            fixture.prepare_fixture(root, phase)
            observed = check_freshness(GitRepo(root), claim)
            self.assertEqual(expected, observed.fresh)
        self.assertEqual(fixture.canonical_json(claim.to_dict()), memory.claim_json)

    def test_fresh_gate_admits_and_cannot_emit_a_stale_receipt(self) -> None:
        fixture.prepare_fixture(self.root, "t0")
        memory = fixture.frozen_bound_memory()
        gate = fixture.evaluate_bound_memory(self.root, memory)
        self.assertTrue(gate.fresh)
        self.assertEqual(memory.payload, gate.payload)
        self.assertIsNone(gate.receipt)
        self.assertEqual((), gate.stale_bindings)

    def test_stale_gate_withholds_exact_same_memory_based_on_actual_freshness(self) -> None:
        fixture.prepare_fixture(self.root, "t1")
        memory = fixture.frozen_bound_memory()
        gate = fixture.evaluate_bound_memory(self.root, asdict(memory))
        self.assertFalse(gate.fresh)
        self.assertIsNone(gate.payload)
        self.assertEqual("stale_payload_withheld", gate.receipt["status"])
        self.assertEqual((f"{fixture.FILE}:{fixture.TARGET_QUALNAME}: java_hash mismatch",), gate.stale_bindings)
        self.assertEqual(memory.memory_sha256, gate.memory_sha256)
        self.assertEqual(memory.claim_sha256, gate.claim_sha256)

    def test_changed_payload_binding_or_fact_proof_is_rejected_not_rehashed(self) -> None:
        fixture.prepare_fixture(self.root, "t0")
        memory = fixture.frozen_bound_memory()
        false_claim = json.loads(memory.claim_json)
        false_claim["bindings"][0]["fn_hash"] = "0" * 64
        changed_payload = memory.payload
        changed_payload["boundary_conclusion"] = "An unsupported claim"
        for changed in (
            replace(memory, claim_json=fixture.canonical_json(false_claim)),
            replace(memory, payload_json=fixture.canonical_json(changed_payload)),
            replace(memory, t0_fact_proof_json="{}"),
        ):
            with self.assertRaises(fixture.PreflightInvariantError):
                fixture.evaluate_bound_memory(self.root, changed)

    def test_unknown_validity_withholds_without_inventing_a_successful_check(self) -> None:
        fixture.prepare_fixture(self.root, "t0")
        with patch.object(fixture, "check_freshness", side_effect=RuntimeError("unavailable")):
            gate = fixture.evaluate_bound_memory(self.root, fixture.frozen_bound_memory())
        self.assertFalse(gate.fresh)
        self.assertIsNone(gate.payload)
        self.assertEqual("unknown_payload_withheld", gate.receipt["status"])
        self.assertEqual(("freshness unavailable: RuntimeError",), gate.stale_bindings)

    def test_preflight_rejects_non_dispatcher_drift_before_compiler(self) -> None:
        copied_base = self.root / "base"
        copied_base.mkdir()
        for name in fixture.PKG_FILES:
            shutil.copyfile(fixture.source_base() / name, copied_base / name)
        (copied_base / "Subscriber.java").write_text("class Broken {}")
        with patch.object(fixture, "source_base", return_value=copied_base), \
                patch.object(fixture, "compile_check") as compile_mock:
            with self.assertRaisesRegex(fixture.PreflightInvariantError, "frozen bytes"):
                fixture.run_freshness_preflight(self.root / "fixture")
        compile_mock.assert_not_called()


@unittest.skipUnless(compiler_available(), "offline javac and locked classpath are required")
class ProductionPreflightTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.preflight = fixture.run_freshness_preflight()

    def test_real_production_fresh_mutate_stale_chain_and_control(self) -> None:
        p = self.preflight
        self.assertEqual({"fresh": True, "stale_bindings": []}, p.t0)
        self.assertEqual({"fresh": True, "stale_bindings": []}, p.control_t0)
        self.assertEqual(p.control_t0, p.control_t1)
        self.assertEqual({"fresh": False, "stale_bindings": [
            f"{fixture.FILE}:{fixture.TARGET_QUALNAME}: java_hash mismatch"]}, p.t1)
        self.assertTrue(p.compile_t0["ok"])
        self.assertTrue(p.compile_t1["ok"])
        self.assertTrue(all(fixture.validate_preflight(p).values()))

    def test_repeated_independent_preflights_have_identical_complete_artifacts(self) -> None:
        other = fixture.run_freshness_preflight()
        self.assertEqual(asdict(self.preflight), asdict(other))
        serialized = fixture.canonical_json(asdict(other))
        self.assertNotIn("/tmp/", serialized)
        self.assertIn("claim_json", serialized)
        self.assertIn("control_claim_json", serialized)
        self.assertEqual(11, len(other.files_t0))
        self.assertEqual(11, len(other.files_t1))

    def test_modified_preflight_or_forged_gate_cannot_be_sealed(self) -> None:
        p = self.preflight
        files = dict(p.files_t1)
        files["Subscriber.java"] = "0" * 64
        gate_t0 = dict(p.gate_t0)
        gate_t0["receipt"] = {"status": "stale_payload_withheld"}
        for changed in (
            replace(p, files_t1=files),
            replace(p, control_claim_json="{}"),
            replace(p, gate_t0=gate_t0),
            replace(p, gate_t1=p.gate_t0),
            replace(p, mutation_diff=p.mutation_diff + "extra change"),
            replace(p, compile_t1={"ok": False, "exit": 1}),
            replace(p, t1={"fresh": False, "stale_bindings": ["other reason"]}),
        ):
            with self.assertRaises(fixture.PreflightInvariantError):
                fixture.validate_preflight(changed)

    def test_actual_compiler_jars_are_pinned_and_no_temporary_paths_are_recorded(self) -> None:
        info = fixture.compiler_environment()
        self.assertEqual(fixture.load_fixture_spec()["compiler_classpath_jars"], info["classpath_jars"])
        self.assertRegex(info["javac_version"], r"^javac \d")
        self.assertRegex(info["javac_binary_sha256"], r"^[0-9a-f]{64}$")
        self.assertNotIn("/tmp/", fixture.canonical_json(info))
        self.assertEqual("bench/agent_ab/guava_cognitive_v1/classpath.txt", info["classpath_source"])

    def test_explicit_classpath_override_is_checked_not_blindly_trusted(self) -> None:
        entries, _ = fixture._compiler_classpath()
        with patch.dict(os.environ, {"TMF_M10_SUCCESSOR_CLASSPATH": os.pathsep.join(map(str, entries))}):
            self.assertEqual(self.preflight.compiler["classpath_jars"],
                             fixture.compiler_environment()["classpath_jars"])
        with tempfile.TemporaryDirectory(prefix="m10-jar-test-") as tmp:
            wrong = Path(tmp) / entries[0].name
            wrong.write_bytes(b"different bytes")
            with patch.dict(os.environ, {"TMF_M10_SUCCESSOR_CLASSPATH": os.pathsep.join(map(str, [wrong, *entries[1:]]))}):
                with self.assertRaisesRegex(fixture.PreflightInvariantError, "frozen jar"):
                    fixture.compiler_environment()

    def test_compiler_environment_injection_is_ignored_and_runtime_is_sealed(self) -> None:
        original = fixture.compiler_environment()
        self.assertIn("lib/modules", original["jdk_runtime_files_sha256"])
        self.assertIn("release", original["jdk_runtime_files_sha256"])
        with tempfile.TemporaryDirectory(prefix="m10-compiler-env-") as directory:
            root = Path(directory)
            fixture.prepare_fixture(root)
            # Invalid flags would prevent even -version if inherited. No values
            # are logged or copied into the scientific artifact.
            with patch.dict(os.environ, {
                "JDK_JAVAC_OPTIONS": "--unrecognized-successor-test-option",
                "JAVA_TOOL_OPTIONS": "-XX:UnrecognizedSuccessorTestOption",
                "_JAVA_OPTIONS": "-XX:UnrecognizedSuccessorTestOption",
                "CLASSPATH": "/not-used", "LC_ALL": "not-a-locale", "TZ": "Other/Timezone",
            }):
                self.assertEqual(original, fixture.compiler_environment())
                self.assertTrue(fixture.compile_check(root)["ok"])

    def test_missing_modular_jdk_materials_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            fake = Path(directory) / "bin" / "javac"
            fake.parent.mkdir()
            fake.write_text("not an actual compiler")
            with patch.object(fixture.shutil, "which", return_value=str(fake)):
                with self.assertRaisesRegex(fixture.PreflightInvariantError, "complete modular"):
                    fixture.compiler_environment()

    def test_java_compilation_failure_is_reported_independently(self) -> None:
        with tempfile.TemporaryDirectory(prefix="m10-compile-test-") as tmp:
            root = Path(tmp)
            fixture.prepare_fixture(root)
            (root / fixture.FILE).write_text("not Java;")
            result = fixture.compile_check(root)
            self.assertFalse(result["ok"])
            self.assertNotEqual(0, result["exit"])
            self.assertNotIn(tmp, result["stderr"])
            self.assertNotIn("semantic_pass", result)


if __name__ == "__main__":
    unittest.main()
