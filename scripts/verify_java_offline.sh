#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

VENV="$ROOT/.ts-venv"
PY="$VENV/bin/python"
PIP="$VENV/bin/pip"
WHEELS="$ROOT/vendor/wheels"
GRAMMAR_SRC="$ROOT/vendor/grammar-src"

fail() {
  echo "JAVA OFFLINE VERIFY: FAIL" >&2
  echo "reason: $*" >&2
  exit 1
}

platform_diag() {
  python3 - <<'PY'
import platform, sys, sysconfig
print("python:", sys.version.replace("\n", " "))
print("platform:", platform.platform())
print("machine:", platform.machine())
print("glibc:", platform.libc_ver())
print("soabi:", sysconfig.get_config_var("SOABI"))
PY
}

echo "[java-offline] platform diagnostics"
platform_diag

echo "[java-offline] creating/reusing venv: $VENV"
python3 -m venv "$VENV" || fail "python3 -m venv failed; ensure stdlib venv is installed"

if [[ ! -x "$PY" ]]; then
  fail "venv python missing at $PY"
fi

# Keep pip offline and deterministic. Do not touch system Python; PEP 668 externally-managed
# environments are avoided by using this repository-local venv.
echo "[java-offline] installing tree-sitter wheels with --no-index"
set +e
"$PIP" install --no-index --find-links "$WHEELS" "tree_sitter==0.25.2" "tree_sitter_java==0.23.5"
install_status=$?
set -e

if [[ $install_status -ne 0 ]]; then
  echo "[java-offline] wheel install failed; checking grammar source fallback" >&2
  if [[ -d "$GRAMMAR_SRC" ]]; then
    fail "wheel ABI install failed and grammar source fallback is present but not implemented in this package; platform may not be Linux x86_64/cp312-compatible"
  fi
  fail "wheel ABI install failed and vendor/grammar-src is absent; expected cp312 manylinux2014_x86_64 wheels in vendor/wheels"
fi

export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

echo "[java-offline] import check"
"$PY" - <<'PY'
import platform, sysconfig
import tree_sitter, tree_sitter_java
from tmf.java_extract import java_status
status = java_status()
assert status.available, status
print("tree_sitter:", getattr(tree_sitter, "__version__", "unknown"))
print("tree_sitter_java language:", tree_sitter_java.language())
print("soabi:", sysconfig.get_config_var("SOABI"))
print("platform:", platform.platform())
PY

echo "[java-offline] Java unit tests: no skip allowed"
unit_output="$($PY -m unittest tests/test_java_nodes.py tests/test_java_inherit.py -v 2>&1)" || {
  printf '%s\n' "$unit_output" >&2
  fail "Java unit tests failed"
}
printf '%s\n' "$unit_output"
if printf '%s\n' "$unit_output" | grep -qi "skipped\|skip"; then
  fail "Java unit tests reported a skip; offline verifier requires real Java execution"
fi

echo "[java-offline] minimal Java fixture warm + two-way freshness assertions"
"$PY" - <<'PY'
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.retrieve import retrieve_path
from tmf.store import Store
from tmf.warm import warm_repo

JAVA = '''package demo;
@interface Marker {}
public class Sample {
    public static final String NAME = "tmf";
    private int count = 1;
    @Marker
    public String greet(String who) {
        return NAME + who + count;
    }
    public void bye() {
        return;
    }
}
'''

def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

with tempfile.TemporaryDirectory() as td:
    repo = Path(td) / "repo"
    repo.mkdir()
    run(["git", "init"], repo)
    run(["git", "config", "user.email", "tmf@example.com"], repo)
    run(["git", "config", "user.name", "tmf"], repo)
    (repo / "Sample.java").write_text(JAVA, encoding="utf-8")
    run(["git", "add", "Sample.java"], repo)
    run(["git", "commit", "-m", "init"], repo)

    warm_result = warm_repo(repo)
    assert warm_result.get("files", 0) >= 1 or warm_result.get("paths_warmed", 0) >= 1, warm_result
    result = retrieve_path(repo, "Sample.java")
    claims = [item.claim for item in result.claims]
    java_claims = [c for c in claims if c.body.get("language") == "java"]
    assert java_claims, claims
    greet = next(c for c in java_claims if c.body.get("qualname") == "Sample.greet")
    sample = next(c for c in java_claims if c.body.get("qualname") == "Sample")

    # Pure comment/trivia remains fresh.
    (repo / "Sample.java").write_text(JAVA.replace("return NAME + who + count;", "// comment only\n        return NAME + who + count;"), encoding="utf-8")
    assert check_freshness(GitRepo(repo), greet).fresh

    # Formatting-only spacing remains fresh.
    (repo / "Sample.java").write_text(JAVA.replace("public String greet(String who) {", "public   String   greet( String who )   {"), encoding="utf-8")
    assert check_freshness(GitRepo(repo), greet).fresh

    # Literal/body token change stales method and containing class.
    (repo / "Sample.java").write_text(JAVA.replace("return NAME + who + count;", "return NAME + who + count + \"!\";"), encoding="utf-8")
    assert not check_freshness(GitRepo(repo), greet).fresh
    assert not check_freshness(GitRepo(repo), sample).fresh

    # Annotation change stales annotated method.
    (repo / "Sample.java").write_text(JAVA.replace("@Marker", "@Deprecated"), encoding="utf-8")
    assert not check_freshness(GitRepo(repo), greet).fresh

    # Delete node and read through: tombstone reconciled away.
    (repo / "Sample.java").write_text("public class Sample { int count = 1; }\n", encoding="utf-8")
    retrieve_path(repo, "Sample.java")
    assert Store(repo).get_claim(greet.id) is None

print("minimal Java fixture assertions passed")
PY


echo "[java-offline] Java inheritance edge bench"
"$PY" - <<'PY'
from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_inherit_edge_claim_id, stable_java_node_claim_id
from tmf.retrieve import retrieve_path, reverse_implementors, reverse_subtypes
from tmf.store import Store
from tmf.warm import warm_repo

def run(cmd, cwd):
    return subprocess.run(cmd, cwd=cwd, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)

with tempfile.TemporaryDirectory() as td:
    repo = Path(td) / "repo"
    repo.mkdir()
    run(["git", "init"], repo)
    run(["git", "config", "user.email", "tmf@example.com"], repo)
    run(["git", "config", "user.name", "tmf"], repo)
    src = """package demo;
import java.util.List;
import demo.missing.*;
interface I {}
class B { int x = 1; }
class C {}
class A extends B implements I, List, WildThing {}
"""
    (repo / "Sample.java").write_text(src, encoding="utf-8")
    run(["git", "add", "Sample.java"], repo)
    run(["git", "commit", "-m", "init"], repo)

    warm_repo(repo)
    store = Store(repo)
    a = stable_java_node_claim_id("Sample.java", "A", "class")
    b = stable_java_node_claim_id("Sample.java", "B", "class")
    c = stable_java_node_claim_id("Sample.java", "C", "class")
    i = stable_java_node_claim_id("Sample.java", "I", "interface")
    edge_id = stable_inherit_edge_claim_id(a, b, "extends")
    impl_id = stable_inherit_edge_claim_id(a, i, "implements")
    edge = store.get_claim(edge_id)
    assert edge is not None and edge.body["edge_kind"] == "inherits" and edge.body["relation"] == "extends"
    assert store.get_claim(impl_id) is not None
    graph = store.get_claim(a).body["graph"]
    unresolved = {(u["expr"], u["reason"]) for u in graph["inherits_unresolved"]}
    assert ("List", "wildcard_import") in unresolved or ("List", "external_or_jdk_type") in unresolved
    assert ("WildThing", "wildcard_import") in unresolved
    assert reverse_subtypes(repo, b)["subtypes"][0]["child_id"] == a
    assert reverse_implementors(repo, i)["implementors"][0]["child_id"] == a

    # Unrelated type body changes do not stale edge.
    (repo / "Sample.java").write_text(src.replace("class C {}", "class C { int y = 2; }"), encoding="utf-8")
    assert check_freshness(GitRepo(repo), edge).fresh

    # Parent body change stales edge.
    (repo / "Sample.java").write_text(src.replace("int x = 1", "int x = 2"), encoding="utf-8")
    assert not check_freshness(GitRepo(repo), edge).fresh

    # Retarget removes old edge and creates new one.
    (repo / "Sample.java").write_text(src.replace("extends B", "extends C"), encoding="utf-8")
    assert not check_freshness(GitRepo(repo), store.get_claim(a)).fresh
    retrieve_path(repo, "Sample.java")
    store = Store(repo)
    assert store.get_claim(edge_id) is None
    assert store.get_claim(stable_inherit_edge_claim_id(a, c, "extends")) is not None

    # Endpoint deletion reconciles edge away.
    (repo / "Sample.java").write_text("package demo; class A {}\n", encoding="utf-8")
    retrieve_path(repo, "Sample.java")
    assert Store(repo).get_claim(stable_inherit_edge_claim_id(a, c, "extends")) is None

print("java inheritance bench assertions passed")
PY

echo "JAVA OFFLINE VERIFY: PASS"
