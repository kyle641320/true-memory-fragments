"""Offline, frozen fixture and production freshness chain for the M10 successor.

No legacy runner or model adapter is imported here.  The semantic memory is a
separately frozen, bounded source observation; TMF's production structural claim
supplies its source binding, not a proof of that memory's semantic truth.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable
from unittest.mock import patch

from tmf.derive import derive_claims_for_path
from tmf.derivation_versions import versions_for_path
from tmf.freshness import Freshness, check_freshness
from tmf.git import GitRepo
from tmf.java_extract import _language_and_parser
from tmf.schema import Claim

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
GUAVA = ROOT / "bench" / "agent_ab" / "guava_cognitive_v1"
SPEC_PATH = HERE / "m10_successor_fixture_spec.json"
FILE = "Dispatcher.java"
PKG_FILES = (
    "AllowConcurrentEvents.java", "AsyncEventBus.java", "DeadEvent.java",
    FILE, "EventBus.java", "ParametricNullness.java", "Subscribe.java",
    "Subscriber.java", "SubscriberExceptionContext.java",
    "SubscriberExceptionHandler.java", "SubscriberRegistry.java",
)
TARGET_QUALNAME = "Dispatcher.PerThreadQueuedDispatcher.dispatch"
CONTROL_QUALNAME = "Dispatcher.ImmediateDispatcher.dispatch"
TARGET_NODE_KIND = "method"
TARGET_BINDING_ROLE = "declaration"
FROZEN_TIMESTAMP = "2026-09-18T00:00:00+00:00"

OLD_SNIPPET = """            while (nextEvent.subscribers.hasNext()) {
              nextEvent.subscribers.next().dispatchEvent(nextEvent.event);
            }"""
NEW_SNIPPET = """            while (nextEvent.subscribers.hasNext()) {
              Subscriber nextSubscriber = nextEvent.subscribers.next();
              dispatchQueuedSubscriber(nextEvent.event, nextSubscriber);
            }"""
HELPER_INSERT_AFTER = """    private static final class Event {
      private final Object event;"""
HELPER_BLOCK = """    private void dispatchQueuedSubscriber(Object event, Subscriber subscriber) {
      dispatchPreparedSubscriber(new EventWithPreparedSubscriber(event, subscriber));
    }

    private void dispatchPreparedSubscriber(EventWithPreparedSubscriber prepared) {
      prepared.subscriber.dispatchEvent(prepared.event);
    }

    private void hook() {}

    private static final class EventWithPreparedSubscriber {
      private final Object event;
      private final Subscriber subscriber;

      private EventWithPreparedSubscriber(Object event, Subscriber subscriber) {
        this.event = event;
        this.subscriber = subscriber;
      }
    }

    private static final class Event {
      private final Object event;"""


class PreflightInvariantError(RuntimeError):
    """The preregistered deterministic contract was not satisfied."""


def canonical_json(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":"))


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def load_fixture_spec() -> dict[str, Any]:
    spec = json.loads(SPEC_PATH.read_text(encoding="utf-8"))
    if spec.get("schema") != "guava-m10-successor-frozen-fixture-v1":
        raise PreflightInvariantError("unsupported frozen fixture specification")
    if tuple(spec["files"]) != PKG_FILES:
        raise PreflightInvariantError("frozen file allowlist differs from implementation")
    for phase in ("t0", "t1"):
        if set(spec["file_sha256"][phase]) != set(PKG_FILES):
            raise PreflightInvariantError(f"incomplete {phase} frozen file manifest")
    if spec["mutation"]["changed_files"] != [FILE]:
        raise PreflightInvariantError("mutation allowlist must contain only Dispatcher.java")
    return spec


def source_base() -> Path:
    return GUAVA / "fixtures" / "B03" / "base"


def fixture_hashes(root: Path) -> dict[str, str]:
    root = Path(root)
    files = {
        p.relative_to(root).as_posix()
        for p in root.rglob("*")
        # Production Java derivation can populate its snapshot cache.  It is
        # preflight-local metadata, never copied by prepare_fixture/arm tools.
        if p.relative_to(root).parts[0] != ".git"
        and p.relative_to(root).parts[:2] != (".tmf", "java_snapshot")
        and (p.is_file() or p.is_symlink())
    }
    if files != set(PKG_FILES):
        raise PreflightInvariantError(f"fixture file allowlist mismatch: {sorted(files)!r}")
    if any((root / name).is_symlink() for name in PKG_FILES):
        raise PreflightInvariantError("fixture source files must not be symlinks")
    return {name: sha256_bytes((root / name).read_bytes()) for name in PKG_FILES}


def validate_fixture(root: Path, phase: str) -> dict[str, str]:
    if phase not in {"t0", "t1"}:
        raise ValueError("phase must be t0 or t1")
    observed = fixture_hashes(root)
    expected = load_fixture_spec()["file_sha256"][phase]
    if observed != expected:
        changed = [name for name in PKG_FILES if observed[name] != expected[name]]
        raise PreflightInvariantError(f"{phase} fixture differs from frozen bytes: {changed!r}")
    return observed


def mutation_diff(before: str, after: str) -> str:
    return "".join(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile=f"a/{FILE}", tofile=f"b/{FILE}", n=3,
    ))


def mutate_dispatcher(source: str) -> str:
    spec = load_fixture_spec()
    if sha256_text(source) != spec["file_sha256"]["t0"][FILE]:
        raise PreflightInvariantError("mutation input is not frozen T0 Dispatcher.java")
    if source.count(OLD_SNIPPET) != 1 or source.count(HELPER_INSERT_AFTER) != 1:
        raise PreflightInvariantError("mutation anchors are not unique")
    result = source.replace(OLD_SNIPPET, NEW_SNIPPET).replace(HELPER_INSERT_AFTER, HELPER_BLOCK)
    if sha256_text(result) != spec["file_sha256"]["t1"][FILE]:
        raise PreflightInvariantError("mutation output differs from frozen T1 Dispatcher.java")
    if mutation_diff(source, result) != spec["mutation"]["unified_diff"]:
        raise PreflightInvariantError("mutation is not the exact frozen diff")
    return result


def prepare_fixture(dest: Path, phase: str = "t1") -> dict[str, Any]:
    """Create only the eleven model-visible files, then verify frozen bytes.

    Existing nonempty destinations are refused, never removed.  T0 git metadata
    is initialized separately by the preflight and is never copied to an arm.
    """
    dest = Path(dest)
    if phase not in {"t0", "t1"}:
        raise ValueError("phase must be t0 or t1")
    dest.mkdir(parents=True, exist_ok=True)
    if any(dest.iterdir()):
        raise PreflightInvariantError("fixture destination must be empty")
    for name in PKG_FILES:
        path = dest / name
        path.write_bytes((source_base() / name).read_bytes())
        path.chmod(0o644)
    validate_fixture(dest, "t0")
    if phase == "t1":
        old = (dest / FILE).read_text(encoding="utf-8")
        (dest / FILE).write_text(mutate_dispatcher(old), encoding="utf-8")
    hashes = validate_fixture(dest, phase)
    return {"phase": phase, "file_sha256": hashes, "fixture_sha256": sha256_text(canonical_json(hashes))}


def _init_git(root: Path) -> None:
    # A fixed identity, clock, branch, object format, and modes make the *whole*
    # production claim reproducible, including its otherwise-volatile commit.
    env = dict(os.environ)
    for name in tuple(env):
        if name.startswith("GIT_"):
            del env[name]
    env.update({
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_AUTHOR_NAME": "M10 Successor Fixture", "GIT_COMMITTER_NAME": "M10 Successor Fixture",
        "GIT_AUTHOR_EMAIL": "m10-successor@example.invalid", "GIT_COMMITTER_EMAIL": "m10-successor@example.invalid",
        "GIT_AUTHOR_DATE": FROZEN_TIMESTAMP, "GIT_COMMITTER_DATE": FROZEN_TIMESTAMP,
    })
    commands = (
        ("init", "-q", "--initial-branch=fixture", "--object-format=sha1"),
        ("add", "--", *PKG_FILES),
        ("-c", "core.hooksPath=/dev/null", "-c", "commit.gpgSign=false", "commit", "-qm", "Frozen M10 successor T0"),
    )
    for command in commands:
        subprocess.run(("git", *command), cwd=root, env=env, check=True,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=30)


def _walk(node: Any) -> Iterable[Any]:
    yield node
    for child in node.named_children:
        yield from _walk(child)


def _text(source: bytes, node: Any) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8")


def _qualified_method(source: bytes, node: Any) -> str:
    parts = []
    current = node
    while current is not None:
        if current.type in {"class_declaration", "method_declaration"}:
            name = current.child_by_field_name("name")
            if name is not None:
                parts.append(_text(source, name))
        current = current.parent
    return ".".join(reversed(parts))


def verify_t0_boundary(source: str) -> dict[str, Any]:
    """Independently check only Dispatcher -> Subscriber.dispatchEvent.

    Subscriber.dispatchEvent itself still performs executor and reflection work;
    this assertion is deliberately NOT the final framework -> user callback.
    """
    data = source.encode("utf-8")
    _, parser = _language_and_parser()
    tree = parser.parse(data)
    if tree.root_node.has_error:
        raise PreflightInvariantError("T0 source is not valid Java syntax")
    methods = [node for node in _walk(tree.root_node)
               if node.type == "method_declaration" and _qualified_method(data, node) == TARGET_QUALNAME]
    if len(methods) != 1:
        raise PreflightInvariantError("T0 target method is not unique")
    method = methods[0]
    calls = [node for node in _walk(method) if node.type == "method_invocation"
             and (name := node.child_by_field_name("name")) is not None and _text(data, name) == "dispatchEvent"]
    expected_call = "nextEvent.subscribers.next().dispatchEvent(nextEvent.event)"
    if len(calls) != 1 or _text(data, calls[0]) != expected_call:
        raise PreflightInvariantError("T0 semantic memory's direct handoff is false or ambiguous")
    ancestors = []
    current = calls[0].parent
    while current is not None and current != method:
        ancestors.append(current.type)
        current = current.parent
    if ancestors.count("while_statement") != 2:
        raise PreflightInvariantError("T0 direct handoff is not in the frozen nested queue-drain loops")
    class_node = method.parent.parent
    if class_node.type != "class_declaration":
        raise PreflightInvariantError("T0 target class shape changed")
    return {
        "method": TARGET_QUALNAME,
        "call_expression": expected_call,
        "dispatch_event_calls_in_method": 1,
        "enclosing_while_loops": 2,
        "source_snapshot": _text(data, class_node),
        "scope": "Dispatcher implementation to Subscriber.dispatchEvent; not the final user-callback boundary",
        "validation": "independent-tree-sitter-bounded-source-fact",
    }


def _select_java_method_claim(claims: Iterable[Claim], qualname: str) -> Claim:
    matches = [claim for claim in claims
               if claim.body.get("language") == "java"
               and claim.body.get("qualname") == qualname
               and claim.body.get("node_kind") == TARGET_NODE_KIND
               and len(claim.bindings) == 1
               and claim.bindings[0].role == TARGET_BINDING_ROLE]
    if len(matches) != 1:
        raise PreflightInvariantError(f"production method claim is not unique: {qualname}")
    claim = matches[0]
    if claim.body.get("derivation_versions") != versions_for_path(FILE):
        raise PreflightInvariantError("production derivation version metadata is missing or incorrect")
    return claim


def derive_t0_claim(repo: GitRepo) -> tuple[Claim, Claim]:
    # Only the acquisition clock is injected.  Claim contents, source bindings,
    # derivation versions, and verification are produced by the production path;
    # no claim field is rewritten or removed after derivation.
    with patch("tmf.derive.now_utc", return_value=FROZEN_TIMESTAMP):
        claims = derive_claims_for_path(repo, FILE, use_model=False)
    return (_select_java_method_claim(claims, TARGET_QUALNAME),
            _select_java_method_claim(claims, CONTROL_QUALNAME))


@dataclass(frozen=True)
class BoundMemory:
    schema: str
    claim_json: str
    payload_json: str
    t0_fact_proof_json: str

    @property
    def claim_sha256(self) -> str:
        return sha256_text(self.claim_json)

    @property
    def payload_sha256(self) -> str:
        return sha256_text(self.payload_json)

    @property
    def memory_sha256(self) -> str:
        return sha256_text(canonical_json(asdict(self)))

    @property
    def payload(self) -> dict[str, Any]:
        return json.loads(self.payload_json)


def frozen_bound_memory() -> BoundMemory:
    return BoundMemory(**load_fixture_spec()["bound_memory"])


def _validate_bound_memory(memory: BoundMemory | dict[str, Any]) -> BoundMemory:
    try:
        value = BoundMemory(**memory) if isinstance(memory, dict) else memory
        if not isinstance(value, BoundMemory) or asdict(value) != load_fixture_spec()["bound_memory"]:
            raise PreflightInvariantError("bound memory differs from the frozen production claim/payload")
        for serialized in (value.claim_json, value.payload_json, value.t0_fact_proof_json):
            if canonical_json(json.loads(serialized)) != serialized:
                raise PreflightInvariantError("bound memory is not canonical JSON")
        Claim.from_dict(json.loads(value.claim_json))
        return value
    except (ValueError, KeyError, TypeError) as exc:
        raise PreflightInvariantError("invalid bound memory artifact") from exc


@dataclass(frozen=True)
class GateDecision:
    fresh: bool
    stale_bindings: tuple[str, ...]
    payload: dict[str, Any] | None
    receipt: dict[str, Any] | None
    memory_sha256: str
    claim_sha256: str
    source_sha256: str | None


def evaluate_bound_memory(root: Path, memory: BoundMemory | dict[str, Any]) -> GateDecision:
    """A real freshness call, not arm-name dispatch, controls memory admission."""
    bound = _validate_bound_memory(memory)
    claim = Claim.from_dict(json.loads(bound.claim_json))
    try:
        freshness = check_freshness(GitRepo(root), claim)
        fresh = freshness.fresh and not freshness.stale_bindings
        reasons = tuple(freshness.stale_bindings)
        status = "stale_payload_withheld"
    except Exception as exc:
        # Unknown validity fails closed.  The preflight separately rejects this
        # result because it requires exactly the intended java_hash mismatch.
        fresh = False
        reasons = (f"freshness unavailable: {type(exc).__name__}",)
        status = "unknown_payload_withheld"
    source = Path(root) / FILE
    digest = sha256_bytes(source.read_bytes()) if source.is_file() else None
    receipt = None if fresh else {"status": status, "changed_bindings": list(reasons), "payload": None}
    return GateDecision(fresh, reasons, bound.payload if fresh else None, receipt,
                        bound.memory_sha256, bound.claim_sha256, digest)


def _compiler_classpath() -> tuple[list[Path], str]:
    override = os.environ.get("TMF_M10_SUCCESSOR_CLASSPATH")
    entries = (override if override is not None else
               (GUAVA / "classpath.txt").read_text(encoding="utf-8").strip()).split(os.pathsep)
    if not entries or any(not item for item in entries):
        raise PreflightInvariantError("empty compiler classpath entry")
    resolved = []
    for entry in entries:
        candidate = Path(entry)
        candidate = candidate if candidate.is_absolute() else GUAVA / candidate
        if override is None and "/.m2/repository/" in entry:
            # The historical classpath contains a developer's home.  Relocate
            # the known Maven prefix *before* probing another user's home:
            # is_file() raises PermissionError on older supported Pythons.
            # Never search/download or silently reinterpret an explicit override.
            candidate = Path.home() / ".m2" / "repository" / entry.split("/.m2/repository/", 1)[1]
        if not candidate.is_file() or candidate.suffix != ".jar":
            raise PreflightInvariantError(f"required offline classpath jar missing: {candidate.name}")
        resolved.append(candidate.resolve())
    return resolved, ("environment:TMF_M10_SUCCESSOR_CLASSPATH" if override is not None else
                      "bench/agent_ab/guava_cognitive_v1/classpath.txt")


def compiler_environment() -> dict[str, Any]:
    """Inventory and verify the actual offline compiler/classpath, no download."""
    entries, source = _compiler_classpath()
    jars = []
    for candidate in entries:
        jars.append({"name": candidate.name, "sha256": sha256_bytes(candidate.read_bytes()),
                     "size_bytes": candidate.stat().st_size})
    if jars != load_fixture_spec()["compiler_classpath_jars"]:
        raise PreflightInvariantError("actual compiler classpath differs from frozen jar identities/order")
    javac, jdk, env = _compiler_runtime()
    version = subprocess.run((str(javac), "-version"), check=True, text=True, env=env,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=10)
    # javac is only a launcher: bind compiler classes, native runtime and conf.
    # Symlink targets are hashed, not their installation-specific absolute paths.
    runtime_paths = {jdk / "release", javac, jdk / "bin/java"}
    for directory in (jdk / "lib", jdk / "conf"):
        runtime_paths.update(path for path in directory.rglob("*") if path.is_file())
    runtime_files = {path.relative_to(jdk).as_posix(): _sha256_file(path)
                     for path in sorted(runtime_paths)}
    # Absolute paths are excluded from the stable seal; dependency identity and
    # order are preserved by names+content digests and the classpath-file digest.
    return {
        "classpath_source": source,
        "classpath_file_sha256": sha256_bytes((GUAVA / "classpath.txt").read_bytes()),
        "classpath_jars": jars,
        "javac_version": (version.stdout + version.stderr).strip(),
        "javac_binary_sha256": _sha256_file(javac),
        "jdk_runtime_files_sha256": runtime_files,
        "compiler_environment": {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC",
                                 "PATH": "<jdk>/bin", "inherit_other_variables": False},
        "javac_flags": ["-nowarn", "-proc:none", "-encoding", "UTF-8", "-implicit:none"],
    }


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _compiler_runtime() -> tuple[Path, Path, dict[str, str]]:
    executable = shutil.which("javac")
    if executable is None:
        raise PreflightInvariantError("javac is unavailable")
    javac = Path(executable).resolve()
    jdk = javac.parent.parent
    if os.name != "posix" or any(not (jdk / name).is_file()
                                 for name in ("release", "lib/modules", "bin/java")):
        raise PreflightInvariantError("a complete modular POSIX JDK runtime image is required")
    # No inherited Java/loader flags, CLASSPATH, user profile or locale variables.
    env = {"PATH": str(jdk / "bin"), "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "TZ": "UTC"}
    return javac, jdk, env


def compile_check(root: Path) -> dict[str, Any]:
    """Compilation is measured independently of semantic scoring."""
    root = Path(root).resolve()
    env_info = compiler_environment()
    javac, _, compiler_env = _compiler_runtime()
    classpath = os.pathsep.join(str(entry) for entry in _compiler_classpath()[0])
    with tempfile.TemporaryDirectory(prefix="m10-successor-javac-") as output:
        try:
            result = subprocess.run(
                (str(javac), *env_info["javac_flags"], "-cp", classpath,
                 "-sourcepath", str(root), "-d", output, *PKG_FILES),
                cwd=root, env=compiler_env, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=90,
            )
            code, stdout, stderr = result.returncode, result.stdout, result.stderr
        except subprocess.TimeoutExpired:
            code, stdout, stderr = 124, "", "javac timeout"
        def redacted(value: str) -> str:
            value = value.replace(str(root), "<workspace>").replace(output, "<class-output>")
            for entry in classpath.split(os.pathsep):
                value = value.replace(entry, f"<classpath>/{Path(entry).name}")
            return value
        return {"ok": code == 0, "exit": code, "stdout": redacted(stdout)[-1000:],
                "stderr": redacted(stderr)[-4000:]}


def _freshness_dict(value: Freshness) -> dict[str, Any]:
    return {"fresh": value.fresh, "stale_bindings": list(value.stale_bindings)}


@dataclass(frozen=True)
class FreshnessPreflight:
    claim_id: str
    claim_sha256: str
    fixture_sha256_t0: str
    fixture_sha256_t1: str
    mutation_diff_sha256: str
    t0: dict[str, Any]
    t1: dict[str, Any]
    control_t0: dict[str, Any]
    control_t1: dict[str, Any]
    compile_t0: dict[str, Any]
    compile_t1: dict[str, Any]
    files_t0: dict[str, str]
    files_t1: dict[str, str]
    mutation_diff: str
    bound_memory: BoundMemory
    control_claim_json: str
    gate_t0: dict[str, Any]
    gate_t1: dict[str, Any]
    compiler: dict[str, Any]
    specification_sha256: str
    reproducibility: dict[str, Any]


def validate_preflight(preflight: FreshnessPreflight) -> dict[str, bool]:
    """Reject altered/incomplete observations before a parent seals any plan.

    This validates the offline artifact, not a signature or a license for model
    execution.  New runs must still execute ``run_freshness_preflight`` first.
    """
    spec = load_fixture_spec()
    memory = _validate_bound_memory(preflight.bound_memory)
    if (preflight.claim_id != json.loads(memory.claim_json)["id"]
            or preflight.claim_sha256 != memory.claim_sha256
            or preflight.control_claim_json != spec["control_claim_json"]):
        raise PreflightInvariantError("preflight complete claims do not match frozen claims")
    for phase, files, digest in (
        ("t0", preflight.files_t0, preflight.fixture_sha256_t0),
        ("t1", preflight.files_t1, preflight.fixture_sha256_t1),
    ):
        if files != spec["file_sha256"][phase] or digest != sha256_text(canonical_json(files)):
            raise PreflightInvariantError(f"preflight {phase} fixture hash manifest is not frozen")
    if (preflight.mutation_diff != spec["mutation"]["unified_diff"]
            or preflight.mutation_diff_sha256 != spec["mutation"]["unified_diff_sha256"]
            or preflight.mutation_diff_sha256 != sha256_text(preflight.mutation_diff)):
        raise PreflightInvariantError("preflight mutation differs from frozen exact diff")
    expected_fresh = {"fresh": True, "stale_bindings": []}
    reason = f"{FILE}:{TARGET_QUALNAME}: java_hash mismatch"
    expected_stale = {"fresh": False, "stale_bindings": [reason]}
    if (preflight.t0 != expected_fresh or preflight.t1 != expected_stale
            or preflight.control_t0 != expected_fresh or preflight.control_t1 != expected_fresh):
        raise PreflightInvariantError("preflight freshness chain/control is invalid")
    expected_gate_t0 = GateDecision(True, (), memory.payload, None, memory.memory_sha256,
                                   memory.claim_sha256, preflight.files_t0[FILE])
    expected_gate_t1 = GateDecision(False, (reason,), None,
                                   {"status": "stale_payload_withheld", "changed_bindings": [reason], "payload": None},
                                   memory.memory_sha256, memory.claim_sha256, preflight.files_t1[FILE])
    if (canonical_json(preflight.gate_t0) != canonical_json(asdict(expected_gate_t0))
            or canonical_json(preflight.gate_t1) != canonical_json(asdict(expected_gate_t1))):
        raise PreflightInvariantError("preflight gate decisions are detached from the same frozen memory")
    for compilation in (preflight.compile_t0, preflight.compile_t1):
        if compilation.get("ok") is not True or compilation.get("exit") != 0:
            raise PreflightInvariantError("preflight does not report both phases compiled successfully")
    if preflight.compiler != compiler_environment():
        raise PreflightInvariantError("preflight compiler inventory differs from actual offline environment")
    if preflight.specification_sha256 != sha256_bytes(SPEC_PATH.read_bytes()):
        raise PreflightInvariantError("preflight references a different frozen specification")
    expected_reproducibility = {
        "claim_clock": FROZEN_TIMESTAMP, "claim_clock_injection": "tmf.derive.now_utc",
        "claim_field_normalization": "none; full production Claim serialized with sorted canonical JSON",
        "git_commit": json.loads(memory.claim_json)["bindings"][0]["commit"],
        "git_identity_and_time": "fixed in fixture builder", "temporary_paths_included": False,
    }
    if preflight.reproducibility != expected_reproducibility:
        raise PreflightInvariantError("preflight reproducibility metadata changed")
    return {"full_fixture_and_claims": True, "sole_stale_cause": True,
            "control_fresh": True, "actual_gate_chain": True, "independent_compile": True}


def run_freshness_preflight(work_root: Path | None = None) -> FreshnessPreflight:
    owned = work_root is None
    root = Path(tempfile.mkdtemp(prefix="m10-successor-preflight-")) if owned else Path(work_root)
    try:
        prepare_fixture(root, phase="t0")
        _init_git(root)
        spec = load_fixture_spec()
        files_t0 = validate_fixture(root, "t0")
        source_t0 = (root / FILE).read_text(encoding="utf-8")
        proof = verify_t0_boundary(source_t0)
        repo = GitRepo(root)
        claim, control = derive_t0_claim(repo)
        memory = frozen_bound_memory()
        if canonical_json(claim.to_dict()) != memory.claim_json:
            raise PreflightInvariantError("derived target claim differs from frozen complete production claim")
        control_json = canonical_json(control.to_dict())
        if control_json != spec["control_claim_json"]:
            raise PreflightInvariantError("derived control claim differs from frozen complete production claim")
        if canonical_json(proof) != memory.t0_fact_proof_json:
            raise PreflightInvariantError("independent T0 semantic fact proof differs from frozen proof")
        if memory.payload["source_snapshot"] != proof["source_snapshot"]:
            raise PreflightInvariantError("semantic memory payload is detached from verified T0 source")
        t0, control_t0 = check_freshness(repo, claim), check_freshness(repo, control)
        if not t0.fresh or t0.stale_bindings or not control_t0.fresh or control_t0.stale_bindings:
            raise PreflightInvariantError("target and control must both be production-FRESH at T0")
        gate_t0 = evaluate_bound_memory(root, memory)
        if not gate_t0.fresh or gate_t0.payload != memory.payload or gate_t0.receipt is not None:
            raise PreflightInvariantError("T0 FRESH gate did not admit the exact memory payload")
        compile_t0 = compile_check(root)
        if not compile_t0["ok"]:
            raise PreflightInvariantError(f"T0 fixture failed compilation: {compile_t0}")
        source_t1 = mutate_dispatcher(source_t0)
        (root / FILE).write_text(source_t1, encoding="utf-8")
        files_t1 = validate_fixture(root, "t1")
        changes = [name for name in PKG_FILES if files_t0[name] != files_t1[name]]
        diff = mutation_diff(source_t0, source_t1)
        if changes != [FILE] or diff != spec["mutation"]["unified_diff"]:
            raise PreflightInvariantError("mutation violated the exact frozen allowlist/diff")
        t1, control_t1 = check_freshness(repo, claim), check_freshness(repo, control)
        expected_reason = f"{FILE}:{TARGET_QUALNAME}: java_hash mismatch"
        if t1.fresh or t1.stale_bindings != [expected_reason]:
            raise PreflightInvariantError(f"T1 target has other than the sole intended stale cause: {t1}")
        if not control_t1.fresh or control_t1.stale_bindings:
            raise PreflightInvariantError("unchanged control became stale at T1")
        gate_t1 = evaluate_bound_memory(root, memory)
        if (gate_t1.fresh or gate_t1.payload is not None or gate_t1.stale_bindings != (expected_reason,)
                or gate_t1.receipt is None or gate_t1.receipt["status"] != "stale_payload_withheld"):
            raise PreflightInvariantError("T1 gate did not withhold the same bound memory for its actual stale result")
        compile_t1 = compile_check(root)
        if not compile_t1["ok"]:
            raise PreflightInvariantError(f"T1 fixture failed compilation: {compile_t1}")
        compiler = compiler_environment()
        result = FreshnessPreflight(
            claim.id, memory.claim_sha256,
            sha256_text(canonical_json(files_t0)), sha256_text(canonical_json(files_t1)), sha256_text(diff),
            _freshness_dict(t0), _freshness_dict(t1), _freshness_dict(control_t0), _freshness_dict(control_t1),
            compile_t0, compile_t1, files_t0, files_t1, diff, memory, control_json,
            asdict(gate_t0), asdict(gate_t1), compiler, sha256_bytes(SPEC_PATH.read_bytes()),
            {"claim_clock": FROZEN_TIMESTAMP, "claim_clock_injection": "tmf.derive.now_utc",
             "claim_field_normalization": "none; full production Claim serialized with sorted canonical JSON",
             "git_commit": repo.head(), "git_identity_and_time": "fixed in fixture builder",
             "temporary_paths_included": False},
        )
        validate_preflight(result)
        return result
    finally:
        if owned:
            shutil.rmtree(root, ignore_errors=True)
