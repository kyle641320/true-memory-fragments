from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path
from unittest.mock import patch

from tmf.assist_openclaw import _extract_json_object, _normalize_response, run_openclaw


class OpenClawAssistAdapterTests(unittest.TestCase):
    def test_extracts_plain_or_fenced_json_only(self):
        self.assertEqual(_extract_json_object('{"answer":"ok"}'), {"answer": "ok"})
        self.assertEqual(_extract_json_object('```json\n{"answer":"ok"}\n```'), {"answer": "ok"})
        with self.assertRaises(ValueError):
            _extract_json_object('{"confidence": NaN}')

    def test_normalizes_common_confidence_labels_for_openclaw_outputs(self):
        self.assertEqual(_normalize_response({"confidence": "high"})["confidence"], 0.8)
        self.assertEqual(_normalize_response({"confidence": "medium"})["confidence"], 0.5)
        self.assertEqual(_normalize_response({"confidence": "low"})["confidence"], 0.2)
        self.assertEqual(_normalize_response({"confidence": 0.7})["confidence"], 0.7)

    def test_run_openclaw_uses_shell_free_cli_and_outputs_provider_json(self):
        with tempfile.TemporaryDirectory() as temp:
            calls = Path(temp) / "calls.json"
            fake = Path(temp) / "openclaw"
            fake.write_text(
                textwrap.dedent(
                    f"""#!/usr/bin/env python3
import json, pathlib, sys
pathlib.Path({str(calls)!r}).write_text(json.dumps(sys.argv), encoding='utf-8')
json.dump({{"outputs":[{{"text": json.dumps({{
    "answer":"ok", "inferences":[], "confidence":0.5, "evidence":[],
    "assumptions":[], "unresolved":[], "suggested_source_reads":[]
}})}}]}}, sys.stdout)
"""
                ),
                encoding="utf-8",
            )
            fake.chmod(0o755)
            env = {
                "TMF_ASSIST_OPENCLAW_BIN": str(fake),
                "TMF_ASSIST_OPENCLAW_MODEL": "aisz/gpt-5.5",
            }
            with patch.dict(os.environ, env, clear=False):
                result = run_openclaw({"question_untrusted_data": "q"})
            self.assertEqual(result["answer"], "ok")
            argv = json.loads(calls.read_text(encoding="utf-8"))
            self.assertEqual(argv[:4], [str(fake), "infer", "model", "run"])
            self.assertIn("--json", argv)
            self.assertIn("--prompt", argv)
            self.assertNotIn(";", argv)

    def test_module_cli_reads_stdin_and_writes_json(self):
        with tempfile.TemporaryDirectory() as temp:
            fake = Path(temp) / "openclaw"
            fake.write_text(
                textwrap.dedent(
                    """#!/usr/bin/env python3
import json, sys
json.dump({"outputs":[{"text": json.dumps({
    "answer":"ok", "inferences":[], "confidence":0.5, "evidence":[],
    "assumptions":[], "unresolved":[], "suggested_source_reads":[]
})}]}, sys.stdout)
"""
                ),
                encoding="utf-8",
            )
            fake.chmod(0o755)
            env = os.environ.copy()
            env.update({"TMF_ASSIST_OPENCLAW_BIN": str(fake)})
            proc = subprocess.run(
                [sys.executable, "-m", "tmf.assist_openclaw"],
                input=json.dumps({"question_untrusted_data": "q"}),
                cwd=Path(__file__).resolve().parents[1],
                env=env,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                check=True,
            )
            self.assertEqual(json.loads(proc.stdout)["answer"], "ok")


if __name__ == "__main__":
    unittest.main()
