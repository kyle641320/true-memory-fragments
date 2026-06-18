from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


class GitRepo:
    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).resolve()

    def run(self, *args: str, check: bool = True) -> str:
        proc = subprocess.run(
            ["git", *args],
            cwd=self.root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if check and proc.returncode != 0:
            raise GitError(proc.stderr.strip() or proc.stdout.strip() or f"git {' '.join(args)} failed")
        return proc.stdout.strip()

    def head(self) -> str | None:
        try:
            return self.run("rev-parse", "HEAD")
        except GitError:
            return None

    def head_blob_sha(self, path: str) -> str | None:
        """Return the committed HEAD blob for provenance/debugging only."""
        try:
            return self.run("rev-parse", f"HEAD:{path}")
        except GitError:
            return None

    def blob_sha(self, path: str) -> str | None:
        """Return the blob SHA of the current working-tree file.

        TMF freshness must track what the coding agent actually sees and edits,
        including uncommitted changes. `git rev-parse HEAD:path` is only the
        committed blob and is therefore insufficient for read-time freshness.
        """
        full = self.root / path
        if not full.exists() or not full.is_file():
            return None
        try:
            return self.run("hash-object", "--", path)
        except GitError:
            return None

    def read_file(self, path: str) -> str:
        return (self.root / path).read_text(encoding="utf-8", errors="replace")

    def relpath(self, path: str | Path) -> str:
        p = Path(path)
        if not p.is_absolute():
            return p.as_posix()
        return p.resolve().relative_to(self.root).as_posix()
