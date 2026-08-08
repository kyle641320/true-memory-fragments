from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo
from tmf.ids import stable_env_claim_id, stable_env_read_edge_claim_id, stable_config_read_edge_claim_id, stable_config_claim_id, stable_function_claim_id
from tmf.retrieve import reverse_env_readers, reverse_config_key_readers
from tmf.store import Store


class EnvAndConfigReadEdgeTests(unittest.TestCase):
    def test_literal_env_reads_create_env_node_and_reverse_and_dynamic_unresolved(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "app.py").write_text('''
import os

def load(name):
    a = os.environ["API_KEY"]
    b = os.environ.get("DEBUG")
    c = os.getenv("HOME")
    d = os.getenv(name)
    e = os.environ.get("X" + "Y")
    return a, b, c, d, e
''', encoding="utf-8")
            repo = GitRepo(root)
            store = Store(root)
            for claim in derive_claims_for_path(repo, "app.py"):
                store.put_claim(claim)
            fn = stable_function_claim_id("app.py", "load")
            api = stable_env_claim_id("API_KEY")
            self.assertIsNotNone(store.get_claim(api))
            self.assertIsNotNone(store.get_claim(stable_env_read_edge_claim_id(fn, "API_KEY")))
            graph = store.get_claim(fn).body["graph"]
            self.assertEqual([x["env_name"] for x in graph["reads_env"]], ["API_KEY", "DEBUG", "HOME"])
            reasons = {x["reason"] for x in graph["reads_env_unresolved"]}
            self.assertIn("env_key_not_literal", reasons)
            self.assertEqual(reverse_env_readers(root, "API_KEY")["readers"][0]["reader_id"], fn)

    def test_literal_config_key_read_resolves_unique_config_file_and_dynamic_unresolved(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "settings.json").write_text('{"service": {"url": "https://example"}, "other": 1}', encoding="utf-8")
            (root / "app.py").write_text('''
import json

def load(path, key):
    config = json.load(open("settings.json"))
    a = config["service"]["url"]
    b = config[key]
    return a, b
''', encoding="utf-8")
            repo = GitRepo(root)
            store = Store(root)
            for path in ["settings.json", "app.py"]:
                for claim in derive_claims_for_path(repo, path):
                    store.put_claim(claim)
            fn = stable_function_claim_id("app.py", "load")
            cfg = stable_config_claim_id("settings.json", "service.url")
            self.assertIsNotNone(store.get_claim(stable_config_read_edge_claim_id(fn, cfg)))
            graph = store.get_claim(fn).body["graph"]
            self.assertEqual(graph["reads_config_key"][0]["config_key"], "service.url")
            self.assertEqual(graph["reads_config_key_unresolved"][0]["reason"], "config_key_not_literal")
            self.assertEqual(reverse_config_key_readers(root, cfg)["readers"][0]["reader_id"], fn)


if __name__ == "__main__":
    unittest.main()
