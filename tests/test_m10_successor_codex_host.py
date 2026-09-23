from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from bench.agent_ab.same_version_chain_v1 import successor_codex_host as host


@unittest.skipUnless(os.name == "posix", "source inspection requires no-follow POSIX descriptors")
class SuccessorCodexHostTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name).resolve()
        self.openclaw = self.base / "openclaw"
        self.codex = self.base / "codex"
        self.openclaw.mkdir()
        self.codex.mkdir()

    def inspect(self):
        report = host.inspect_host(self.openclaw, self.codex)
        self.assertEqual("NOT_READY", report["verdict"])
        self.assertIs(False, report["live_allowed"])
        with self.assertRaises(host.HostNotReadyError):
            host.require_live_host(report)
        return report

    def make_unknown_sources(self):
        # Same names/versions are deliberately insufficient to recognize a host.
        # None of these inert test files claims to be the installed stock source.
        for component, relative_path, _ in host._SOURCE_PINS:
            root = self.openclaw if component == "openclaw" else self.codex
            target = root / relative_path
            target.parent.mkdir(parents=True, exist_ok=True)
            if relative_path == "package.json":
                package = {"name": "openclaw" if component == "openclaw" else "@openclaw/codex",
                           "version": "2026.9.2", "dependencies": {"@openai/codex": "0.153.4"}}
                target.write_text(json.dumps(package))
            else:
                target.write_text("unknown test source; never import or execute\n")

    def error_codes(self, report):
        return {item["code"] for item in report["source_errors"]}

    def test_missing_host_has_no_supported_or_live_claim(self):
        report = self.inspect()
        self.assertEqual("unknown_or_incomplete", report["host_recognition"])
        self.assertIn("source_missing", self.error_codes(report))
        self.assertEqual([], report["supported_surfaces"])
        self.assertEqual({}, report["evidence"])
        self.assertEqual([], report["sources"])

    def test_version_and_source_names_do_not_self_attest(self):
        self.make_unknown_sources()
        report = self.inspect()
        self.assertEqual("2026.9.2", report["versions"]["openclaw"])
        self.assertEqual("0.153.4", report["versions"]["codex_dependency_declared"])
        self.assertIsNone(report["versions"]["codex_binary_runtime"])
        self.assertEqual("unknown_or_incomplete", report["host_recognition"])
        self.assertIn("source_hash_mismatch", self.error_codes(report))
        self.assertEqual({}, report["evidence"])

    def test_report_is_deterministic_and_only_returns_selected_metadata(self):
        self.make_unknown_sources()
        (self.codex / "dist/run-attempt-BzthFQSM.js").write_text("CONFIDENTIAL_CANARY_NOT_FOR_REPORT")
        first, second = self.inspect(), self.inspect()
        self.assertEqual(first, second)
        self.assertNotIn("CONFIDENTIAL_CANARY", json.dumps(first))
        self.assertTrue(all(len(entry["sha256"]) == 64 for entry in first["sources"]))

    def test_never_reads_auth_config_or_executes_package(self):
        self.make_unknown_sources()
        for root in (self.openclaw, self.codex):
            for name in ("auth.json", "openclaw.json", "config.toml", ".env"):
                (root / name).write_text("PRIVATE_CANARY_MUST_NOT_READ")
        opened_leafs = []
        real_open = os.open

        def watched_open(path, flags, *args, **kwargs):
            if not flags & os.O_DIRECTORY:
                opened_leafs.append(path)
                self.assertNotIn(path, {"auth.json", "openclaw.json", "config.toml", ".env"})
            return real_open(path, flags, *args, **kwargs)

        with patch.object(host.os, "open", side_effect=watched_open), \
                patch("subprocess.Popen", side_effect=AssertionError("no process launch")), \
                patch("socket.socket", side_effect=AssertionError("no network")):
            report = self.inspect()
        self.assertEqual(len(host._SOURCE_PINS), len(opened_leafs))
        self.assertNotIn("PRIVATE_CANARY", json.dumps(report))
        self.assertTrue(all(value == 0 for value in report["inspection_activity"].values()))

    def test_rejects_relative_and_parent_traversal_roots_without_reads(self):
        for bad in (Path("relative"), self.base / "x/../openclaw", "not-a-Path", None):
            with self.subTest(root=bad), patch.object(host, "_read_source") as read:
                report = host.inspect_host(bad, bad)
                self.assertEqual("NOT_READY", report["verdict"])
                self.assertIn("invalid_root", self.error_codes(report))
                read.assert_not_called()

    def test_rejects_symlink_root_and_symlink_ancestor(self):
        self.make_unknown_sources()
        alias = self.base / "alias"
        alias.symlink_to(self.openclaw, target_is_directory=True)
        for root in (alias, alias / "dist"):
            with self.subTest(root=root):
                report = host.inspect_host(root, self.codex)
                self.assertIn("symlink_source", self.error_codes(report))
                self.assertFalse(any(item["component"] == "openclaw" for item in report["sources"]))

    def test_rejects_symlink_file_without_following_target(self):
        outside = self.base / "private"
        outside.write_text("PRIVATE_CANARY_MUST_NOT_READ")
        (self.openclaw / "package.json").symlink_to(outside)
        report = self.inspect()
        self.assertIn("symlink_source", self.error_codes(report))
        self.assertNotIn("PRIVATE_CANARY", json.dumps(report))
        self.assertFalse(any(item["component"] == "openclaw" and item["path"] == "package.json"
                             for item in report["sources"]))

    def test_rejects_symlink_intermediate_directory(self):
        other = self.base / "other"
        other.mkdir()
        (other / "run-attempt-BzthFQSM.js").write_text("never followed")
        (self.codex / "dist").symlink_to(other, target_is_directory=True)
        self.assertIn("symlink_source", self.error_codes(self.inspect()))

    def test_fifo_is_rejected_without_opening_it(self):
        target = self.openclaw / "package.json"
        os.mkfifo(target)
        real_open = os.open

        def refuse_fifo_open(path, flags, *args, **kwargs):
            if path == "package.json":
                raise AssertionError("FIFO must be rejected before open")
            return real_open(path, flags, *args, **kwargs)

        with patch.object(host.os, "open", side_effect=refuse_fifo_open):
            report = self.inspect()
        self.assertIn("not_regular_source", self.error_codes(report))

    def test_oversize_source_is_rejected_before_content_read(self):
        with (self.openclaw / "package.json").open("wb") as stream:
            stream.truncate(host._MAX_SOURCE_BYTES + 1)
        with patch.object(host.os, "read", side_effect=AssertionError("oversize content read")):
            report = self.inspect()
        self.assertIn("source_too_large", self.error_codes(report))

    def test_invalid_encoding_and_malformed_package_fail_closed(self):
        for data in (b"\xff", b"{broken", b"[]", b'{"name": "different-package"}'):
            with self.subTest(data=data):
                (self.openclaw / "package.json").write_bytes(data)
                report = self.inspect()
                self.assertEqual("unknown_or_incomplete", report["host_recognition"])
                self.assertIsNone(report["versions"]["openclaw"])

    def test_changed_during_read_is_rejected(self):
        target = self.openclaw / "package.json"
        target.write_bytes(b"{}")
        real_read = os.read
        changed = False

        def change_after_first_read(descriptor, count):
            nonlocal changed
            result = real_read(descriptor, count)
            if not changed:
                changed = True
                with target.open("ab") as stream:
                    stream.write(b"changed")
            return result

        with patch.object(host.os, "read", side_effect=change_after_first_read):
            report = self.inspect()
        self.assertIn("source_changed_during_read", self.error_codes(report))

    def test_forged_ready_never_unlocks_guard(self):
        for report in ({}, {"verdict": "READY", "live_allowed": True},
                       {"schema": host.SCHEMA, "verdict": "READY", "host_recognition": "observed_stock",
                        "live_allowed": True, "missing_capabilities": [], "attested": True}, None):
            with self.subTest(report=report), self.assertRaisesRegex(
                    host.HostNotReadyError, "source inspection is not live admission authority"):
                host.require_live_host(report)


if __name__ == "__main__":
    unittest.main()
