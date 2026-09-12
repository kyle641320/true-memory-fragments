"""Exercise the shipped legacy module command, without a model/network call."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class AssistAdapterTests(unittest.TestCase):
    def run_adapter(self, request, fail=False):
        with tempfile.TemporaryDirectory() as d:
            fake = Path(d) / 'openclaw'
            fake.write_text('#!' + sys.executable + '\n' + '''import json, sys
assert sys.argv[1:5] == ['infer', 'model', 'run', '--json']
assert sys.argv[sys.argv.index('--model') + 1] == 'test/model'
prompt = sys.argv[sys.argv.index('--prompt') + 1]
assert 'TMF_ASSIST_REQUEST_JSON:' in prompt
request = json.loads(prompt.split('TMF_ASSIST_REQUEST_JSON:', 1)[1])
assert request['question'] == 'test question'
''' + ("sys.stderr.write('controlled failure'); sys.exit(7)\n" if fail else '''answer = {'answer': 'test answer', 'confidence': 'medium', 'inferences': [], 'evidence': [], 'assumptions': [], 'unresolved': [], 'suggested_source_reads': []}
print(json.dumps({'outputs': [{'text': json.dumps(answer)}]}))
'''))
            fake.chmod(0o700)
            env = dict(os.environ)
            env.update(TMF_ASSIST_OPENCLAW_BIN=str(fake), TMF_ASSIST_OPENCLAW_MODEL='test/model', PYTHONDONTWRITEBYTECODE='1')
            return subprocess.run([sys.executable, '-B', '-m', 'tmf.assist_openclaw'], input=json.dumps(request), capture_output=True, text=True, env=env, timeout=15)

    def test_legacy_module_command(self):
        result = self.run_adapter({'question': 'test question'})
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['confidence'], 0.5)
        self.assertEqual(json.loads(result.stdout)['answer'], 'test answer')

    def test_provider_failure_is_nonzero(self):
        result = self.run_adapter({'question': 'test question'}, fail=True)
        self.assertEqual(result.returncode, 2)
        self.assertEqual(result.stdout, '')
        self.assertIn('controlled failure', result.stderr)

    def test_bad_request_does_not_invoke_provider(self):
        result = self.run_adapter([])
        self.assertEqual(result.returncode, 2)
        self.assertIn('request must be a JSON object', result.stderr)


if __name__ == '__main__':
    unittest.main()
