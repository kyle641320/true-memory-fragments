"""Run existing upgrade contracts against an installed wheel, not checkout imports."""
from pathlib import Path
import argparse
import os
import shutil
import subprocess
import tempfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python', required=True, help='Python in the wheel installation venv')
    args = parser.parse_args()
    # Do not resolve venv symlinks: that would select the system interpreter.
    python = os.path.abspath(args.python)
    root = Path(__file__).resolve().parents[1]
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(('TMF_', 'PYTHON'))}
    env['PYTHONDONTWRITEBYTECODE'] = '1'
    with tempfile.TemporaryDirectory(prefix='tmf-installed-upgrade-') as directory:
        test_root = Path(directory)
        tests = test_root / 'tests'
        tests.mkdir()
        (tests / '__init__.py').touch()
        for name in ('test_readonly_locator_compat.py', 'test_assist_openclaw_adapter.py'):
            shutil.copyfile(root / 'tests' / name, tests / name)
        code = '''
import importlib.metadata, pathlib, sys, unittest
import tmf
module = pathlib.Path(tmf.__file__).resolve()
assert module.is_relative_to(pathlib.Path(sys.prefix).resolve()), module
assert 'site-packages' in module.parts, module
assert tmf.__version__ == importlib.metadata.version('true-memory-fragments')
print('Installed package:', module, 'version:', tmf.__version__, flush=True)
sys.path.insert(0, sys.argv[1])
suite = unittest.defaultTestLoader.loadTestsFromNames([
    'tests.test_readonly_locator_compat', 'tests.test_assist_openclaw_adapter'])
assert suite.countTestCases() >= 11, suite.countTestCases()
result = unittest.TextTestRunner(verbosity=2).run(suite)
sys.exit(not result.wasSuccessful())
'''
        subprocess.run([python, '-I', '-B', '-c', code, directory],
                       cwd=directory, env=env, check=True, timeout=180)


if __name__ == '__main__':
    main()
