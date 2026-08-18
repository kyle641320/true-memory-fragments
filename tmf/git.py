from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Iterable


class GitError(RuntimeError):
    pass


_UNSET = object()


class GitRepo:
    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).resolve()
        self._head_cache: str | None | object = _UNSET
        self._blob_cache: dict[str, tuple[int, int, int, str | None]] = {}

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

    def ls_files(self) -> list[str]:
        """Return tracked paths without Git's quoting or line-delimiter ambiguity."""
        proc = subprocess.run(
            ["git", "ls-files", "-z"],
            cwd=self.root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        if proc.returncode != 0:
            stderr = proc.stderr.decode(errors="replace").strip()
            raise GitError(stderr or "git ls-files -z failed")
        return [os.fsdecode(item) for item in proc.stdout.split(b"\0") if item]

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
        # Freshness must not trust (mtime, size) alone: content can be restored
        # to the same length with its timestamp preserved. ctime cannot be set
        # by that restore and therefore closes the stale-cache hole while still
        # allowing repeated checks in one request to reuse the verified digest.
        try:
            stat = full.stat()
            key = (stat.st_mtime_ns, stat.st_size, stat.st_ctime_ns)
            cached = self._blob_cache.get(path)
            if cached and cached[:3] == key:
                return cached[3]
            sha = self.run("hash-object", "--", path)
            after = full.stat()
        except (GitError, OSError):
            sha = None
        else:
            after_key = (after.st_mtime_ns, after.st_size, after.st_ctime_ns)
            if after_key == key:
                self._blob_cache[path] = (*after_key, sha)
            else:
                # The file changed while Git read it; retry against current bytes.
                return self.blob_sha(path)
        return sha

    def blob_shas(self, paths: Iterable[str]) -> dict[str, str | None]:
        """Hash many worktree files in one git process and prime the local cache.

        ``blob_sha`` deliberately follows dirty worktree content, but one
        ``git hash-object`` process per path dominates large warm/no-op runs.
        The batch form preserves those semantics. Digests are recomputed on
        every call unless a digest was already verified against the same
        ``(mtime, size, ctime)`` in this repo instance. Files changed while the
        batch is running are re-read through ``blob_sha``. Paths containing
        line separators cannot be represented by Git's line-delimited
        ``--stdin-paths`` protocol and use the safe single-path form instead.
        """
        ordered = list(dict.fromkeys(paths))
        result: dict[str, str | None] = {}
        pending: list[str] = []
        before: dict[str, tuple[int, int, int]] = {}
        for path in ordered:
            full = self.root / path
            if not full.is_file():
                self._blob_cache.pop(path, None)
                result[path] = None
                continue
            if "\n" in path or "\r" in path:
                result[path] = self.blob_sha(path)
                continue
            try:
                stat = full.stat()
            except OSError:
                result[path] = None
                continue
            key = (stat.st_mtime_ns, stat.st_size, stat.st_ctime_ns)
            cached = self._blob_cache.get(path)
            if cached and cached[:3] == key:
                result[path] = cached[3]
                continue
            pending.append(path)
            before[path] = key
        if pending:
            proc = subprocess.run(
                ["git", "hash-object", "--stdin-paths"],
                cwd=self.root,
                input="".join(f"{path}\n" for path in pending),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            hashes = proc.stdout.splitlines() if proc.returncode == 0 else []
            if len(hashes) == len(pending):
                for path, sha in zip(pending, hashes):
                    full = self.root / path
                    try:
                        stat = full.stat()
                    except OSError:
                        result[path] = None
                        continue
                    after = (stat.st_mtime_ns, stat.st_size, stat.st_ctime_ns)
                    if after == before[path]:
                        self._blob_cache[path] = (*after, sha)
                        result[path] = sha
                    else:
                        result[path] = self.blob_sha(path)
            else:
                for path in pending:
                    result[path] = self.blob_sha(path)
        return {path: result.get(path) for path in ordered}

    def read_file(self, path: str) -> str:
        return (self.root / path).read_text(encoding="utf-8", errors="replace")

    def relpath(self, path: str | Path) -> str:
        p = Path(path)
        if not p.is_absolute():
            return p.as_posix()
        return p.resolve().relative_to(self.root).as_posix()
