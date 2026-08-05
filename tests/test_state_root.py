from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tmf.cli import main
from tmf.store import Store, configure_state_root


class StateRootTests(unittest.TestCase):
    def tearDown(self) -> None:
        configure_state_root(None)

    def test_store_state_root_precedence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = root / "repo"
            repo.mkdir()
            env_root = root / "env"
            cli_root = root / "cli"

            with patch.dict(os.environ, {}, clear=False):
                os.environ.pop("TMF_STATE_ROOT", None)
                self.assertEqual(Store(repo).root, repo / ".tmf")

                os.environ["TMF_STATE_ROOT"] = str(env_root)
                self.assertEqual(Store(repo).root, env_root)

                configure_state_root(cli_root)
                self.assertEqual(Store(repo).root, cli_root)

    def test_cli_state_root_overrides_environment(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            repo = root / "repo"
            repo.mkdir()
            env_root = root / "env"
            cli_root = root / "cli"

            with patch.dict(os.environ, {"TMF_STATE_ROOT": str(env_root)}):
                self.assertEqual(main(["warm", "--repo", str(repo), "--state-root", str(cli_root)]), 0)

            self.assertTrue((cli_root / "schema_version").is_file())
            self.assertFalse(env_root.exists())
            self.assertFalse((repo / ".tmf").exists())


if __name__ == "__main__":
    unittest.main()
