from __future__ import annotations

from contextlib import redirect_stdout
from copy import deepcopy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from tmf.cli import build_parser, main
from tmf.doctor import inspect_reflex, render_doctor_text, UNARMED_WARNING
from tmf.warm import warm_repo


ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / "integrations/reflex/hooks/pre_tool_use.py"
SELECTOR = ROOT / "integrations/reflex/scripts/claim_selection.py"
# Preserve the pre-fix file-selection path; this fixture is inspected, never run.
LEGACY_FUNCTION_ONLY_HOOK = '''
def check_file_freshness(repo_root, rel_path, state_root):
    from tmf.git import GitRepo
    from tmf.store import Store
    from tmf.freshness import check_freshness
    repo = GitRepo(repo_root)
    store = Store(state_root)
    claim_ids = set()
    for claim in store.iter_claims():
        if claim.scope != "function":
            continue
        for binding in claim.bindings:
            if binding.path == rel_path:
                claim_ids.add(claim.id)
                break
    if not claim_ids:
        return {"fresh": True, "stale_functions": [], "error": None}
    return [check_freshness(repo, store.get_claim(claim_id)) for claim_id in claim_ids]

def main():
    return check_file_freshness(".", "Sample.java", ".tmf")
'''
CAPABILITIES = "REFLEX_CAPABILITIES = {'schema_version': 'tmf.reflex.capabilities.v1', 'file_languages': ['python', 'java']}\n"


class ReflexDoctorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.repo = self.base / "project with spaces"
        self.repo.mkdir()
        self.fixture_home = self.base / "home"
        self.fixture_home.mkdir()
        self.patch_home = mock.patch("tmf.doctor.Path.home", return_value=self.fixture_home)
        self.patch_home.start()
        self.addCleanup(self.patch_home.stop)
        self.config = self.base / "custom-claude-config"
        self.patch_env = mock.patch.dict(os.environ, {
            "CLAUDE_CONFIG_DIR": str(self.config),
            "PYTHONDONTWRITEBYTECODE": "1",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        })
        self.patch_env.start()
        self.addCleanup(self.patch_env.stop)
        self.target = self.repo / "integrations/reflex/hooks/pre_tool_use.py"
        self.target.parent.mkdir(parents=True)
        shutil.copyfile(HOOK, self.target)
        self.selector = self.repo / "integrations/reflex/scripts/claim_selection.py"
        self.selector.parent.mkdir(parents=True)
        shutil.copyfile(SELECTOR, self.selector)
        self.paths = {
            "global": self.config / "settings.json",
            "project": self.repo / ".claude/settings.json",
            "local": self.repo / ".claude/settings.local.json",
        }
        self.settings = json.loads((ROOT / "integrations/reflex/examples/claude-settings.example.json").read_text())

    def write_settings(self, scope="project", settings=None):
        path = self.paths[scope]
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.settings if settings is None else settings), encoding="utf-8")
        return path

    def result(self):
        return inspect_reflex(self.repo)

    def codes(self, result=None):
        return {item["code"] for item in (result or self.result())["findings"]}

    def handler(self, settings=None):
        return (self.settings if settings is None else settings)["hooks"]["PreToolUse"][0]["hooks"][0]

    def assert_not_armed(self, code=None, status=None):
        result = self.result()
        self.assertFalse(result["armed"])
        self.assertFalse(result["runtime_verified"])
        self.assertEqual(result["warning"], UNARMED_WARNING)
        self.assertIn(UNARMED_WARNING, render_doctor_text(result))
        if code:
            self.assertIn(code, self.codes(result))
        if status:
            self.assertEqual(result["status"], status)
        return result

    def test_warmed_engine_without_registration_is_explicitly_unarmed(self):
        for command in (["git", "init", "-b", "master"],
                        ["git", "config", "user.email", "fixture@example.com"],
                        ["git", "config", "user.name", "fixture"]):
            subprocess.run(command, cwd=self.repo, check=True, capture_output=True)
        (self.repo / "sample.py").write_text("def sample():\n    return 1\n")
        subprocess.run(["git", "add", "sample.py"], cwd=self.repo, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "fixture"], cwd=self.repo, check=True, capture_output=True)
        warm_repo(self.repo)
        self.assertTrue((self.repo / ".tmf").is_dir())
        result = self.assert_not_armed("missing_coverage", "unarmed")
        self.assertEqual(len(result["checked_locations"]), 3)
        self.assertEqual({item["status"] for item in result["checked_locations"]}, {"missing"})

    def test_global_project_and_local_can_each_register(self):
        for scope in self.paths:
            with self.subTest(scope=scope):
                path = self.write_settings(scope)
                result = self.result()
                self.assertEqual(result["status"], "armed")
                self.assertTrue(result["armed"])
                self.assertFalse(result["runtime_verified"])
                self.assertEqual(result["matched_tools"], ["Read", "Edit", "Write"])
                path.unlink()

    def test_default_global_directory_when_config_dir_is_not_set(self):
        default = self.fixture_home / ".claude/settings.json"
        default.parent.mkdir()
        default.write_text(json.dumps(self.settings))
        with mock.patch.dict(os.environ, {"CLAUDE_CONFIG_DIR": ""}):
            result = self.result()
        self.assertTrue(result["armed"])
        self.assertEqual(result["checked_locations"][0]["path"], str(default))

    def test_config_dir_replaces_default_global_location(self):
        default = self.fixture_home / ".claude/settings.json"
        default.parent.mkdir()
        default.write_text(json.dumps(self.settings))
        self.assert_not_armed("missing_coverage", "unarmed")

    def test_hook_arrays_merge_and_disable_boolean_has_scope_precedence(self):
        global_settings = deepcopy(self.settings)
        global_settings["hooks"]["PreToolUse"][0]["matcher"] = "Read"
        global_settings["disableAllHooks"] = True
        self.write_settings("global", global_settings)
        project_settings = deepcopy(self.settings)
        project_settings["hooks"]["PreToolUse"][0]["matcher"] = "Edit|Write"
        project_settings["disableAllHooks"] = False
        self.write_settings("project", project_settings)
        self.assertTrue(self.result()["armed"])
        self.write_settings("local", {"disableAllHooks": True})
        self.assert_not_armed("hooks_disabled", "disabled")
        self.write_settings("local", {"disableAllHooks": False})
        self.assertTrue(self.result()["armed"])

    def test_invalid_settings_blocks_a_positive_registration(self):
        self.write_settings("project")
        for content in ('{"secret":"DO_NOT_PRINT",', '[]', '{"disableAllHooks": "false"}',
                        '{"hooks": {}, "timeout": NaN}',
                        '{"hooks": []}', '{"hooks": {"PreToolUse": {}}}',
                        '{"hooks": {"PreToolUse": [null]}}',
                        '{"hooks": {"PreToolUse": [{"hooks": [null]}]}}'):
            with self.subTest(content=content):
                path = self.paths["global"]
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(content)
                result = self.assert_not_armed(status="invalid")
                self.assertNotIn("DO_NOT_PRINT", json.dumps(result))

    def test_wrong_event_example_and_usage_rules_are_not_registration(self):
        self.settings["hooks"]["SessionStart"] = self.settings["hooks"].pop("PreToolUse")
        self.write_settings()
        (self.repo / "CLAUDE.md").write_text("Always run TMF freshness before editing.")
        shutil.copyfile(ROOT / "integrations/reflex/examples/claude-settings.example.json",
                        self.repo / "settings.example.json")
        self.assert_not_armed("wrong_event", "unarmed")

    def test_matcher_requires_all_standard_tools(self):
        group = self.settings["hooks"]["PreToolUse"][0]
        for matcher, expected in [("Bash", "wrong_matcher"), ("read|edit|write", "wrong_matcher"),
                                  ("ReadFile|EditFile|WriteFile", "wrong_matcher"),
                                  ("Edit|Write", "missing_coverage")]:
            with self.subTest(matcher=matcher):
                group["matcher"] = matcher
                self.write_settings()
                self.assert_not_armed(expected, "unarmed")

    def test_supported_matchers_and_omitted_matcher(self):
        group = self.settings["hooks"]["PreToolUse"][0]
        for matcher in ("Read|Edit|Write", "Read, Edit, Write", "^(Read|Edit|Write)$", "(?:Read|Edit|Write)", ".*", "*", ""):
            with self.subTest(matcher=matcher):
                group["matcher"] = matcher
                self.write_settings()
                self.assertTrue(self.result()["armed"])
        group.pop("matcher")
        self.write_settings()
        self.assertTrue(self.result()["armed"])

    def test_invalid_and_unsupported_matchers_do_not_pass(self):
        group = self.settings["hooks"]["PreToolUse"][0]
        for matcher, code in [("[", "invalid_matcher"), (None, "invalid_matcher"),
                              ("(?i)read|edit|write", "unsupported_matcher"),
                              (r"\w+", "unsupported_matcher")]:
            with self.subTest(matcher=matcher):
                group["matcher"] = matcher
                self.write_settings()
                self.assert_not_armed(code)

    def test_missing_or_unrelated_same_named_script_does_not_pass(self):
        self.write_settings()
        self.target.unlink()
        self.assert_not_armed("missing_script")
        self.target.write_text("print('not the TMF reflex')\n")
        self.assert_not_armed("unrecognized_script")
        self.target.write_text("def :\n")
        self.assert_not_armed("unreadable_script")

    def test_python_possessive_regex_is_not_a_javascript_matcher(self):
        group = self.settings["hooks"]["PreToolUse"][0]
        for matcher in (".*+", ".++", "(Read|Edit|Write)?+"):
            with self.subTest(matcher=matcher):
                group["matcher"] = matcher
                self.write_settings()
                self.assert_not_armed("unsupported_matcher")

    def test_echo_wrappers_inline_code_and_shell_programs_are_not_armed(self):
        commands = [
            'echo "pre_tool_use.py"',
            'printf "python3 pre_tool_use.py"',
            'python3 -c "print(\'pre_tool_use.py\')"',
            'bash -c "python3 pre_tool_use.py"',
            'false && python3 "$CLAUDE_PROJECT_DIR/integrations/reflex/hooks/pre_tool_use.py"',
            'python3 "$CLAUDE_PROJECT_DIR/integrations/reflex/hooks/pre_tool_use.py" || true',
            'python3 "$CLAUDE_PROJECT_DIR/integrations/reflex/hooks/pre_tool_use.py" </dev/null',
            'python3 "$CLAUDE_PROJECT_DIR/integrations/reflex/hooks/pre_tool_use.py" &',
            'python3 -- -u "$CLAUDE_PROJECT_DIR/integrations/reflex/hooks/pre_tool_use.py"',
            'python3 "$UNKNOWN_TMF_ROOT/integrations/reflex/hooks/pre_tool_use.py"',
            "python3 '$CLAUDE_PROJECT_DIR/integrations/reflex/hooks/pre_tool_use.py'",
            'python3 $CLAUDE_PROJECT_DIR/integrations/reflex/hooks/pre_tool_use.py',
            'python3 integrations/reflex/hooks/pre_tool_use.py',
        ]
        for command in commands:
            with self.subTest(command=command):
                self.handler()["command"] = command
                self.write_settings()
                self.assert_not_armed()

    def test_direct_python_absolute_and_exec_form_paths(self):
        handler = self.handler()
        for command in (f'"{sys.executable}" -u -B "{self.target}"',
                        'python3 "${CLAUDE_PROJECT_DIR}/integrations/reflex/hooks/pre_tool_use.py"'):
            with self.subTest(command=command):
                handler["command"] = command
                self.write_settings()
                self.assertTrue(self.result()["armed"])
        handler["command"] = sys.executable
        handler["args"] = ["${CLAUDE_PROJECT_DIR}/integrations/reflex/hooks/pre_tool_use.py"]
        self.write_settings()
        self.assertTrue(self.result()["armed"])
        handler["args"] = ["$CLAUDE_PROJECT_DIR/integrations/reflex/hooks/pre_tool_use.py"]
        self.write_settings()
        self.assert_not_armed("unsupported_command")

    def test_missing_interpreter_and_prompt_hooks_are_not_armed(self):
        self.handler()["command"] = f'"{self.base}/missing/bin/python3" "{self.target}"'
        self.write_settings()
        self.assert_not_armed("missing_interpreter")
        self.handler()["type"] = "prompt"
        self.handler()["prompt"] = "Please run pre_tool_use.py"
        self.write_settings()
        self.assert_not_armed("missing_coverage")

    def test_nonblocking_and_conditional_handlers_do_not_pass(self):
        handler = self.handler()
        for key, value, code in [("async", True, "background_hook"),
                                 ("asyncRewake", True, "background_hook"),
                                 ("if", "Edit(*.ts)", "conditional_hook"),
                                 ("enabled", False, "unsupported_toggle"),
                                 ("disabled", True, "unsupported_toggle"),
                                 ("timeout", 0, "invalid_timeout"),
                                 ("timeout", False, "invalid_timeout")]:
            with self.subTest(key=key):
                old = handler.get(key)
                handler[key] = value
                self.write_settings()
                self.assert_not_armed(code)
                if old is None:
                    handler.pop(key)
                else:
                    handler[key] = old

    def test_doctor_is_read_only_and_never_executes_configured_commands(self):
        marker = self.base / "should-not-exist"
        self.handler()["command"] = f'touch "{marker}"; echo pre_tool_use.py'
        self.settings["env"] = {"PRIVATE_TOKEN": "DO_NOT_PRINT"}
        self.write_settings()
        before = {path.relative_to(self.base): (path.read_bytes(), path.stat().st_mtime_ns)
                  for path in self.base.rglob("*") if path.is_file()}
        with mock.patch("subprocess.run", side_effect=AssertionError("doctor executed a process")):
            result = self.assert_not_armed("unsupported_command")
        after = {path.relative_to(self.base): (path.read_bytes(), path.stat().st_mtime_ns)
                 for path in self.base.rglob("*") if path.is_file()}
        self.assertEqual(before, after)
        self.assertFalse(marker.exists())
        self.assertNotIn("DO_NOT_PRINT", json.dumps(result))
        self.assertNotIn("touch", json.dumps(result))
        self.assertFalse((self.repo / ".tmf").exists())

    def test_cli_json_text_exit_codes_and_default_repo(self):
        self.assertEqual(build_parser().parse_args(["doctor"]).repo, ".")
        for armed in (False, True):
            if armed:
                self.write_settings()
            with self.subTest(armed=armed):
                output = io.StringIO()
                with redirect_stdout(output):
                    code = main(["doctor", "--repo", str(self.repo), "--json"])
                payload = json.loads(output.getvalue())
                self.assertEqual(code, 0 if armed else 1)
                self.assertEqual(payload["schema_version"], "tmf.doctor.v1")
                self.assertEqual(payload["armed"], armed)
                self.assertFalse(payload["runtime_verified"])
                output = io.StringIO()
                with redirect_stdout(output):
                    code = main(["doctor", "--repo", str(self.repo)])
                self.assertEqual(code, 0 if armed else 1)
                self.assertIn("Checked settings:", output.getvalue())
                if armed:
                    self.assertIn("runtime firing NOT verified", output.getvalue())
                else:
                    self.assertIn(UNARMED_WARNING, output.getvalue())

    def test_invalid_repo_is_reported_without_creating_it(self):
        missing = self.base / "missing-project"
        result = inspect_reflex(missing)
        self.assertEqual(result["status"], "invalid")
        self.assertFalse(missing.exists())

    def add_java_source(self, path="nested/project/src/Sample.java"):
        target = self.repo / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("class Sample { int value() { return 1; } }\n")
        return target

    def test_missing_external_helper_fails_even_without_checked_source_languages(self):
        external = self.base / "external-integration"
        shutil.move(str(self.repo / "integrations"), str(external))
        self.target = external / "reflex/hooks/pre_tool_use.py"
        self.handler()["command"] = f'"{sys.executable}" "{self.target}"'
        selector = external / "reflex/scripts/claim_selection.py"
        valid = self.base / "valid-integration"
        shutil.copytree(external, valid)
        self.write_settings()
        for other_source in (False, True):
            with self.subTest(other_source=other_source):
                if other_source:
                    (self.repo / "app.ts").write_text("export const value = 1;\n")
                self.assertTrue(self.result()["armed"])
                selector.unlink()
                result = self.assert_not_armed("unrecognized_java_selector", "unarmed")
                self.assertEqual(result["language_capability"]["source_scan"]["required_languages"], [])
                self.assertEqual(result["registered_tools"], ["Read", "Edit", "Write"])
                self.assertEqual(result["matched_tools"], [])
                # One broken registration must not mask another complete one.
                settings = deepcopy(self.settings)
                handler = deepcopy(self.handler())
                handler["command"] = f'"{sys.executable}" "{valid / "reflex/hooks/pre_tool_use.py"}"'
                settings["hooks"]["PreToolUse"][0]["hooks"].append(handler)
                self.write_settings(settings=settings)
                self.assertTrue(self.result()["armed"])
                self.write_settings()
                shutil.copyfile(valid / "reflex/scripts/claim_selection.py", selector)

    def test_registered_legacy_hook_is_not_armed_for_nested_java_repo(self):
        self.add_java_source()
        self.target.write_text(LEGACY_FUNCTION_ONLY_HOOK)
        self.write_settings()
        result = self.assert_not_armed("java_function_only_filter", "unarmed")
        self.assertIn("registration_found", self.codes(result))
        self.assertEqual(result["registered_tools"], ["Read", "Edit", "Write"])
        self.assertEqual(result["matched_tools"], [])
        self.assertEqual(result["language_capability"]["source_scan"]["required_languages"], ["java", "python"])
        output = io.StringIO()
        with redirect_stdout(output):
            code = main(["doctor", "--repo", str(self.repo), "--json"])
        self.assertEqual(code, 1)
        self.assertFalse(json.loads(output.getvalue())["armed"])

    def test_legacy_python_only_hook_retains_its_narrow_registration(self):
        self.target.write_text(LEGACY_FUNCTION_ONLY_HOOK)
        self.write_settings()
        result = self.result()
        self.assertTrue(result["armed"])
        self.assertFalse(result["behavior_verified"])
        self.assertEqual(result["language_capability"]["registrations"][0]["effective_languages"], ["python"])
        self.assertEqual(result["language_capability"]["source_scan"]["required_languages"], ["python"])

    def test_capability_marker_does_not_override_known_inert_java_filter(self):
        self.add_java_source()
        self.target.write_text(CAPABILITIES + LEGACY_FUNCTION_ONLY_HOOK)
        self.write_settings()
        result = self.assert_not_armed("java_function_only_filter")
        capability = result["language_capability"]["registrations"][0]
        self.assertEqual(capability["declared_languages"], ["java", "python"])
        self.assertEqual(capability["effective_languages"], ["python"])

    def test_marker_only_or_dead_entrypoints_do_not_establish_java_registration(self):
        self.add_java_source()
        self.write_settings()
        for source in (CAPABILITIES, CAPABILITIES + '''
from tmf.freshness import check_freshness
def main():
    return None
def check_file_freshness(*args):
    return {"fresh": True}
'''):
            with self.subTest(source=source):
                self.target.write_text(source)
                self.assert_not_armed("unrecognized_script")

    def test_current_java_hook_declares_coverage_without_claiming_runtime_proof(self):
        self.add_java_source()
        self.write_settings()
        before = {path: (path.read_bytes(), path.stat().st_mtime_ns)
                  for path in self.base.rglob("*") if path.is_file()}
        with mock.patch("subprocess.run", side_effect=AssertionError("doctor executed a process")):
            result = self.result()
        self.assertTrue(result["armed"])
        self.assertFalse(result["runtime_verified"])
        self.assertFalse(result["behavior_verified"])
        self.assertEqual(result["language_capability"]["matched_tools_by_language"], {
            "java": ["Read", "Edit", "Write"], "python": ["Read", "Edit", "Write"],
        })
        after = {path: (path.read_bytes(), path.stat().st_mtime_ns)
                 for path in self.base.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_missing_or_malformed_shared_selector_prevents_java_arming(self):
        self.add_java_source()
        self.write_settings()
        self.selector.unlink()
        self.assert_not_armed("unrecognized_java_selector")
        for text in ("def :\n", "# capability header without selection logic\n"):
            with self.subTest(text=text):
                self.selector.write_text(text)
                self.assert_not_armed("unrecognized_java_selector")

    def test_missing_imported_shared_selector_also_prevents_python_arming(self):
        self.write_settings()
        self.selector.unlink()
        result = self.assert_not_armed("unrecognized_java_selector")
        self.assertEqual(result["language_capability"]["source_scan"]["required_languages"], ["python"])
        self.assertEqual(result["matched_tools"], [])

    def test_malformed_and_nonliteral_capabilities_are_not_executed_or_trusted(self):
        self.add_java_source()
        self.write_settings()
        marker = self.base / "never-created"
        for declaration in (
            "REFLEX_CAPABILITIES = {'schema_version': 'unknown', 'file_languages': ['java']}\n",
            "REFLEX_CAPABILITIES = {'schema_version': 'tmf.reflex.capabilities.v1', 'file_languages': 'java'}\n",
            "REFLEX_CAPABILITIES = {'schema_version': 'tmf.reflex.capabilities.v1', 'file_languages': ['java', 'java']}\n",
            CAPABILITIES + CAPABILITIES,
            f"REFLEX_CAPABILITIES = __import__('pathlib').Path({str(marker)!r}).write_text('not allowed')\n",
        ):
            with self.subTest(declaration=declaration):
                self.target.write_text(declaration + LEGACY_FUNCTION_ONLY_HOOK)
                self.assert_not_armed("invalid_capabilities")
        self.assertFalse(marker.exists())

    def test_java_coverage_is_per_tool_not_the_union_of_incompatible_handlers(self):
        self.add_java_source()
        legacy = self.repo / "legacy/hooks/pre_tool_use.py"
        legacy.parent.mkdir(parents=True)
        legacy.write_text(LEGACY_FUNCTION_ONLY_HOOK)
        self.settings["hooks"]["PreToolUse"][0]["matcher"] = "Edit|Write"
        self.write_settings()
        legacy_settings = deepcopy(self.settings)
        legacy_settings["hooks"]["PreToolUse"][0]["matcher"] = "Read"
        self.handler(legacy_settings)["command"] = f'"{sys.executable}" "{legacy}"'
        self.write_settings("global", legacy_settings)
        result = self.assert_not_armed("missing_language_coverage")
        self.assertEqual(result["registered_tools"], ["Read", "Edit", "Write"])
        self.assertEqual(result["matched_tools"], ["Edit", "Write"])
        self.assertEqual(result["language_capability"]["matched_tools_by_language"]["java"], ["Edit", "Write"])
        self.settings["hooks"]["PreToolUse"][0]["matcher"] = "Read|Edit|Write"
        self.write_settings()
        self.assertTrue(self.result()["armed"])

    def test_other_source_languages_are_visible_but_not_claimed_as_supported(self):
        self.add_java_source()
        (self.repo / "integration.ts").write_text("export const value = 1;\n")
        self.write_settings()
        result = self.result()
        self.assertTrue(result["armed"])
        self.assertIn("other_languages_unverified", self.codes(result))
        self.assertEqual(result["language_capability"]["source_scan"]["other_source_languages"], ["typescript"])
        self.assertNotIn("typescript", result["language_capability"]["matched_tools_by_language"])

    def test_source_discovery_skips_declared_metadata_but_includes_nested_projects(self):
        self.add_java_source(".git/objects/NotSource.java")
        self.add_java_source(".venv/NotSource.java")
        self.write_settings()
        self.target.write_text(LEGACY_FUNCTION_ONLY_HOOK)
        self.assertTrue(self.result()["armed"])
        self.add_java_source(".nested/repository/src/RealSource.java")
        self.assert_not_armed("java_function_only_filter")

    def test_incomplete_source_discovery_never_arms(self):
        self.write_settings()
        with mock.patch("tmf.doctor.os.scandir", side_effect=PermissionError("DO_NOT_PRINT")):
            result = self.assert_not_armed("source_scan_unreadable", "unknown")
        self.assertNotIn("DO_NOT_PRINT", json.dumps(result))
        with mock.patch("tmf.doctor._MAX_SOURCE_ENTRIES", 1):
            self.assert_not_armed("source_scan_limit", "unknown")
        with mock.patch("tmf.doctor._MAX_SOURCE_DEPTH", 0):
            self.assert_not_armed("source_scan_limit", "unknown")

    def test_source_directory_symlinks_and_broken_links_are_inconclusive(self):
        self.write_settings()
        outside = self.base / "outside"
        outside.mkdir()
        (outside / "Hidden.java").write_text("class Hidden {}\n")
        link = self.repo / "linked-source"
        link.symlink_to(outside, target_is_directory=True)
        self.assert_not_armed("source_scan_symlink", "unknown")
        link.unlink()
        link.symlink_to(self.base / "missing")
        self.assert_not_armed("source_scan_unreadable", "unknown")


if __name__ == "__main__":
    unittest.main()
