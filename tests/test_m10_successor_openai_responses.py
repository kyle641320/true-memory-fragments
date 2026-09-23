from __future__ import annotations

import copy
import json
import unittest
from dataclasses import replace
from unittest.mock import patch

from bench.agent_ab.same_version_chain_v1 import successor_openai_responses as codec
from bench.agent_ab.same_version_chain_v1.m10_successor_protocol import ACTION_SCHEMAS


def initial_input():
    return [{"role": "system", "content": "Use the local native functions."},
            {"role": "user", "content": 'Current source: 中文 / "quoted" \\ escaped\nline 2'}]


def prepared(*, purpose="scientific"):
    return codec.prepare_request(initial_input(), copy.deepcopy(ACTION_SCHEMAS), purpose=purpose)


def response(request=None, *, name="list", arguments=None):
    request = request or prepared()
    generation = json.loads(request.generation_json)
    return {
        "object": "response", "id": "resp_offline_fixture", "model": codec.MODEL,
        "created_at": 1_790_000_000, "status": "completed", "error": None,
        "incomplete_details": None,
        **{key: copy.deepcopy(generation[key]) for key in (
            "reasoning", "text", "parallel_tool_calls", "tool_choice", "tools",
            "truncation", "background", "service_tier", "max_output_tokens")},
        # Official RESPONSE shape, not a copy of request-only prewarm.
        "prompt_cache_options": {"mode": "implicit", "ttl": "30m"},
        "output": [
            {"type": "reasoning", "id": "rs_offline", "summary": [],
             "encrypted_content": "opaque-offline-fixture-not-real-provider-state"},
            {"type": "message", "id": "msg_offline", "role": "assistant", "status": "completed",
             "phase": "commentary", "content": [{"type": "output_text", "text": "Inspecting source.", "annotations": []}]},
            {"type": "function_call", "id": "fc_offline", "name": name,
             "call_id": "call_offline", "arguments": codec.canonical(arguments or {}), "status": "completed"},
        ],
        "usage": {"input_tokens": 800, "output_tokens": 120, "total_tokens": 920,
                  "input_tokens_details": {"cached_tokens": 200, "cache_write_tokens": 100},
                  "output_tokens_details": {"reasoning_tokens": 100}},
    }


def encoded(value):
    return codec.canonical(value).encode("utf-8")


def inspect(value, request=None, **kwargs):
    return codec.inspect_response(encoded(value), request or prepared(), expected_input_tokens=800, **kwargs)


class OpenAIResponsesProfileTests(unittest.TestCase):
    def test_pure_profile_and_request_rendering_never_open_network_or_process(self):
        with patch("socket.socket", side_effect=AssertionError("no network")), \
             patch("subprocess.Popen", side_effect=AssertionError("no process")):
            request = prepared()
            codec.verify_prepared(request)
            observed = inspect(response(request), request)
        self.assertTrue(observed["ok"])
        config = codec.profile()
        self.assertEqual("unavailable", config["observability"]["immutable_deployment_revision"])
        self.assertEqual("unavailable", config["observability"]["tokenizer_material_revision"])
        self.assertEqual("unknown", config["count_pricing"])
        self.assertFalse(config["pilot_execution_authorized"])
        config["reasoning"]["effort"] = "max"
        self.assertEqual("medium", codec.profile()["reasoning"]["effort"])

    def test_count_and_generation_have_identical_full_scientific_projection(self):
        request = prepared()
        count, generation = json.loads(request.count_json), json.loads(request.generation_json)
        self.assertEqual(count, {key: generation[key] for key in codec.SCIENTIFIC_FIELDS})
        self.assertEqual(set(codec.GENERATION_ONLY_FIELDS), set(generation) - set(count))
        self.assertEqual(initial_input(), count["input"])
        self.assertEqual(7, len(count["tools"]))
        self.assertEqual("required", count["tool_choice"])
        self.assertEqual({"effort": "medium", "context": "all_turns", "mode": "standard"}, count["reasoning"])
        self.assertEqual("disabled", count["truncation"])
        self.assertEqual(4096, generation["max_output_tokens"])
        self.assertFalse(generation["stream"])
        self.assertFalse(generation["store"])
        self.assertFalse(generation["background"])
        self.assertNotIn("prompt_cache_key", generation)
        self.assertNotIn("previous_response_id", generation)
        self.assertNotIn("conversation", generation)
        self.assertNotIn("messages", generation)
        self.assertNotIn("max_completion_tokens", generation)

    def test_native_schema_is_lossless_except_action_discriminator(self):
        tools = codec.native_tools(ACTION_SCHEMAS)
        self.assertEqual(sorted(ACTION_SCHEMAS), [tool["name"] for tool in tools])
        for tool in tools:
            self.assertEqual("function", tool["type"])
            self.assertIs(tool["strict"], False)
            source = copy.deepcopy(ACTION_SCHEMAS[tool["name"]])
            self.assertEqual(source.pop("description"), tool["description"])
            del source["properties"]["action"]
            source["required"].remove("action")
            self.assertEqual(source, tool["parameters"])
        search = next(tool for tool in tools if tool["name"] == "search")
        self.assertIn("path", search["parameters"]["properties"])
        self.assertNotIn("path", search["parameters"]["required"])

    def test_action_schema_drift_and_additional_tools_rejected(self):
        schemas = copy.deepcopy(ACTION_SCHEMAS)
        schemas["search"]["description"] += " Arm-specific instruction."
        with self.assertRaises(codec.ResponsesContractError):
            codec.native_tools(schemas)
        schemas = copy.deepcopy(ACTION_SCHEMAS)
        schemas["web_search"] = {}
        with self.assertRaises(codec.ResponsesContractError):
            codec.native_tools(schemas)

    def test_imported_mutable_schema_cannot_redefine_profile_after_import(self):
        schemas = copy.deepcopy(ACTION_SCHEMAS)
        before = codec.profile()["action_schemas_sha256"]
        with patch.dict(ACTION_SCHEMAS["list"], description="Mutated common module"):
            with self.assertRaises(codec.ResponsesContractError):
                codec.native_tools(ACTION_SCHEMAS)
            self.assertEqual(7, len(codec.native_tools(schemas)))
            self.assertEqual(before, codec.profile()["action_schemas_sha256"])

    def test_post_preparation_mutation_does_not_change_snapshot(self):
        items = initial_input()
        schemas = copy.deepcopy(ACTION_SCHEMAS)
        request = codec.prepare_request(items, schemas)
        items[1]["content"] = "MUTATED"
        schemas["list"]["description"] = "MUTATED"
        codec.verify_prepared(request)
        self.assertNotIn("MUTATED", request.generation_json)

    def test_re_signed_forbidden_configuration_is_not_admitted(self):
        original = prepared()
        mutations = (("store", True), ("stream", True), ("model", "another-model"),
                     ("max_output_tokens", 2048), ("previous_response_id", "resp_hidden"),
                     ("prompt_cache_key", "arm_1"), ("reasoning", {"effort": "max"}),
                     ("truncation", "auto"), ("tools", [{"type": "web_search"}]))
        for key, value in mutations:
            with self.subTest(field=key):
                body = json.loads(original.generation_json)
                body[key] = value
                generation_json = codec.canonical(body)
                count = {key: body[key] for key in codec.SCIENTIFIC_FIELDS}
                count_json = codec.canonical(count)
                tampered = replace(original, generation_json=generation_json,
                                   generation_sha256=codec.digest(generation_json), count_json=count_json,
                                   scientific_sha256=codec.digest(count_json))
                with self.assertRaises(codec.ResponsesContractError):
                    codec.verify_prepared(tampered)

    def test_count_generation_difference_noncanonical_or_forged_hash_rejected(self):
        original = prepared()
        count = json.loads(original.count_json)
        count["input"][1]["content"] += " silent difference"
        count_json = codec.canonical(count)
        cases = [replace(original, count_json=count_json, scientific_sha256=codec.digest(count_json)),
                 replace(original, generation_sha256="0" * 64),
                 replace(original, generation_json=" " + original.generation_json,
                         generation_sha256=codec.digest(" " + original.generation_json)),
                 replace(original, max_output_tokens=True)]
        for request in cases:
            with self.subTest(request=request.scientific_sha256), self.assertRaises(codec.ResponsesContractError):
                codec.verify_prepared(request)

    def test_non_json_numbers_and_surrogates_do_not_get_repaired(self):
        for value in (float("nan"), float("inf"), {1: "key"}, ("tuple",), "\ud800"):
            with self.subTest(value=repr(value)), self.assertRaises(codec.ResponsesContractError):
                codec.canonical(value)
        self.assertEqual('{"unicode":"中文"}', codec.canonical({"unicode": "中文"}))

    def test_payload_byte_limit_is_utf8_not_character_count(self):
        items = initial_input()
        items[-1]["content"] = "中" * 40_000
        with self.assertRaisesRegex(codec.ResponsesContractError, "request_byte_limit"):
            codec.prepare_request(items, ACTION_SCHEMAS)

    def test_hidden_or_remote_input_and_explicit_cache_breakpoints_rejected(self):
        items = initial_input()
        cases = [
            {"role": "user", "content": [{"type": "input_image", "image_url": "https://example.invalid/private"}]},
            {"role": "user", "content": [{"type": "input_text", "text": "x", "prompt_cache_breakpoint": {"mode": "explicit"}}]},
            {"type": "item_reference", "id": "resp_hidden"},
            {"role": "tool", "content": "legacy text tool response"},
        ]
        for item in cases:
            with self.subTest(item=item), self.assertRaises(codec.ResponsesContractError):
                codec.prepare_request(items + [item], ACTION_SCHEMAS)

    def test_official_count_receipt_strict_parse_and_no_extra_exact_assertions(self):
        self.assertEqual(800, codec.parse_count(b'{"object":"response.input_tokens","input_tokens":800}'))
        invalid = [b'{"object":"response.input_tokens","input_tokens":true}',
                   b'{"object":"response.input_tokens","input_tokens":-1}',
                   b'{"object":"response.input_tokens","input_tokens":1.0}',
                   b'{"object":"response.input_tokens","input_tokens":NaN}',
                   b'{"object":"response.input_tokens","input_tokens":1,"input_tokens":2}',
                   b'{"object":"response.input_tokens","input_tokens":1,"exact":true}',
                   b'{"object":"chat.completion","input_tokens":1}', b'[]', b'\xff']
        for raw in invalid:
            with self.subTest(raw=raw), self.assertRaises(codec.ResponsesContractError):
                codec.parse_count(raw)

    def test_request_purpose_and_probe_configuration_are_fixed(self):
        request = prepared(purpose="output_cap")
        generation = json.loads(request.generation_json)
        self.assertEqual(64, request.max_output_tokens)
        self.assertEqual([], generation["tools"])
        self.assertEqual("none", generation["tool_choice"])
        self.assertEqual(json.loads(prepared().generation_json)["reasoning"], generation["reasoning"])
        with self.assertRaises(codec.ResponsesContractError):
            prepared(purpose="arm_1")


class OpenAIResponsesInspectionTests(unittest.TestCase):
    def test_official_cache_response_shape_does_not_require_request_only_prewarm(self):
        for extra in ({}, {"comparison_response_id": None}):
            body = response()
            body["prompt_cache_options"] = {"mode": "implicit", "ttl": "30m", **extra}
            observed = inspect(body)
            self.assertTrue(observed["ok"], observed["errors"])
            self.assertEqual(body, observed["response"])
            self.assertNotIn("prewarm", observed["response"]["prompt_cache_options"])
        self.assertIs(json.loads(prepared().generation_json)["prompt_cache_options"]["prewarm"], False)

    def test_cache_response_drift_or_unknown_schema_fails_without_losing_usage(self):
        for options in (None, {}, {"mode": "explicit", "ttl": "30m"},
                        {"mode": "implicit", "ttl": "24h"},
                        {"mode": "implicit", "ttl": "30m", "comparison_response_id": "hidden"},
                        {"mode": "implicit", "ttl": "30m", "prewarm": False}):
            with self.subTest(options=options):
                body = response()
                body["prompt_cache_options"] = options
                observed = inspect(body)
                self.assertFalse(observed["ok"])
                self.assertIn("response_prompt_cache_options_mismatch", observed["errors"])
                self.assertEqual(920, observed["usage"]["total_tokens"])
                self.assertEqual(body, observed["response"])

    def test_native_function_actions_are_validated_and_usage_not_double_counted(self):
        actions = [
            ("list", {}), ("search", {"query": "dispatch"}),
            ("read_range", {"path": "Dispatcher.java", "start": 1, "end": 2}),
            ("read_symbol", {"path": "Dispatcher.java", "symbol": "Dispatcher"}),
            ("edit", {"path": "Dispatcher.java", "old": "before", "new": "after"}),
            ("compile", {}), ("final", {"answer": "Done", "files": ["Dispatcher.java"]}),
        ]
        for name, arguments in actions:
            with self.subTest(name=name):
                result = inspect(response(name=name, arguments=arguments))
                self.assertTrue(result["ok"], result["errors"])
                self.assertEqual({"action": name, **arguments}, result["action"])
                self.assertEqual({"input_tokens": 800, "output_tokens": 120, "total_tokens": 920}, result["usage"])
                self.assertEqual(100, result["usage_details"]["reasoning_tokens"])

    def test_valid_usage_preserved_on_identity_configuration_and_status_errors(self):
        mutations = [
            ("id", ""), ("model", "wrong-model"), ("object", "chat.completion"),
            ("created_at", True), ("status", "queued"), ("service_tier", "priority"),
            ("max_output_tokens", True), ("reasoning", {"effort": "max"}),
            ("tool_choice", "auto"), ("tools", []), ("parallel_tool_calls", 0),
            ("background", True), ("truncation", "auto"), ("store", True),
            ("conversation", {"id": "hidden"}), ("previous_response_id", "resp_hidden"),
            ("prompt_cache_key", "arm_1"), ("error", {"code": "server_error"}),
        ]
        for field, value in mutations:
            with self.subTest(field=field):
                body = response()
                body[field] = value
                result = inspect(body)
                self.assertFalse(result["ok"])
                self.assertIsNone(result["action"])
                self.assertEqual(920, result["usage"]["total_tokens"])
                self.assertEqual(body, result["response"])

    def test_raw_response_untouched_and_digest_tracks_original_formatting(self):
        body = response()
        raw = json.dumps(body, ensure_ascii=False, indent=2).encode("utf-8")
        observed = codec.inspect_response(raw, prepared(), expected_input_tokens=800)
        self.assertTrue(observed["ok"])
        self.assertEqual(codec.digest(raw), observed["response_sha256"])
        self.assertNotEqual(observed["response_sha256"], observed["response_canonical_sha256"])
        self.assertEqual(body, observed["response"])

    def test_missing_cache_write_details_are_unknown_not_zero(self):
        body = response()
        del body["usage"]["input_tokens_details"]["cache_write_tokens"]
        observed = inspect(body)
        self.assertFalse(observed["ok"])
        self.assertIsNone(observed["usage_details"]["cache_write_tokens"])
        self.assertEqual(920, observed["usage"]["total_tokens"])
        self.assertNotIn("cache_write_tokens", observed["response"]["usage"]["input_tokens_details"])

    def test_detail_contradictions_fail_without_losing_valid_aggregates(self):
        for path, value in (("cached_tokens", 801), ("cache_write_tokens", 601), ("reasoning_tokens", 121),
                            ("cached_tokens", True), ("cache_write_tokens", -1), ("reasoning_tokens", 1.0)):
            body = response()
            field = "output_tokens_details" if path == "reasoning_tokens" else "input_tokens_details"
            body["usage"][field][path] = value
            with self.subTest(path=path, value=value):
                result = inspect(body)
                self.assertFalse(result["ok"])
                self.assertEqual(920, result["usage"]["total_tokens"])

    def test_unknown_usage_semantics_halt_with_raw_evidence(self):
        body = response()
        body["usage"]["output_tokens_details"]["new_provider_token_class"] = 10
        result = inspect(body)
        self.assertFalse(result["ok"])
        self.assertIn("unknown_usage_detail_semantics", result["errors"])
        self.assertEqual(920, result["usage"]["total_tokens"])

    def test_invalid_or_missing_aggregate_usage_is_not_repaired(self):
        for field, value in (("total_tokens", 921), ("input_tokens", True), ("output_tokens", -1)):
            body = response()
            body["usage"][field] = value
            with self.subTest(field=field):
                result = inspect(body)
                self.assertFalse(result["ok"])
                self.assertIsNone(result["usage"])
                self.assertEqual(value, result["response"]["usage"][field])
        body = response()
        del body["usage"]
        self.assertIsNone(inspect(body)["usage"])

    def test_count_mismatch_and_output_overrun_preserve_actual_usage(self):
        body = response()
        body["usage"]["input_tokens"] = 801
        body["usage"]["total_tokens"] = 921
        result = inspect(body)
        self.assertIn("count_usage_mismatch", result["errors"])
        self.assertEqual(801, result["usage"]["input_tokens"])
        body = response()
        body["usage"]["output_tokens"] = 4097
        body["usage"]["total_tokens"] = 4897
        result = inspect(body)
        self.assertIn("output_usage_exceeds_cap", result["errors"])
        self.assertEqual(4097, result["usage"]["output_tokens"])

    def test_duplicate_and_nonfinite_json_fail_closed(self):
        for raw in (b'{"usage":{},"usage":{}}', b'{"value":NaN}', b'[]', b'\xff', b' ' * 262145):
            with self.subTest(raw=raw[:50]):
                result = codec.inspect_response(raw, prepared(), expected_input_tokens=800)
                self.assertFalse(result["ok"])
                self.assertIsNone(result["action"])
                self.assertIsNone(result["usage"])

    def test_multiple_calls_refusal_hosted_tools_and_text_json_are_not_actions(self):
        cases = []
        body = response()
        body["output"].append({"type": "function_call", "name": "compile", "arguments": "{}", "call_id": "second"})
        cases.append(body)
        body = response()
        body["output"][1]["content"] = [{"type": "refusal", "refusal": "no"}]
        cases.append(body)
        body = response()
        body["output"].append({"type": "web_search_call", "id": "ws_hidden", "status": "completed"})
        cases.append(body)
        body = response()
        body["output"].pop()
        body["output"][1]["content"][0]["text"] = '{"action":"compile"}'
        cases.append(body)
        for body in cases:
            with self.subTest(body=body["output"]):
                result = inspect(body)
                self.assertFalse(result["ok"])
                self.assertIsNone(result["action"])
                self.assertEqual(920, result["usage"]["total_tokens"])

    def test_missing_or_incomplete_reasoning_state_prevents_continuation(self):
        for field, value in (("encrypted_content", ""), ("status", "in_progress"), ("summary", None)):
            body = response()
            body["output"][0][field] = value
            with self.subTest(field=field):
                self.assertFalse(inspect(body)["ok"])

    def test_bad_tool_names_arguments_extras_booleans_and_duplicates_are_rejected(self):
        cases = [response(name="shell", arguments={"command": "echo x"}),
                 response(name="search", arguments={"query": "x", "path": "../../private"}),
                 response(name="read_range", arguments={"path": "Dispatcher.java", "start": True, "end": 5}),
                 response(name="list", arguments={"action": "compile"}),
                 response(name="list", arguments={"extra": "hidden"}),
                 response(name="final", arguments={"answer": "done", "files": ["Dispatcher.java", "Dispatcher.java"]})]
        for raw_args in ('{"query":"x","query":"y"}', '{"query":NaN}', '[]', '"text"'):
            body = response(name="search")
            body["output"][-1]["arguments"] = raw_args
            cases.append(body)
        for body in cases:
            with self.subTest(call=body["output"][-1]):
                self.assertFalse(inspect(body)["ok"])

    def test_normalized_action_byte_budget_is_enforced(self):
        body = response(name="final", arguments={"answer": "中" * 5400, "files": []})
        result = inspect(body)
        self.assertFalse(result["ok"])
        self.assertEqual(920, result["usage"]["total_tokens"])

    def test_async_program_or_namespaced_function_is_not_local_mediation(self):
        for key, value in (("async", True), ("async", 0), ("caller", {"type": "program", "caller_id": "p"}), ("namespace", "external")):
            body = response()
            body["output"][-1][key] = value
            with self.subTest(key=key, value=value):
                self.assertFalse(inspect(body)["ok"])
        body = response()
        body["output"][-1]["caller"] = {"type": "direct"}
        body["output"][-1]["async"] = False
        self.assertTrue(inspect(body)["ok"])

    def test_response_cap_requires_responses_incomplete_reason_not_finish_reason(self):
        request = prepared(purpose="output_cap")
        body = response(request)
        body["output"] = []
        body["status"] = "incomplete"
        body["incomplete_details"] = {"reason": "max_output_tokens"}
        body["usage"]["output_tokens"] = 64
        body["usage"]["total_tokens"] = 864
        body["usage"]["output_tokens_details"]["reasoning_tokens"] = 64
        result = inspect(body, request, expect_cap=True)
        self.assertTrue(result["ok"], result["errors"])
        self.assertTrue(result["cap_observed"])
        self.assertIsNone(result["action"])
        body["status"] = "completed"
        body["incomplete_details"] = None
        body["finish_reason"] = "length"
        result = inspect(body, request, expect_cap=True)
        self.assertFalse(result["ok"])
        self.assertIn("output_cap_evidence_insufficient", result["errors"])
        self.assertFalse(result["cap_observed"])

    def test_scientific_cap_and_probe_tool_call_fail_closed(self):
        body = response()
        body["status"] = "incomplete"
        body["incomplete_details"] = {"reason": "max_output_tokens"}
        result = inspect(body)
        self.assertFalse(result["ok"])
        self.assertTrue(result["cap_observed"])
        self.assertIsNone(result["action"])
        request = prepared(purpose="output_cap")
        body = response(request)
        body["status"] = "incomplete"
        body["incomplete_details"] = {"reason": "max_output_tokens"}
        self.assertIn("function_call_in_output_cap_probe", inspect(body, request, expect_cap=True)["errors"])

    def test_response_does_not_have_to_claim_request_only_store_stream_fields(self):
        body = response()
        self.assertNotIn("store", body)
        self.assertNotIn("stream", body)
        self.assertTrue(inspect(body)["ok"])
        body["reasoning"]["summary"] = None
        body["conversation"] = None
        self.assertTrue(inspect(body)["ok"])


class OpenAIResponsesStateTests(unittest.TestCase):
    def test_deterministic_continuation_preserves_all_original_items_order_and_phase(self):
        request = prepared()
        body = response(request)
        observation = inspect(body, request)
        frozen_result = '{"ok":false,"error":"conformance_only","unicode":"中文","escaped":"\\\\ \\""}'
        actual = codec.continuation_input(request, observation, frozen_result)
        self.assertEqual(initial_input(), actual[:2])
        self.assertEqual(body["output"], actual[2:-1])
        self.assertEqual("commentary", actual[3]["phase"])
        self.assertEqual({"type": "function_call_output", "call_id": "call_offline", "output": frozen_result}, actual[-1])
        self.assertEqual(actual, codec.continuation_input(request, observation, frozen_result))
        next_request = codec.prepare_request(actual, ACTION_SCHEMAS)
        codec.verify_prepared(next_request)
        self.assertEqual(actual, json.loads(next_request.count_json)["input"])
        actual[2]["encrypted_content"] = "changed-copy"
        self.assertNotEqual(actual[2], observation["output_items"][0])

    def test_modified_observation_or_request_provenance_is_rejected(self):
        request = prepared()
        observation = inspect(response(request), request)
        cases = []
        for field, value in (("ok", False), ("request_sha256", "0" * 64), ("action", {"action": "compile"}),
                             ("output_items", []), ("expected_input_tokens", 1), ("response_canonical_sha256", "0" * 64)):
            changed = copy.deepcopy(observation)
            changed[field] = value
            cases.append(changed)
        changed = copy.deepcopy(observation)
        changed["response"]["output"][0]["encrypted_content"] = "tampered"
        cases.append(changed)
        for changed in cases:
            with self.subTest(changed=changed["request_sha256"]), self.assertRaises(codec.ResponsesContractError):
                codec.continuation_input(request, changed, "fixed result")

    def test_replay_duplicate_ids_call_ids_or_orphaned_results_are_not_admitted(self):
        request = prepared()
        good = codec.continuation_input(request, inspect(response(request), request), "fixed result")
        variants = [good[:-1], good + [copy.deepcopy(good[-1])],
                    good + copy.deepcopy(good[2:]), good + [{"type": "function_call_output", "call_id": "unknown", "output": "x"}]]
        for items in variants:
            with self.subTest(length=len(items)), self.assertRaises(codec.ResponsesContractError):
                codec.prepare_request(items, ACTION_SCHEMAS)

    def test_continuation_result_limit_and_total_limit_are_enforced(self):
        request = prepared()
        observation = inspect(response(request), request)
        for result in ("中" * 8001, {"not": "a raw frozen string"}):
            with self.subTest(result=type(result)), self.assertRaises(codec.ResponsesContractError):
                codec.continuation_input(request, observation, result)
        body = response(request)
        body["output"][0]["encrypted_content"] = "opaque" * 24_000
        observation = inspect(body, request)
        self.assertTrue(observation["ok"])
        with self.assertRaisesRegex(codec.ResponsesContractError, "request_byte_limit"):
            codec.continuation_input(request, observation, "fixed result")

    def test_probe_may_not_replay_scientific_provider_state(self):
        request = prepared()
        items = codec.continuation_input(request, inspect(response(request), request), "fixed")
        with self.assertRaisesRegex(codec.ResponsesContractError, "output_cap_must_not_reuse_provider_state"):
            codec.prepare_request(items, ACTION_SCHEMAS, purpose="output_cap")


if __name__ == "__main__":
    unittest.main()
