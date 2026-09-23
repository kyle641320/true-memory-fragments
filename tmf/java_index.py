from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


_PACKAGE_RE = re.compile(r"(?m)^\s*package\s+([A-Za-z_][\w.]*)\s*;")


@dataclass(frozen=True)
class JavaSymbol:
    fqn: str
    simple_name: str
    path: str
    package: str
    module: str = "root"
    source_set: str = "unclassified"
    generated: bool = False


@dataclass(frozen=True)
class JavaIndexPolicy:
    include_main: bool = True
    include_test: bool = True
    include_generated: bool = True
    include_custom: bool = True
    include_unclassified: bool = True

    def includes(self, *, source_set: str, generated: bool) -> bool:
        if generated:
            return self.include_generated
        if source_set == "main":
            return self.include_main
        if source_set == "test":
            return self.include_test
        if source_set == "unclassified":
            return self.include_unclassified
        return self.include_custom


@dataclass(frozen=True)
class ExternalJavaSymbol:
    fqn: str
    simple_name: str
    origin: str
    provenance: str
    source_defined: bool = False


class JavaProjectIndex:
    """Read-only project symbol index for source-defined Java top-level types.

    This deliberately indexes source declarations only. Classpath/JDK symbols,
    generated sources, reflection, and runtime proxies remain explicit boundaries.
    """

    def __init__(self, repo: Any, policy: JavaIndexPolicy | None = None):
        self.repo = repo
        self.policy = policy or JavaIndexPolicy()
        self._by_fqn: dict[str, JavaSymbol] = {}
        self._by_simple: dict[str, list[JavaSymbol]] = {}
        self._by_package_simple: dict[tuple[str, str], list[JavaSymbol]] = {}
        self._by_path_simple: dict[tuple[str, str], list[JavaSymbol]] = {}
        self._built = False

    def _paths(self) -> list[str]:
        from .java_project import java_project_model
        snapshot = getattr(self.repo, "_tmf_java_repository_snapshot", None)
        return list(snapshot.paths) if snapshot is not None else java_project_model(self.repo).java_paths()

    def build(self) -> "JavaProjectIndex":
        if self._built:
            return self
        from .java_project import java_project_model
        project = java_project_model(self.repo)
        snapshot = getattr(self.repo, "_tmf_java_repository_snapshot", None)
        if snapshot is not None:
            locations = {item.path: item for item in project.sources}
            for item in snapshot.symbol_manifest():
                location = locations.get(item["path"])
                # Syntax shards may survive build-file-only changes. Layout
                # metadata must come from the current project model, not the
                # old symbol shard whose Java source bytes still match.
                source_set = location.source_set if location else item.get("source_set", "unclassified")
                generated = location.generated if location else bool(item.get("generated", False))
                if not self.policy.includes(source_set=source_set, generated=generated):
                    continue
                symbol = JavaSymbol(
                    fqn=item["fqn"], simple_name=item["simple_name"], path=item["path"],
                    package=item.get("package", ""), module=location.module if location else item.get("module", "root"),
                    source_set=source_set, generated=generated,
                )
                self._by_fqn.setdefault(symbol.fqn, symbol)
                self._by_simple.setdefault(symbol.simple_name, []).append(symbol)
                self._by_package_simple.setdefault((symbol.package, symbol.simple_name), []).append(symbol)
                self._by_path_simple.setdefault((symbol.path, symbol.simple_name), []).append(symbol)
            self._built = True
            return self

        from .java_extract import extract_java_classes
        for path in self._paths():
            try:
                source = self.repo.read_file(path)
                location = project.source_for(path)
                if location is not None and not self.policy.includes(source_set=location.source_set, generated=location.generated):
                    continue
                package_match = _PACKAGE_RE.search(source)
                package = package_match.group(1) if package_match else ""
                class_nodes = extract_java_classes(path, source)
                for node in class_nodes:
                    if node.node_kind not in {"class", "interface", "enum", "record"} or "." in node.qualname:
                        continue
                    simple = node.qualname
                    fqn = f"{package}.{simple}" if package else simple
                    symbol = JavaSymbol(
                        fqn=fqn,
                        simple_name=simple,
                        path=path,
                        package=package,
                        module=location.module if location else "root",
                        source_set=location.source_set if location else "unclassified",
                        generated=location.generated if location else False,
                    )
                    self._by_fqn.setdefault(fqn, symbol)
                    self._by_simple.setdefault(simple, []).append(symbol)
                    self._by_package_simple.setdefault((package, simple), []).append(symbol)
                    self._by_path_simple.setdefault((path, simple), []).append(symbol)
            except (OSError, UnicodeError):
                continue
        self._built = True
        return self

    def candidates(self, simple_name: str, *, package: str | None = None) -> list[JavaSymbol]:
        self.build()
        if package is not None:
            return list(self._by_package_simple.get((package, simple_name), []))
        return list(self._by_simple.get(simple_name, []))

    def resolve(self, type_expr: str, *, package: str = "", imports: dict[str, str] | None = None,
                wildcard_imports: set[str] | None = None) -> tuple[JavaSymbol | None, str]:
        self.build()
        bare = type_expr.rsplit(".", 1)[-1]
        imports = imports or {}

        def exact(fqn: str) -> list[JavaSymbol]:
            # Duplicate FQNs across modules/source sets require a compiler
            # classpath to disambiguate; never silently select the first.
            return [item for item in self._by_simple.get(bare, []) if item.fqn == fqn]

        if "." in type_expr:
            matches = exact(type_expr)
            if len(matches) == 1:
                return matches[0], "project_fqn"
            return None, "project_ambiguous_simple_name" if matches else "project_type_not_found"
        imported_target = imports.get(bare)
        if imported_target:
            imported_fqn = imported_target[:-5].replace("/", ".") if imported_target.endswith(".java") else imported_target
            matches = exact(imported_fqn)
            if not matches:
                matches = self._by_path_simple.get((imported_target, bare), [])
                if not matches:
                    matches = [item for item in self._by_simple.get(bare, []) if item.path.endswith("/" + imported_target) or item.path == imported_target]
            if len(matches) > 1:
                return None, "project_ambiguous_simple_name"
            symbol = matches[0] if matches else None
            return (symbol, "project_explicit_import") if symbol else (None, "external_or_missing_import")
        scoped = self.candidates(bare, package=package)
        if len(scoped) == 1:
            return scoped[0], "project_same_package"
        if len(scoped) > 1:
            return None, "project_ambiguous_simple_name"
        if wildcard_imports:
            matches = [item for item in self._by_simple.get(bare, []) if item.package in wildcard_imports]
            if len(matches) == 1:
                return matches[0], "project_wildcard_import"
            if len(matches) > 1:
                return None, "project_ambiguous_wildcard_import"
            return None, "project_wildcard_type_not_found"
        global_matches = self.candidates(bare)
        if len(global_matches) > 1:
            return None, "project_ambiguous_simple_name"
        return None, "project_type_not_found"

    def external_placeholder(self, type_expr: str, *, imports: dict[str, str] | None = None) -> ExternalJavaSymbol | None:
        """Describe a non-source type without promoting it to a resolved source symbol."""
        bare = type_expr.rsplit(".", 1)[-1]
        imported = (imports or {}).get(bare)
        imported_fqn = None
        if imported:
            imported_fqn = imported[:-5].replace("/", ".") if imported.endswith(".java") else imported
        fqn = imported_fqn or (type_expr if "." in type_expr else None)
        if not fqn:
            return None
        origin = "jdk" if fqn.startswith(("java.", "javax.", "jdk.")) else "external_dependency"
        provenance = "explicit_import" if imported_fqn else "fully_qualified_reference"
        return ExternalJavaSymbol(fqn=fqn, simple_name=fqn.rsplit(".", 1)[-1], origin=origin, provenance=provenance)


def java_project_index(repo: Any, policy: JavaIndexPolicy | None = None) -> JavaProjectIndex:
    policy = policy or JavaIndexPolicy()
    cache = getattr(repo, "_tmf_java_project_indexes", {})
    cached_entry = cache.get(policy)
    if cached_entry is not None and getattr(repo, "_tmf_java_snapshot_pinned", False):
        return cached_entry[1]
    snapshot = getattr(repo, "_tmf_java_repository_snapshot", None)
    paths = list(snapshot.paths) if snapshot is not None else JavaProjectIndex(repo, policy)._paths()
    fingerprint = snapshot.fingerprint if snapshot is not None else tuple(
        (path, (repo.root / path).stat().st_mtime_ns, (repo.root / path).stat().st_size)
        for path in paths
        if (repo.root / path).is_file()
    )
    cache_key = policy
    if cached_entry is None or cached_entry[0] != fingerprint:
        cached = JavaProjectIndex(repo, policy).build()
        cache = dict(cache)
        cache[cache_key] = (fingerprint, cached)
        setattr(repo, "_tmf_java_project_indexes", cache)
    else:
        cached = cached_entry[1]
    return cached


def java_symbol_manifest_digest(repo: Any) -> str:
    """Fingerprint the source lookup universe, retaining duplicate declarations.

    Consulted-file bindings cannot detect a newly competing type in another
    file. This digest deliberately records symbol identity, not method bodies:
    unrelated body edits must not invalidate every hierarchy-backed claim.
    Outside a pinned derivation snapshot, build the index from a fresh repo
    view when any tracked source/build input changes (including ctime).
    """
    import hashlib
    import json
    from dataclasses import asdict
    from .git import GitRepo
    from .java_project import JavaProjectModel, _BUILD_FILES, _SETTINGS_FILES
    from pathlib import PurePosixPath

    pinned = getattr(repo, "_tmf_java_snapshot_pinned", False)
    cache = getattr(repo, "_tmf_java_resolution_manifest", None)
    if pinned:
        fingerprint = ("pinned", id(getattr(repo, "_tmf_java_repository_snapshot", None)))
    else:
        inputs = sorted(path for path in JavaProjectModel(repo)._tracked_paths()
                        if path.endswith(".java") or PurePosixPath(path).name in _BUILD_FILES | _SETTINGS_FILES)
        entries = []
        for path in inputs:
            try:
                stat = (repo.root / path).stat()
                entries.append((path, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size))
            except FileNotFoundError:
                entries.append((path, None, None, None))
        fingerprint = tuple(entries)
    if cache is not None and cache[0] == fingerprint:
        return cache[1]
    index = java_project_index(repo) if pinned else JavaProjectIndex(GitRepo(repo.root)).build()
    symbols = [asdict(symbol) for name in sorted(index._by_simple)
               for symbol in index._by_simple[name]]
    symbols.sort(key=lambda item: json.dumps(item, sort_keys=True))
    digest = hashlib.sha256(json.dumps(symbols, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    setattr(repo, "_tmf_java_resolution_manifest", (fingerprint, digest))
    return digest


def java_package(source: str) -> str:
    match = _PACKAGE_RE.search(source)
    return match.group(1) if match else ""
