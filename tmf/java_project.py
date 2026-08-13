from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
import re
import xml.etree.ElementTree as ET
from typing import Any


_BUILD_FILES = {"pom.xml", "build.gradle", "build.gradle.kts"}
_SETTINGS_FILES = {"settings.gradle", "settings.gradle.kts"}


@dataclass(frozen=True)
class JavaSourceLocation:
    path: str
    module: str
    module_root: str
    source_set: str
    generated: bool


@dataclass(frozen=True)
class JavaModule:
    name: str
    root: str
    build_system: str


@dataclass(frozen=True)
class JavaModuleDependency:
    source_root: str
    target_root: str
    scope: str
    resolution: str


@dataclass(frozen=True)
class JavaRepositorySnapshot:
    """One-warm immutable view of Java source facts.

    Cross-file resolvers must use this view instead of independently walking
    the repository.  It is deliberately scoped to a GitRepo instance; the
    caller can discard the repo to obtain a fresh snapshot after edits.
    """

    paths: tuple[str, ...]
    texts: dict[str, str]
    classes: dict[str, tuple[Any, ...]]
    methods: dict[str, tuple[Any, ...]]
    fingerprint: tuple[tuple[str, int, int], ...]


class JavaProjectModel:
    def __init__(self, repo: Any):
        self.repo = repo
        self.modules: tuple[JavaModule, ...] = ()
        self.sources: tuple[JavaSourceLocation, ...] = ()
        self.dependencies: tuple[JavaModuleDependency, ...] = ()
        self._built = False

    def _tracked_paths(self) -> list[str]:
        try:
            return [path for path in self.repo.run("ls-files").splitlines() if path]
        except Exception:
            return sorted(
                str(path.relative_to(self.repo.root)).replace("\\", "/")
                for path in self.repo.root.rglob("*")
                if path.is_file()
            )

    def _read(self, path: str) -> str:
        try:
            return self.repo.read_file(path)
        except Exception:
            return ""

    @staticmethod
    def _parent(path: str) -> str:
        parent = str(PurePosixPath(path).parent)
        return "" if parent == "." else parent

    def _maven_module_roots(self, pom_path: str) -> set[str]:
        root = self._parent(pom_path)
        roots = {root}
        try:
            document = ET.fromstring(self._read(pom_path))
        except ET.ParseError:
            return roots
        for element in document.iter():
            if element.tag.rsplit("}", 1)[-1] != "module" or not element.text:
                continue
            module = element.text.strip().strip("/")
            if module and ".." not in PurePosixPath(module).parts:
                roots.add(str(PurePosixPath(root) / module) if root else module)
        return roots

    def _gradle_module_roots(self, settings_path: str) -> set[str]:
        root = self._parent(settings_path)
        roots = {root}
        text = self._read(settings_path)
        modules: set[str] = set()
        for match in re.finditer(r"(?m)^\s*include\s*(?:\((.*?)\)|(.*))$", text):
            payload = match.group(1) if match.group(1) is not None else match.group(2)
            modules.update(re.findall(r"['\"]:?(.*?)['\"]", payload or ""))
        for module in modules:
            path = module.replace(":", "/").strip("/")
            if path and ".." not in PurePosixPath(path).parts:
                roots.add(str(PurePosixPath(root) / path) if root else path)
        return roots

    @staticmethod
    def _xml_children_text(document: ET.Element, name: str) -> list[str]:
        return [
            element.text.strip()
            for element in document.iter()
            if element.tag.rsplit("}", 1)[-1] == name and element.text and element.text.strip()
        ]

    def _maven_coordinates(self, pom_path: str) -> tuple[str | None, str | None]:
        try:
            document = ET.fromstring(self._read(pom_path))
        except ET.ParseError:
            return None, None
        artifact = next((child.text.strip() for child in document if child.tag.rsplit("}", 1)[-1] == "artifactId" and child.text), None)
        group = next((child.text.strip() for child in document if child.tag.rsplit("}", 1)[-1] == "groupId" and child.text), None)
        if group is None:
            parent = next((child for child in document if child.tag.rsplit("}", 1)[-1] == "parent"), None)
            if parent is not None:
                group = next((child.text.strip() for child in parent if child.tag.rsplit("}", 1)[-1] == "groupId" and child.text), None)
        return group, artifact

    def _maven_dependencies(self, pom_path: str, coordinate_roots: dict[tuple[str | None, str], str]) -> list[JavaModuleDependency]:
        try:
            document = ET.fromstring(self._read(pom_path))
        except ET.ParseError:
            return []
        source_root = self._parent(pom_path)
        found: list[JavaModuleDependency] = []
        for dependency in (element for element in document.iter() if element.tag.rsplit("}", 1)[-1] == "dependency"):
            values = {
                child.tag.rsplit("}", 1)[-1]: child.text.strip()
                for child in dependency
                if child.text and child.text.strip()
            }
            artifact = values.get("artifactId")
            if not artifact:
                continue
            target = coordinate_roots.get((values.get("groupId"), artifact))
            if target is None:
                matches = {root for (group, name), root in coordinate_roots.items() if name == artifact}
                target = next(iter(matches)) if len(matches) == 1 else None
            if target is not None and target != source_root:
                found.append(JavaModuleDependency(source_root, target, values.get("scope", "compile"), "maven_literal_dependency"))
        return found

    def _gradle_dependencies(self, build_path: str, known_roots: set[str]) -> list[JavaModuleDependency]:
        source_root = self._parent(build_path)
        project_root = next((root for root in known_roots if not root), "")
        found: list[JavaModuleDependency] = []
        for match in re.finditer(r"(?m)^\s*(api|implementation|compileOnly|runtimeOnly|testImplementation)\s*\(?\s*project\s*\(\s*['\"](:[^'\"]+)['\"]\s*\)\s*\)?", self._read(build_path)):
            scope, project = match.groups()
            relative = project.lstrip(":").replace(":", "/")
            target = str(PurePosixPath(project_root) / relative) if project_root else relative
            if target in known_roots and target != source_root:
                found.append(JavaModuleDependency(source_root, target, scope, "gradle_literal_project_dependency"))
        return found

    @staticmethod
    def _module_name(root: str) -> str:
        return PurePosixPath(root).name if root else "root"

    @staticmethod
    def _classify(relative_path: str) -> tuple[str, bool]:
        parts = PurePosixPath(relative_path).parts
        if parts[:3] == ("src", "main", "java"):
            return "main", False
        if parts[:3] == ("src", "test", "java"):
            return "test", False
        if len(parts) >= 3 and parts[0] == "src" and parts[2] == "java":
            return parts[1], False
        if parts[:2] == ("target", "generated-sources") or parts[:3] == ("build", "generated", "sources"):
            return "generated", True
        return "unclassified", False

    def build(self) -> "JavaProjectModel":
        if self._built:
            return self
        paths = self._tracked_paths()
        descriptors = [path for path in paths if PurePosixPath(path).name in _BUILD_FILES | _SETTINGS_FILES]
        module_systems: dict[str, str] = {}
        for descriptor in descriptors:
            name = PurePosixPath(descriptor).name
            root = self._parent(descriptor)
            if name == "pom.xml":
                for module_root in self._maven_module_roots(descriptor):
                    module_systems.setdefault(module_root, "maven")
            elif name in _SETTINGS_FILES:
                for module_root in self._gradle_module_roots(descriptor):
                    module_systems.setdefault(module_root, "gradle")
            else:
                module_systems.setdefault(root, "gradle")
        if not module_systems:
            module_systems[""] = "unknown"
        modules = [JavaModule(self._module_name(root), root, system) for root, system in module_systems.items()]
        modules.sort(key=lambda item: (len(PurePosixPath(item.root).parts), item.root), reverse=True)
        sources: list[JavaSourceLocation] = []
        for path in paths:
            if not path.endswith(".java"):
                continue
            module = next(
                (item for item in modules if not item.root or path == item.root or path.startswith(item.root + "/")),
                JavaModule("root", "", "unknown"),
            )
            relative = path[len(module.root) + 1 :] if module.root else path
            source_set, generated = self._classify(relative)
            sources.append(JavaSourceLocation(path, module.name, module.root, source_set, generated))
        self.modules = tuple(sorted(modules, key=lambda item: item.root))
        self.sources = tuple(sorted(sources, key=lambda item: item.path))
        coordinates: dict[tuple[str | None, str], str] = {}
        for descriptor in descriptors:
            if PurePosixPath(descriptor).name == "pom.xml":
                group, artifact = self._maven_coordinates(descriptor)
                if artifact:
                    coordinates[(group, artifact)] = self._parent(descriptor)
        dependencies: list[JavaModuleDependency] = []
        known_roots = set(module_systems)
        for descriptor in descriptors:
            name = PurePosixPath(descriptor).name
            if name == "pom.xml":
                dependencies.extend(self._maven_dependencies(descriptor, coordinates))
            elif name in {"build.gradle", "build.gradle.kts"}:
                dependencies.extend(self._gradle_dependencies(descriptor, known_roots))
        self.dependencies = tuple(sorted(set(dependencies), key=lambda edge: (edge.source_root, edge.target_root, edge.scope)))
        self._built = True
        return self

    def java_paths(self) -> list[str]:
        return [source.path for source in self.build().sources]

    def source_for(self, path: str) -> JavaSourceLocation | None:
        return next((source for source in self.build().sources if source.path == path), None)


def java_project_model(repo: Any) -> JavaProjectModel:
    cached = getattr(repo, "_tmf_java_project_model", None)
    if cached is not None and getattr(repo, "_tmf_java_snapshot_pinned", False):
        return cached
    probe = JavaProjectModel(repo)
    relevant = [
        path for path in probe._tracked_paths()
        if path.endswith(".java") or PurePosixPath(path).name in _BUILD_FILES | _SETTINGS_FILES
    ]
    fingerprint = tuple(
        (path, (repo.root / path).stat().st_mtime_ns, (repo.root / path).stat().st_size)
        for path in relevant
        if (repo.root / path).is_file()
    )
    cached_fingerprint = getattr(repo, "_tmf_java_project_model_fingerprint", None)
    if cached is None or cached_fingerprint != fingerprint:
        cached = probe.build()
        setattr(repo, "_tmf_java_project_model", cached)
        setattr(repo, "_tmf_java_project_model_fingerprint", fingerprint)
    return cached


def java_repository_snapshot(repo: Any) -> JavaRepositorySnapshot:
    """Build and cache repository-wide Java facts once per repo instance."""
    from .java_extract import extract_java_classes, extract_java_methods

    cached = getattr(repo, "_tmf_java_repository_snapshot", None)
    if cached is not None and getattr(repo, "_tmf_java_snapshot_pinned", False):
        return cached
    model = java_project_model(repo)
    paths = tuple(model.java_paths())
    fingerprint = tuple(
        (path, (repo.root / path).stat().st_mtime_ns, (repo.root / path).stat().st_size)
        for path in paths
        if (repo.root / path).is_file()
    )
    if cached is not None and cached.fingerprint == fingerprint:
        return cached
    texts: dict[str, str] = {}
    classes: dict[str, tuple[Any, ...]] = {}
    methods: dict[str, tuple[Any, ...]] = {}
    for path in paths:
        try:
            text = repo.read_file(path)
            texts[path] = text
            try:
                classes[path] = tuple(extract_java_classes(path, text))
                methods[path] = tuple(extract_java_methods(path, text))
            except ImportError:
                # Preserve the existing Java parser degradation path: the
                # source cache remains useful, but no syntax facts are claimed.
                classes[path] = ()
                methods[path] = ()
        except (OSError, UnicodeError):
            continue
    snapshot = JavaRepositorySnapshot(paths, texts, classes, methods, fingerprint)
    setattr(repo, "_tmf_java_repository_snapshot", snapshot)
    return snapshot
