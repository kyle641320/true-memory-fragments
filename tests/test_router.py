from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd, cwd, env=None):
    return subprocess.run(cmd, cwd=cwd, env=env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)


def init_repo(tmp_path: Path, files: dict[str, str]) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-b", "master"], repo)
    run(["git", "config", "user.email", "tmf@example.com"], repo)
    run(["git", "config", "user.name", "tmf"], repo)
    for path, content in files.items():
        full = repo / path
        full.parent.mkdir(parents=True, exist_ok=True)
        full.write_text(content, encoding="utf-8")
    run(["git", "add", *files.keys()], repo)
    run(["git", "commit", "-m", "init"], repo)
    return repo


def write_fake_router(path: Path) -> Path:
    script = path / "fake_router.py"
    script.write_text(
        """
import json, sys
payload = json.load(sys.stdin)
claims = payload.get('claims_untrusted_data', [])
ids = [c.get('id') for c in claims if c.get('qualname') == 'target']
print(json.dumps({'claim_ids': ids}))
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return script


class RouterRetrieveTests(unittest.TestCase):
    def test_router_off_matches_default_payload(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"m.py": "def target():\n    return 1\n"})
            env = dict(os.environ)
            env.pop("TMF_ROUTER_COMMAND", None)
            env.pop("TMF_EMBED_COMMAND", None)
            run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "m.py", "--refresh", "--repo", str(repo)], ROOT, env=env)
            first = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "zzz", "--repo", str(repo)], ROOT, env=env).stdout)
            second = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "zzz", "--repo", str(repo)], ROOT, env=env).stdout)
            self.assertEqual(first, second)

    def test_fake_router_selects_seed_and_result_is_thin_without_trust_change(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = init_repo(root, {"m.py": "def target():\n    return 1\n"})
            env = dict(os.environ)
            env.pop("TMF_EMBED_COMMAND", None)
            env["TMF_ROUTER_COMMAND"] = f"{sys.executable} {write_fake_router(root)}"
            run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "m.py", "--refresh", "--repo", str(repo)], ROOT, env=env)
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "semantic-miss", "--repo", str(repo)], ROOT, env=env).stdout)
            target = [claim for claim in data["claims"] if claim.get("qualname") == "target"][0]
            self.assertEqual(target["trust"]["level"], "observed")
            self.assertEqual(data["view"], "thin")
            self.assertNotIn("body", json.dumps(data))
            self.assertTrue(target["fresh"])


if __name__ == "__main__":
    unittest.main()
