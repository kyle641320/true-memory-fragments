# TMF Production Integration Smoke — 2026-09-02

Verdict: **PASS**.

Scope: user-facing CLI and MCP integration smoke. This validates local operational surfaces, stale labeling, source fallback, thin retrieval, reverse callers, MCP tool listing/status, and fail-closed path/malformed-json behavior. It does not publish a package, create a release tag, or certify runtime framework behavior.

## Summary

- Checks: 15/15 pass.

## Checks

- cli_warm_exports_claims: PASS.
- cli_retrieve_thin_claims: PASS.
- cli_retrieve_omits_thick_body: PASS.
- cli_explain_json_fresh: PASS.
- cli_callers_has_main: PASS.
- cli_explain_marks_stale_after_source_change: PASS.
- cli_retrieve_source_fallback_after_stale: PASS.
- mcp_initialize: PASS.
- mcp_tools_list_required: PASS.
- mcp_warm_content: PASS.
- mcp_retrieve_thin_no_body: PASS.
- mcp_status_content: PASS.
- mcp_rejects_path_traversal: PASS.
- mcp_malformed_json_fails_closed: PASS.
- mcp_no_traceback_stderr: PASS.
