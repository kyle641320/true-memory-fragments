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
        from .java_extract import extract_java_classes

        from .java_project import java_project_model
        project = java_project_model(self.repo)
        for path in self._paths():
            try:
                snapshot = getattr(self.repo, "_tmf_java_repository_snapshot", None)
                source = snapshot.texts.get(path) if snapshot is not None else self.repo.read_file(path)
                if source is None:
                    continue
                location = project.source_for(path)
                if location is not None and not self.policy.includes(source_set=location.source_set, generated=location.generated):
                    continue
                package_match = _PACKAGE_RE.search(source)
                package = package_match.group(1) if package_match else ""
                snapshot = getattr(self.repo, "_tmf_java_repository_snapshot", None)
                class_nodes = snapshot.classes.get(path, ()) if snapshot is not None else extract_java_classes(path, source)
                for node in class_nodes:
                    if node.node_kind not in {"class", "interface", "enum"} or "." in node.qualname:
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

    def resolve(self, type_expr: str, *, package: str = "", imports: dict[str, str] | None = None) -> tuple[JavaSymbol | None, str]:
        self.build()
        bare = type_expr.rsplit(".", 1)[-1]
        imports = imports or {}
        imported_target = imports.get(bare)
        if imported_target:
            imported_fqn = imported_target[:-5].replace("/", ".") if imported_target.endswith(".java") else imported_target
            symbol = self._by_fqn.get(imported_fqn) or self._by_fqn.get(type_expr)
            if symbol is None:
                matches = self._by_path_simple.get((imported_target, bare), [])
                if not matches:
                    matches = [item for item in self._by_simple.get(bare, []) if item.path.endswith("/" + imported_target) or item.path == imported_target]
                symbol = matches[0] if len(matches) == 1 else None
            return (symbol, "project_explicit_import") if symbol else (None, "external_or_missing_import")
        if "." in type_expr and type_expr in self._by_fqn:
            return self._by_fqn[type_expr], "project_fqn"
        scoped = self.candidates(bare, package=package)
        if len(scoped) == 1:
            return scoped[0], "project_same_package"
        if len(scoped) > 1:
            return None, "project_ambiguous_simple_name"
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


def java_package(source: str) -> str:
    match = _PACKAGE_RE.search(source)
    return match.group(1) if match else ""
