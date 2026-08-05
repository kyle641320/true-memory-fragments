from __future__ import annotations

import hashlib
import multiprocessing
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .derive import derive_claims_for_path
from .git import GitRepo
from .schema import Claim, SkippedClaim

DEFAULT_PER_FILE_TIMEOUT_SECONDS = 60.0


@dataclass(frozen=True)
class DeriveOutcome:
    claims: list[Claim]
    skipped: SkippedClaim | None = None


class _SnapshotRepo:
    def __init__(self, root: str, path: str, source: str, blob: str | None, head: str | None):
        self.root = Path(root)
        self._path = path
        self._source = source
        self._blob = blob
        self._head = head

    def read_file(self, path: str) -> str:
        if path != self._path:
            raise FileNotFoundError(path)
        return self._source

    def blob_sha(self, path: str) -> str:
        if path != self._path:
            raise FileNotFoundError(path)
        if self._blob is not None:
            return self._blob
        data = self._source.encode("utf-8")
        header = f"blob {len(data)}\0".encode("utf-8")
        return hashlib.sha1(header + data).hexdigest()

    def head(self) -> str:
        return self._head or "dry-run-blob"


def _derive_worker(
    connection: Any,
    repo_root: str,
    path: str,
    source: str | None,
    blob: str | None,
    head: str | None,
    use_model: bool,
) -> None:
    try:
        repo = GitRepo(repo_root) if source is None else _SnapshotRepo(repo_root, path, source, blob, head)
        connection.send(("ok", derive_claims_for_path(repo, path, use_model=use_model)))
    except BaseException as exc:
        connection.send(("error", f"{type(exc).__name__}: {exc}", traceback.format_exc()))
    finally:
        connection.close()


def derive_claims_for_path_with_timeout(
    repo: GitRepo,
    path: str,
    *,
    per_file_timeout: float = DEFAULT_PER_FILE_TIMEOUT_SECONDS,
    source: str | None = None,
    blob: str | None = None,
    head: str | None = None,
    use_model: bool = False,
) -> DeriveOutcome:
    """Derive one file in an engine-owned, killable process boundary."""

    started = time.monotonic()
    if per_file_timeout <= 0:
        try:
            target_repo = repo if source is None else _SnapshotRepo(str(repo.root), path, source, blob, head)
            return DeriveOutcome(derive_claims_for_path(target_repo, path, use_model=use_model))
        except Exception as exc:
            elapsed_ms = round((time.monotonic() - started) * 1000)
            return DeriveOutcome([], SkippedClaim(path, "derive_failed", elapsed_ms, f"{type(exc).__name__}: {exc}"))

    # fork keeps the budget about derivation itself on POSIX; spawn is the
    # portable fallback when fork is unavailable.
    method = "fork" if "fork" in multiprocessing.get_all_start_methods() else "spawn"
    context = multiprocessing.get_context(method)
    parent, child = context.Pipe(duplex=False)
    process = context.Process(
        target=_derive_worker,
        args=(child, str(repo.root), path, source, blob, head, use_model),
        daemon=True,
    )
    process.start()
    child.close()
    try:
        if not parent.poll(per_file_timeout):
            process.terminate()
            process.join(timeout=1.0)
            if process.is_alive():
                process.kill()
                process.join(timeout=1.0)
            elapsed_ms = round((time.monotonic() - started) * 1000)
            return DeriveOutcome(
                [],
                SkippedClaim(
                    path,
                    "derive_timeout",
                    elapsed_ms,
                    f"derive timed out after {per_file_timeout:g}s",
                ),
            )
        message = parent.recv()
        process.join(timeout=1.0)
        elapsed_ms = round((time.monotonic() - started) * 1000)
        if message[0] == "ok":
            return DeriveOutcome(message[1])
        return DeriveOutcome([], SkippedClaim(path, "derive_failed", elapsed_ms, message[1]))
    except EOFError:
        elapsed_ms = round((time.monotonic() - started) * 1000)
        return DeriveOutcome([], SkippedClaim(path, "derive_failed", elapsed_ms, "derive worker exited without a result"))
    finally:
        parent.close()
        if process.is_alive():
            process.kill()
            process.join(timeout=1.0)
