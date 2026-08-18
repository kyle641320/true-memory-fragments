from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath
from pathlib import Path
import hashlib
import json
import os
import re
import tempfile
import xml.etree.ElementTree as ET
from typing import Any, Iterator, Mapping

from .derivation_versions import JAVA_DERIVATION_VERSION


_BUILD_FILES = {"pom.xml", "build.gradle", "build.gradle.kts"}
_SETTINGS_FILES = {"settings.gradle", "settings.gradle.kts"}
_JAVA_SNAPSHOT_CACHE_VERSION = "java.snapshot.v1"


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


class _LazyTextMap(Mapping[str, str]):
    def __init__(self, snapshot: "JavaRepositorySnapshot") -> None:
        self.snapshot = snapshot
        self._cache: dict[str, str] = {}

    def __getitem__(self, path: str) -> str:
        if path not in self.snapshot._path_set:
            raise KeyError(path)
        if path not in self._cache:
            self._cache[path] = self.snapshot._read_pinned_text(path)
            self.snapshot.loaded_text_count += 1
        return self._cache[path]

    def __iter__(self) -> Iterator[str]:
        return iter(self.snapshot.paths)

    def __len__(self) -> int:
        return len(self.snapshot.paths)

    def __contains__(self, path: object) -> bool:
        return path in self.snapshot._path_set


class _LazyNodeMap(Mapping[str, tuple[Any, ...]]):
    def __init__(self, snapshot: "JavaRepositorySnapshot", kind: str) -> None:
        self.snapshot = snapshot
        self.kind = kind

    def __getitem__(self, path: str) -> tuple[Any, ...]:
        if path not in self.snapshot._path_set:
            raise KeyError(path)
        return self.snapshot._nodes(path)[0 if self.kind == "classes" else 1]

    def __iter__(self) -> Iterator[str]:
        return iter(self.snapshot.paths)

    def __len__(self) -> int:
        return len(self.snapshot.paths)

    def __contains__(self, path: object) -> bool:
        return path in self.snapshot._path_set


class JavaRepositorySnapshot:
    """A pinned repository view whose source and syntax facts load per file.

    ``paths`` and worktree blob identities are fixed at construction. Source
    text remains authoritative and is read only on access. Parsed class/method
    facts use path+blob+schema+derivation-version shards; shards never contain
    source text. A compact symbol manifest lets ordinary type resolution avoid
    opening every per-file shard on later processes.
    """

    def __init__(self, repo: Any, paths: tuple[str, ...], blobs: dict[str, str | None], fingerprint: tuple[tuple[str, int, int], ...]) -> None:
        self.repo = repo
        self.paths = paths
        self.blobs = dict(blobs)
        self.fingerprint = fingerprint
        self._path_set = frozenset(paths)
        self._parsed: dict[str, tuple[tuple[Any, ...], tuple[Any, ...]]] = {}
        self.texts: Mapping[str, str] = _LazyTextMap(self)
        self.classes: Mapping[str, tuple[Any, ...]] = _LazyNodeMap(self, "classes")
        self.methods: Mapping[str, tuple[Any, ...]] = _LazyNodeMap(self, "methods")
        self.loaded_text_count = 0
        self.loaded_shard_count = 0
        self.parsed_source_count = 0
        self._manifest_symbols: list[dict[str, Any]] | None = None

    @property
    def cache_dir(self) -> Path:
        return Path(self.repo.root) / ".tmf" / "java_snapshot" / _JAVA_SNAPSHOT_CACHE_VERSION

    @property
    def manifest_path(self) -> Path:
        return self.cache_dir / "manifest.json"

    def _shard(self, path: str) -> Path:
        return self.cache_dir / (hashlib.sha256(path.encode("utf-8")).hexdigest() + ".json")

    def _verify_pinned_blob(self, path: str) -> None:
        if self.repo.blob_sha(path) != self.blobs.get(path):
            raise OSError(f"Java source changed after snapshot creation: {path}")

    def _verify_all_pinned_blobs(self) -> None:
        current = self.repo.blob_shas(self.paths)
        for path in self.paths:
            if current.get(path) != self.blobs.get(path):
                raise OSError(f"Java source changed after snapshot creation: {path}")

    def _read_pinned_text(self, path: str) -> str:
        """Read source only if it still matches this snapshot's pinned blob.

        Lazy loading creates a gap between snapshot construction and first
        access. Refuse to combine bytes from a later worktree state with the
        earlier blob identity; the caller can create a fresh GitRepo/snapshot.
        """
        expected = self.blobs.get(path)
        self._verify_pinned_blob(path)
        text = self.repo.read_file(path)
        if self.repo.blob_sha(path) != expected:
            raise OSError(f"Java source changed while snapshot was reading: {path}")
        return text

    def _nodes(self, path: str) -> tuple[tuple[Any, ...], tuple[Any, ...]]:
        cached = self._parsed.get(path)
        if cached is not None:
            return cached
        # Validate even on a shard hit: lazy access must never expose facts
        # for the pinned blob after the worktree has moved to different bytes.
        self._verify_pinned_blob(path)
        from .extract import ClassNode
        from .java_extract import extract_java_classes, extract_java_methods
        blob = self.blobs.get(path)
        shard = self._shard(path)
        try:
            payload = json.loads(shard.read_text(encoding="utf-8"))
            if not (
                payload.get("version") == _JAVA_SNAPSHOT_CACHE_VERSION
                and payload.get("derivation_version") == JAVA_DERIVATION_VERSION
                and payload.get("path") == path
                and payload.get("blob") == blob
                and "text" not in payload
            ):
                raise ValueError("stale Java snapshot shard")
            result = (
                tuple(ClassNode(**item) for item in payload["classes"]),
                tuple(ClassNode(**item) for item in payload["methods"]),
            )
            self.loaded_shard_count += 1
        except (OSError, UnicodeError, json.JSONDecodeError, AttributeError, KeyError, TypeError, ValueError):
            text = self.texts[path]
            try:
                result = (tuple(extract_java_classes(path, text)), tuple(extract_java_methods(path, text)))
            except ImportError:
                result = ((), ())
            self.parsed_source_count += 1
            serialized = {
                "version": _JAVA_SNAPSHOT_CACHE_VERSION,
                "derivation_version": JAVA_DERIVATION_VERSION,
                "path": path,
                "blob": blob,
                "classes": [item.__dict__ for item in result[0]],
                "methods": [item.__dict__ for item in result[1]],
            }
            self._atomic_json(shard, serialized)
        self._parsed[path] = result
        return result

    def _atomic_json(self, path: Path, payload: Any) -> None:
        temporary: Path | None = None
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, prefix=".tmp-", delete=False) as handle:
                temporary = Path(handle.name)
                json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
                handle.flush(); os.fsync(handle.fileno())
            os.replace(temporary, path)
        except OSError:
            if temporary is not None:
                temporary.unlink(missing_ok=True)

    @staticmethod
    def _valid_manifest_symbol(item: Any, paths: frozenset[str]) -> bool:
        if not isinstance(item, dict) or item.get("path") not in paths:
            return False
        required_strings = ("fqn", "simple_name", "path", "package", "module", "source_set")
        return all(isinstance(item.get(key), str) for key in required_strings) and isinstance(item.get("generated"), bool)

    def symbol_manifest(self) -> list[dict[str, Any]]:
        # A compact manifest is another lazy facts cache, so it must obey the
        # same pinned-source invariant as per-file shards on every access.
        self._verify_all_pinned_blobs()
        if self._manifest_symbols is not None:
            return self._manifest_symbols
        expected = {path: self.blobs.get(path) for path in self.paths}
        reusable_blobs: dict[str, Any] = {}
        reusable_by_path: dict[str, list[dict[str, Any]]] = {}
        try:
            payload = json.loads(self.manifest_path.read_text(encoding="utf-8"))
            if (
                payload.get("version") == _JAVA_SNAPSHOT_CACHE_VERSION
                and payload.get("derivation_version") == JAVA_DERIVATION_VERSION
                and isinstance(payload.get("blobs"), dict)
                and isinstance(payload.get("symbols"), list)
                and all(self._valid_manifest_symbol(item, self._path_set) for item in payload["symbols"])
            ):
                reusable_blobs = payload["blobs"]
                for item in payload["symbols"]:
                    reusable_by_path.setdefault(item["path"], []).append(item)
                if reusable_blobs == expected:
                    self._manifest_symbols = payload["symbols"]
                    return self._manifest_symbols
        except (OSError, UnicodeError, json.JSONDecodeError, AttributeError):
            pass
        package_re = re.compile(r"(?m)^\s*package\s+([A-Za-z_][\w.]*)\s*;")
        symbols: list[dict[str, Any]] = []
        model = java_project_model(self.repo)
        for path in self.paths:
            if reusable_blobs.get(path) == expected[path] and path in reusable_blobs:
                symbols.extend(reusable_by_path.get(path, ()))
                continue
            text = self.texts.get(path)
            if text is None:
                continue
            package_match = package_re.search(text)
            package = package_match.group(1) if package_match else ""
            location = model.source_for(path)
            for node in self.classes.get(path, ()):
                if node.node_kind not in {"class", "interface", "enum", "record"} or "." in node.qualname:
                    continue
                simple = node.qualname
                symbols.append({
                    "fqn": f"{package}.{simple}" if package else simple,
                    "simple_name": simple, "path": path, "package": package,
                    "module": location.module if location else "root",
                    "source_set": location.source_set if location else "unclassified",
                    "generated": location.generated if location else False,
                })
        self._manifest_symbols = symbols
        self._atomic_json(self.manifest_path, {
            "version": _JAVA_SNAPSHOT_CACHE_VERSION,
            "derivation_version": JAVA_DERIVATION_VERSION,
            "blobs": expected,
            "symbols": symbols,
        })
        return symbols

    def cleanup_stale_shards(self) -> None:
        if not self.cache_dir.is_dir():
            return
        active = {self._shard(path) for path in self.paths}
        for stale in self.cache_dir.glob("*.json"):
            if stale.name != "manifest.json" and stale not in active:
                try: stale.unlink()
                except OSError: pass


class JavaProjectModel:
    def __init__(self, repo: Any):
        self.repo = repo
        self.modules: tuple[JavaModule, ...] = ()
        self.sources: tuple[JavaSourceLocation, ...] = ()
        self.dependencies: tuple[JavaModuleDependency, ...] = ()
        self._built = False

    def _tracked_paths(self) -> list[str]:
        try:
            return self.repo.ls_files()
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
    """Create a pinned lazy Java view without reading or parsing source files."""
    cached = getattr(repo, "_tmf_java_repository_snapshot", None)
    if cached is not None and getattr(repo, "_tmf_java_snapshot_pinned", False):
        return cached
    model = java_project_model(repo)
    paths = tuple(model.java_paths())
    fingerprint = tuple(
        (path, (repo.root / path).stat().st_mtime_ns, (repo.root / path).stat().st_size)
        for path in paths if (repo.root / path).is_file()
    )
    if cached is not None and cached.fingerprint == fingerprint:
        return cached
    blobs = repo.blob_shas(paths) if hasattr(repo, "blob_shas") else {path: repo.blob_sha(path) for path in paths}
    snapshot = JavaRepositorySnapshot(repo, paths, blobs, fingerprint)
    snapshot.cleanup_stale_shards()
    setattr(repo, "_tmf_java_repository_snapshot", snapshot)
    return snapshot
