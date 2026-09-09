"""Offline contract tests; no engine changes or live state."""
import importlib.util
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from state_root import canonical_state_root
from local_warm import local_warm

ROOT = Path(__file__).resolve().parents[3]
HOOK = ROOT / 'integrations/reflex/hooks/pre_tool_use.py'
spec = importlib.util.spec_from_file_location('pre_hook', HOOK)
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)

class StateRootTests(unittest.TestCase):
    def test_default_external_and_invalid(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d)/'repo'
            self.assertEqual(canonical_state_root(r), r/'.tmf')
            self.assertEqual(canonical_state_root(r, Path(d)/'external/.tmf'), Path(d)/'external/.tmf')
            with self.assertRaisesRegex(ValueError,'state_root_error'): canonical_state_root(r,Path(d)/'state')
    def test_environment_shared_by_hook_and_warm(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d)/'repo';r.mkdir();(r/'a.py').write_text('def a():\n    return 1\n')
            subprocess.run(['git','init','-q',str(r)],check=True)
            state=Path(d)/'external/.tmf'
            with patch.dict(os.environ,{'TMF_STATE_ROOT':str(state)}):
                self.assertEqual(hook.resolve_state_root(str(r)),state)
                result=local_warm(str(r),'a.py')
            self.assertEqual(result['canonical_state_root'],str(state))
            self.assertTrue((state/'claims').exists());self.assertFalse((r/'.tmf').exists())
    def test_invalid_warm_no_writes_and_direct_hook_helpers_reject(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d)/'repo';r.mkdir();bad=Path(d)/'state'
            for fn in [lambda:local_warm(str(r),'a.py',str(bad)),lambda:hook.check_file_freshness(str(r),'a.py',bad),lambda:hook.resolve_unique_function_claim(str(r),'a',bad)]:
                with self.assertRaisesRegex(ValueError,'state_root_error'):fn()
            self.assertFalse((r/'.tmf').exists());self.assertFalse(bad.exists())
    def test_symlink_canonical_basename(self):
        with tempfile.TemporaryDirectory() as d:
            r=Path(d);(r/'state').mkdir();(r/'.tmf').symlink_to(r/'state',target_is_directory=True)
            with self.assertRaises(ValueError): canonical_state_root(r,r/'.tmf')

if __name__=='__main__':unittest.main()
