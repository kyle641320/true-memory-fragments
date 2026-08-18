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


def write_fake_embedder(path: Path) -> Path:
    script = path / "fake_embedder.py"
    script.write_text(
        """
import json, sys
payload = json.load(sys.stdin)
texts = payload.get('texts_untrusted_data', [])
vectors = []
for text in texts:
    t = str(text).lower()
    if 'payments' in t or 'charge' in t or 'bill' in t:
        vectors.append([1.0, 0.0])
    elif 'main' in t:
        vectors.append([0.8, 0.0])
    else:
        vectors.append([0.0, 1.0])
print(json.dumps({'vectors': vectors}))
""".strip()
        + "\n",
        encoding="utf-8",
    )
    return script


class EmbeddingRetrieveTests(unittest.TestCase):
    def test_embeddings_off_retrieve_text_matches_default_cli_payload(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"m.py": "def add(a, b):\n    return a + b\n"})
            base_env = dict(os.environ)
            base_env.pop("TMF_EMBED_COMMAND", None)
            run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "m.py", "--refresh", "--repo", str(repo)], ROOT, env=base_env)
            first = run([sys.executable, "-m", "tmf.cli", "retrieve", "add", "--repo", str(repo)], ROOT, env=base_env).stdout
            second = run([sys.executable, "-m", "tmf.cli", "retrieve", "add", "--repo", str(repo)], ROOT, env=base_env).stdout
            self.assertEqual(json.loads(first), json.loads(second))

    def test_configured_embedder_can_select_semantic_seed_and_expand_fresh_edges(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = init_repo(root, {
                "a.py": "from b import charge\n\ndef main():\n    return charge()\n",
                "b.py": "def charge():\n    return 'bill'\n",
            })
            env = dict(os.environ)
            env["TMF_EMBED_COMMAND"] = f"{sys.executable} {write_fake_embedder(root)}"
            run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "b.py", "--refresh", "--repo", str(repo)], ROOT, env=env)
            run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "a.py", "--refresh", "--repo", str(repo)], ROOT, env=env)
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "payments", "--repo", str(repo), "--limit", "5"], ROOT, env=env).stdout)
            names = {claim.get("qualname") for claim in data["claims"]}
            self.assertIn("charge", names)
            self.assertIn("main", names)
            self.assertEqual(data["view"], "thin")
            self.assertNotIn("quoted_text_untrusted_data", json.dumps(data))
            self.assertTrue(all(claim["fresh"] for claim in data["claims"]))

    def test_stale_embedding_seed_is_excluded(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = init_repo(root, {"b.py": "def charge():\n    return 'bill'\n"})
            env = dict(os.environ)
            env["TMF_EMBED_COMMAND"] = f"{sys.executable} {write_fake_embedder(root)}"
            run([sys.executable, "-m", "tmf.cli", "retrieve", "--path", "b.py", "--refresh", "--repo", str(repo)], ROOT, env=env)
            (repo / "b.py").write_text("def charge():\n    return 'changed bill'\n", encoding="utf-8")
            data = json.loads(run([sys.executable, "-m", "tmf.cli", "retrieve", "payments", "--repo", str(repo), "--limit", "5"], ROOT, env=env).stdout)
            self.assertEqual(data["claims"], [])


if __name__ == "__main__":
    unittest.main()
