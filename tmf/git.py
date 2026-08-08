from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


_UNSET = object()


class GitRepo:
    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).resolve()
        self._head_cache: str | None | object = _UNSET
        self._blob_cache: dict[str, tuple[int, int, str | None]] = {}

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
        if self._head_cache is not _UNSET:
            return self._head_cache  # type: ignore[return-value]
        try:
            self._head_cache = self.run("rev-parse", "HEAD")
        except GitError:
            self._head_cache = None
        return self._head_cache  # type: ignore[return-value]

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
            self._blob_cache.pop(path, None)
            return None
        stat = full.stat()
        cached = self._blob_cache.get(path)
        if cached and cached[0] == stat.st_mtime_ns and cached[1] == stat.st_size:
            return cached[2]
        try:
            sha = self.run("hash-object", "--", path)
        except GitError:
            sha = None
        self._blob_cache[path] = (stat.st_mtime_ns, stat.st_size, sha)
        return sha

    def read_file(self, path: str) -> str:
        return (self.root / path).read_text(encoding="utf-8", errors="replace")

    def relpath(self, path: str | Path) -> str:
        p = Path(path)
        if not p.is_absolute():
            return p.as_posix()
        return p.resolve().relative_to(self.root).as_posix()
