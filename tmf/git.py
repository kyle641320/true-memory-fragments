from __future__ import annotations

import subprocess
from pathlib import Path


class GitError(RuntimeError):
    pass


class GitRepo:
    def __init__(self, root: str | Path = ".") -> None:
        self.root = Path(root).resolve()
        self._blob_sha_cache: dict[str, str | None] = {}
        self._read_cache: dict[str, tuple[str, str]] = {}  # path -> (blob, content)

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

    def list_files(self) -> list[str]:
        """List working-tree files while honoring Git and TMF ignore rules."""
        try:
            candidates = set(self.run("ls-files", "-co", "--exclude-standard").splitlines())
            ignored = set(self.run("ls-files", "-ci", "--exclude-standard").splitlines())
        except GitError:
            return sorted(
                path.relative_to(self.root).as_posix()
                for path in self.root.rglob("*")
                if path.is_file()
                and not path.relative_to(self.root).as_posix().startswith((".git/", ".tmf/"))
            )
        tmfignore = self.root / ".tmfignore"
        if tmfignore.is_file():
            exclude = f"--exclude-from={tmfignore}"
            candidates.update(self.run("ls-files", "-o", exclude).splitlines())
            ignored.update(self.run("ls-files", "-ci", exclude).splitlines())
            ignored.update(self.run("ls-files", "-oi", exclude).splitlines())
        return sorted(
            path for path in candidates - ignored
            if not path.startswith((".git/", ".tmf/")) and (self.root / path).is_file()
        )

    def head_blob_sha(self, path: str) -> str | None:
        """Return the committed HEAD blob for provenance/debugging only."""
        try:
            return self.run("rev-parse", f"HEAD:{path}")
        except GitError:
            return None

    def preload_blob_shas(self, paths: list[str]) -> None:
        """Batch-load blob SHAs for many paths in one subprocess (P0-2)."""
        existing = [p for p in paths if (self.root / p).is_file()]
        if not existing:
            for p in paths:
                self._blob_sha_cache[p] = None
            return
        try:
            proc = subprocess.run(
                ["git", "hash-object", "--stdin-paths"],
                input="\n".join(existing) + "\n",
                cwd=self.root,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if proc.returncode == 0:
                shas = proc.stdout.strip().split("\n") if proc.stdout.strip() else []
                for p, sha in zip(existing, shas):
                    self._blob_sha_cache[p] = sha if sha else None
        except Exception:
            pass
        # Fill any slots that the batch call missed (error fallback).
        leftover = [p for p in existing if p not in self._blob_sha_cache]
        for p in leftover:
            self._blob_sha_cache[p] = self._blob_sha_raw(p)
        for p in paths:
            if p not in self._blob_sha_cache:
                self._blob_sha_cache[p] = None

    def _blob_sha_raw(self, path: str) -> str | None:
        full = self.root / path
        if not full.exists() or not full.is_file():
            return None
        try:
            return self.run("hash-object", "--", path)
        except GitError:
            return None

    def blob_sha(self, path: str) -> str | None:
        """Return the blob SHA of the current working-tree file.

        TMF freshness must track what the coding agent actually sees and edits,
        including uncommitted changes. `git rev-parse HEAD:path` is only the
        committed blob and is therefore insufficient for read-time freshness.

        The cache is pre-populated by preload_blob_shas() for batch warm ops;
        outside of that context we always call git for correctness.
        """
        if path in self._blob_sha_cache:
            return self._blob_sha_cache[path]
        return self._blob_sha_raw(path)

    def read_file(self, path: str) -> str:
        """Read file content, cached by blob SHA to avoid re-reading unchanged files."""
        blob = self.blob_sha(path)
        if blob and path in self._read_cache:
            cached_blob, cached_content = self._read_cache[path]
            if cached_blob == blob:
                return cached_content
        content = (self.root / path).read_text(encoding="utf-8", errors="replace")
        if blob:
            self._read_cache[path] = (blob, content)
        return content

    def relpath(self, path: str | Path) -> str:
        p = Path(path)
        if not p.is_absolute():
            return p.as_posix()
        return p.resolve().relative_to(self.root).as_posix()
