from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

from .git import GitRepo


@dataclass(frozen=True)
class ImportTarget:
    local_name: str
    module_path: str
    symbol: str | None
    kind: str  # from_import | import_module


def _module_to_candidates(repo: GitRepo, module: str, current_path: str, level: int = 0) -> list[str]:
    parts = [p for p in module.split(".") if p]
    base = repo.root
    if level:
        cur_dir = (repo.root / current_path).parent
        base = cur_dir
        # level=1 means current package/directory; level=2 parent, etc.
        for _ in range(max(0, level - 1)):
            base = base.parent
    rel_base = base.relative_to(repo.root) if base != repo.root else Path("")
    mod_path = rel_base.joinpath(*parts) if parts else rel_base
    candidates = []
    file_candidate = (mod_path.with_suffix(".py")).as_posix()
    init_candidate = (mod_path / "__init__.py").as_posix()
    for candidate in [file_candidate, init_candidate]:
        if (repo.root / candidate).is_file():
            candidates.append(candidate)
    return candidates


def _unique_module_path(repo: GitRepo, module: str, current_path: str, level: int = 0) -> str | None:
    candidates = _module_to_candidates(repo, module, current_path, level=level)
    return candidates[0] if len(candidates) == 1 else None


def parse_import_targets(repo: GitRepo, path: str, source: str) -> tuple[dict[str, ImportTarget], dict[str, str]]:
    """Return conservative import alias table and unresolved import reasons."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return {}, {}
    table: dict[str, ImportTarget] = {}
    unresolved: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.ImportFrom):
            if any(alias.name == "*" for alias in node.names):
                unresolved["*"] = "star_import_not_resolved"
                continue
            module = node.module or ""
            module_path = _unique_module_path(repo, module, path, level=node.level)
            if module_path is None:
                for alias in node.names:
                    unresolved[alias.asname or alias.name] = "import_module_not_unique_or_missing"
                continue
            for alias in node.names:
                local = alias.asname or alias.name
                table[local] = ImportTarget(local_name=local, module_path=module_path, symbol=alias.name, kind="from_import")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                module_path = _unique_module_path(repo, alias.name, path, level=0)
                local = alias.asname or alias.name.split(".")[0]
                if module_path is None:
                    unresolved[local] = "import_module_not_unique_or_missing"
                    continue
                table[local] = ImportTarget(local_name=local, module_path=module_path, symbol=None, kind="import_module")
    return table, unresolved
