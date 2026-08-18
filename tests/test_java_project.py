from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest import mock
from pathlib import Path

from tmf.git import GitRepo
from tmf.derive import _java_node_anchor_for
from tmf.java_index import JavaIndexPolicy, java_project_index
from tmf.java_project import java_project_model, java_repository_snapshot
from tests.test_java_inherit import init_repo


class JavaProjectModelTests(unittest.TestCase):
    def test_batch_blob_hashes_match_single_hashes_and_follow_dirty_content(self):
        with tempfile.TemporaryDirectory() as td:
            root = init_repo(Path(td), {"A.java": "class A {}\n", "B.java": "class B {}\n"})
            repo = GitRepo(root)
            batched = repo.blob_shas(["A.java", "B.java", "missing.java"])
            self.assertEqual(batched["A.java"], repo.blob_sha("A.java"))
            self.assertEqual(batched["B.java"], repo.blob_sha("B.java"))
            self.assertIsNone(batched["missing.java"])
            old = batched["A.java"]
            (root / "A.java").write_text("class A { int dirty; }\n", encoding="utf-8")
            self.assertNotEqual(repo.blob_shas(["A.java"])["A.java"], old)

    def test_blob_hash_does_not_trust_same_size_and_mtime(self):
        with tempfile.TemporaryDirectory() as td:
            root = init_repo(Path(td), {"A.java": "class A { int a; }\n"})
            repo = GitRepo(root)
            path = root / "A.java"
            original_stat = path.stat()
            first = repo.blob_shas(["A.java"])["A.java"]
            path.write_text("class A { int b; }\n", encoding="utf-8")
            os.utime(path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
            self.assertEqual(path.stat().st_size, original_stat.st_size)
            self.assertEqual(path.stat().st_mtime_ns, original_stat.st_mtime_ns)
            self.assertNotEqual(repo.blob_shas(["A.java"])["A.java"], first)

    def test_batch_blob_hashes_and_snapshot_support_newline_path(self):
        with tempfile.TemporaryDirectory() as td:
            unusual = "Line\nBreak.java"
            root = init_repo(Path(td), {"A.java": "class A {}\n", unusual: "class Odd {}\n"})
            repo = GitRepo(root)
            batched = repo.blob_shas(["A.java", unusual])
            self.assertEqual(batched["A.java"], repo.blob_sha("A.java"))
            self.assertEqual(batched[unusual], repo.blob_sha(unusual))
            self.assertIsNotNone(batched[unusual])
            self.assertIn(unusual, java_project_model(repo).java_paths())
            self.assertIn(unusual, java_repository_snapshot(repo).paths)

    def test_maven_multi_module_source_sets(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "pom.xml": "<project><modules><module>domain</module><module>app</module></modules></project>\n",
                "domain/pom.xml": "<project/>\n",
                "domain/src/main/java/acme/Domain.java": "package acme; class Domain {}\n",
                "app/pom.xml": "<project/>\n",
                "app/src/test/java/acme/AppTest.java": "package acme; class AppTest {}\n",
            })
            model = java_project_model(GitRepo(repo))
            self.assertEqual({module.root for module in model.modules}, {"", "app", "domain"})
            domain = model.source_for("domain/src/main/java/acme/Domain.java")
            app_test = model.source_for("app/src/test/java/acme/AppTest.java")
            self.assertEqual((domain.module, domain.source_set), ("domain", "main"))
            self.assertEqual((app_test.module, app_test.source_set), ("app", "test"))

    def test_gradle_literal_modules_and_generated_sources(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "settings.gradle.kts": "include(\":api\", \"services:billing\")\n",
                "build.gradle.kts": "plugins { java }\n",
                "api/src/main/java/acme/Api.java": "package acme; class Api {}\n",
                "services/billing/build/generated/sources/annotationProcessor/java/main/acme/Bill.java": "package acme; class Bill {}\n",
            })
            model = java_project_model(GitRepo(repo))
            self.assertEqual({module.root for module in model.modules}, {"", "api", "services/billing"})
            generated = model.source_for("services/billing/build/generated/sources/annotationProcessor/java/main/acme/Bill.java")
            self.assertEqual((generated.module, generated.source_set, generated.generated), ("billing", "generated", True))

    def test_symbol_index_carries_module_and_source_set(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "pom.xml": "<project><modules><module>lib</module></modules></project>\n",
                "lib/src/main/java/acme/Value.java": "package acme; public class Value {}\n",
            })
            symbol, resolution = java_project_index(GitRepo(repo)).resolve("acme.Value")
            self.assertEqual(resolution, "project_fqn")
            self.assertEqual((symbol.module, symbol.source_set, symbol.generated), ("lib", "main", False))

    def test_literal_maven_and_gradle_module_dependencies(self):
        with tempfile.TemporaryDirectory() as td:
            maven = init_repo(Path(td) / "maven", {
                "pom.xml": "<project><groupId>acme</groupId><artifactId>root</artifactId><modules><module>domain</module><module>app</module></modules></project>\n",
                "domain/pom.xml": "<project><parent><groupId>acme</groupId></parent><artifactId>domain</artifactId></project>\n",
                "app/pom.xml": "<project><artifactId>app</artifactId><dependencies><dependency><groupId>acme</groupId><artifactId>domain</artifactId></dependency></dependencies></project>\n",
            })
            edges = java_project_model(GitRepo(maven)).dependencies
            self.assertIn(("app", "domain", "compile", "maven_literal_dependency"), {(e.source_root, e.target_root, e.scope, e.resolution) for e in edges})
        with tempfile.TemporaryDirectory() as td:
            gradle = init_repo(Path(td), {
                "settings.gradle": "include ':api', ':service'\n",
                "api/build.gradle": "plugins { id 'java' }\n",
                "service/build.gradle": "dependencies {\n  implementation project(':api')\n}\n",
            })
            edges = java_project_model(GitRepo(gradle)).dependencies
            self.assertIn(("service", "api", "implementation", "gradle_literal_project_dependency"), {(e.source_root, e.target_root, e.scope, e.resolution) for e in edges})

    def test_build_descriptor_change_invalidates_cached_model(self):
        with tempfile.TemporaryDirectory() as td:
            root = init_repo(Path(td), {
                "settings.gradle": "include ':api'\n",
                "api/build.gradle": "plugins { id 'java' }\n",
                "service/build.gradle": "plugins { id 'java' }\n",
            })
            repo = GitRepo(root)
            first = java_project_model(repo)
            self.assertEqual({module.root for module in first.modules}, {"", "api", "service"})
            (root / "settings.gradle").write_text("include ':api', ':service'\n", encoding="utf-8")
            second = java_project_model(repo)
            self.assertIsNot(first, second)
            self.assertEqual({module.root for module in second.modules}, {"", "api", "service"})

    def test_index_policy_can_exclude_test_generated_and_custom_sources(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "pom.xml": "<project/>\n",
                "src/main/java/acme/MainType.java": "package acme; class MainType {}\n",
                "src/test/java/acme/TestType.java": "package acme; class TestType {}\n",
                "src/integration/java/acme/IntegrationType.java": "package acme; class IntegrationType {}\n",
                "target/generated-sources/annotations/acme/GeneratedType.java": "package acme; class GeneratedType {}\n",
            })
            git_repo = GitRepo(repo)
            policy = JavaIndexPolicy(include_test=False, include_generated=False, include_custom=False)
            index = java_project_index(git_repo, policy)
            self.assertIsNotNone(index.resolve("acme.MainType")[0])
            self.assertIsNone(index.resolve("acme.TestType")[0])
            self.assertIsNone(index.resolve("acme.IntegrationType")[0])
            self.assertIsNone(index.resolve("acme.GeneratedType")[0])
            self.assertIsNot(index, java_project_index(git_repo, JavaIndexPolicy()))

    def test_external_placeholders_preserve_provenance_without_source_resolution(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {"App.java": "class App {}\n"})
            index = java_project_index(GitRepo(repo))
            jdk = index.external_placeholder("List", imports={"List": "java.util.List"})
            external = index.external_placeholder("org.example.Client")
            unknown = index.external_placeholder("Client")
            self.assertEqual((jdk.fqn, jdk.origin, jdk.provenance, jdk.source_defined), ("java.util.List", "jdk", "explicit_import", False))
            self.assertEqual((external.origin, external.provenance), ("external_dependency", "fully_qualified_reference"))
            self.assertIsNone(unknown)
        self.assertEqual(index.resolve("List", imports={"List": "java.util.List"}), (None, "external_or_missing_import"))

    def test_repository_snapshot_construction_is_lazy_and_manifest_reused_by_project_index(self):
        with tempfile.TemporaryDirectory() as td:
            root = init_repo(Path(td), {
                "src/main/java/acme/Value.java": "package acme; public class Value {}\n",
                "src/main/java/acme/Use.java": "package acme; public class Use { Value value; }\n",
            })
            repo = GitRepo(root)
            repo.read_file = mock.Mock(wraps=repo.read_file)
            with mock.patch("tmf.java_extract.extract_java_classes", wraps=__import__("tmf.java_extract", fromlist=["extract_java_classes"]).extract_java_classes) as classes:
                snapshot = java_repository_snapshot(repo)
                self.assertEqual(repo.read_file.call_count, 0)
                self.assertEqual(classes.call_count, 0)
                self.assertIsNotNone(java_project_index(repo).resolve("acme.Value")[0])
                self.assertEqual(repo.read_file.call_count, 2)
                self.assertEqual(classes.call_count, 2)
            fresh = GitRepo(root)
            fresh.read_file = mock.Mock(side_effect=AssertionError("compact manifest miss"))
            second = java_repository_snapshot(fresh)
            self.assertIsNotNone(java_project_index(fresh).resolve("acme.Value")[0])
            self.assertEqual(second.loaded_shard_count, 0)
            self.assertEqual(second.loaded_text_count, 0)

    def test_pinned_snapshot_skips_repository_fingerprint_work(self):
        with tempfile.TemporaryDirectory() as td:
            root = init_repo(Path(td), {"A.java": "class A {}\n"})
            repo = GitRepo(root)
            snapshot = java_repository_snapshot(repo)
            setattr(repo, "_tmf_java_snapshot_pinned", True)
            repo.run = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("unexpected git scan"))
            self.assertIs(snapshot, java_repository_snapshot(repo))
            self.assertIs(java_project_model(repo), java_project_model(repo))

    def test_unpinned_snapshot_invalidates_for_add_delete_and_modify(self):
        with tempfile.TemporaryDirectory() as td:
            root = init_repo(Path(td), {"A.java": "class A {}\n", "B.java": "class B {}\n"})
            repo = GitRepo(root)
            first = java_repository_snapshot(repo)

            (root / "A.java").write_text("class A { int changed; }\n", encoding="utf-8")
            modified = java_repository_snapshot(repo)
            self.assertIsNot(first, modified)
            self.assertIn("changed", modified.texts["A.java"])

            (root / "C.java").write_text("class C {}\n", encoding="utf-8")
            repo.run("add", "C.java")
            added = java_repository_snapshot(repo)
            self.assertIsNot(modified, added)
            self.assertIn("C.java", added.paths)

            repo.run("rm", "B.java")
            deleted = java_repository_snapshot(repo)
            self.assertIsNot(added, deleted)
            self.assertNotIn("B.java", deleted.paths)

    def test_pinned_snapshot_has_explicit_repo_lifetime_and_fresh_repo_refreshes(self):
        with tempfile.TemporaryDirectory() as td:
            root = init_repo(Path(td), {"A.java": "class A {}\n"})
            pinned_repo = GitRepo(root)
            pinned = java_repository_snapshot(pinned_repo)
            setattr(pinned_repo, "_tmf_java_snapshot_pinned", True)
            (root / "A.java").write_text("class A { int later; }\n", encoding="utf-8")
            self.assertIs(pinned, java_repository_snapshot(pinned_repo))
            fresh = java_repository_snapshot(GitRepo(root))
            self.assertIsNot(pinned, fresh)
            self.assertIn("later", fresh.texts["A.java"])

    def test_synthetic_large_repo_snapshot_loads_only_accessed_file(self):
        with tempfile.TemporaryDirectory() as td:
            files = {f"src/main/java/acme/T{i}.java": f"package acme; class T{i} {{}}\n" for i in range(240)}
            root = init_repo(Path(td), files)
            repo = GitRepo(root); repo.read_file = mock.Mock(wraps=repo.read_file)
            with mock.patch("tmf.java_extract.extract_java_classes", wraps=__import__("tmf.java_extract", fromlist=["extract_java_classes"]).extract_java_classes) as classes, \
                 mock.patch("tmf.java_extract.extract_java_methods", wraps=__import__("tmf.java_extract", fromlist=["extract_java_methods"]).extract_java_methods) as methods:
                snapshot = java_repository_snapshot(repo)
                self.assertEqual(repo.read_file.call_count, 0)
                self.assertEqual(classes.call_count, 0)
                self.assertEqual(len(snapshot.classes["src/main/java/acme/T7.java"]), 1)
                self.assertEqual(repo.read_file.call_count, 1)
                self.assertEqual(classes.call_count, 1)
                self.assertEqual(methods.call_count, 1)
                snapshot.methods["src/main/java/acme/T7.java"]
                self.assertEqual(repo.read_file.call_count, 1)
                self.assertEqual(classes.call_count, 1)

    def test_repository_snapshot_reuses_persistent_blob_shard_without_source(self):
        with tempfile.TemporaryDirectory() as td:
            root = init_repo(Path(td), {"A.java": "class A { void one() {} }\n", "B.java": "class B {}\n"})
            first = java_repository_snapshot(GitRepo(root))
            expected = first.classes["A.java"]
            shard = first._shard("A.java")
            self.assertNotIn('"text"', shard.read_text(encoding="utf-8"))
            fresh_repo = GitRepo(root); fresh_repo.read_file = mock.Mock(side_effect=AssertionError("persistent shard miss"))
            second = java_repository_snapshot(fresh_repo)
            self.assertEqual(second.classes["A.java"], expected)
            self.assertEqual(second.loaded_shard_count, 1)
            self.assertEqual(second.loaded_text_count, 0)

    def test_repository_snapshot_rebuilds_changed_and_corrupt_accessed_shards(self):
        with tempfile.TemporaryDirectory() as td:
            root = init_repo(Path(td), {"A.java": "class A { void one() {} }\n", "B.java": "class B {}\n"})
            first = java_repository_snapshot(GitRepo(root)); first.classes["A.java"]; first.classes["B.java"]
            (root / "A.java").write_text("class A { void changed() {} }\n", encoding="utf-8")
            changed = java_repository_snapshot(GitRepo(root))
            self.assertEqual(changed.parsed_source_count, 0)
            self.assertTrue(any(n.qualname == "A.changed" for n in changed.methods["A.java"]))
            self.assertEqual(changed.parsed_source_count, 1)
            changed._shard("B.java").write_text("{broken", encoding="utf-8")
            fresh = java_repository_snapshot(GitRepo(root)); fresh.classes["B.java"]
            self.assertEqual(fresh.parsed_source_count, 1)

    def test_lazy_snapshot_rejects_source_changed_after_construction_with_shard_hit(self):
        with tempfile.TemporaryDirectory() as td:
            root = init_repo(Path(td), {"A.java": "class A { void oldName() {} }\n"})
            primed = java_repository_snapshot(GitRepo(root))
            self.assertTrue(any(n.qualname == "A.oldName" for n in primed.methods["A.java"]))
            snapshot = java_repository_snapshot(GitRepo(root))
            (root / "A.java").write_text("class A { void newName() {} }\n", encoding="utf-8")
            with self.assertRaisesRegex(OSError, "changed after snapshot creation"):
                snapshot.classes["A.java"]

    def test_lazy_mapping_membership_is_io_free(self):
        with tempfile.TemporaryDirectory() as td:
            root = init_repo(Path(td), {"A.java": "class A {}\n"})
            repo = GitRepo(root)
            snapshot = java_repository_snapshot(repo)
            repo.read_file = mock.Mock(side_effect=AssertionError("membership performed I/O"))
            self.assertIn("A.java", snapshot.texts)
            self.assertIn("A.java", snapshot.classes)
            self.assertIn("A.java", snapshot.methods)
            self.assertNotIn("Missing.java", snapshot.methods)
            self.assertEqual(snapshot.loaded_text_count, 0)
            self.assertEqual(snapshot.loaded_shard_count, 0)

    def test_lazy_manifest_rejects_source_changed_after_construction(self):
        with tempfile.TemporaryDirectory() as td:
            root = init_repo(Path(td), {"A.java": "class A {}\n"})
            primed = java_repository_snapshot(GitRepo(root))
            self.assertEqual([item["fqn"] for item in primed.symbol_manifest()], ["A"])
            snapshot = java_repository_snapshot(GitRepo(root))
            (root / "A.java").write_text("class B {}\n", encoding="utf-8")
            with self.assertRaisesRegex(OSError, "changed after snapshot creation"):
                snapshot.symbol_manifest()

    def test_cached_in_memory_manifest_is_revalidated(self):
        with tempfile.TemporaryDirectory() as td:
            root = init_repo(Path(td), {"A.java": "class A {}\n"})
            snapshot = java_repository_snapshot(GitRepo(root))
            self.assertEqual([item["fqn"] for item in snapshot.symbol_manifest()], ["A"])
            (root / "A.java").write_text("class B {}\n", encoding="utf-8")
            with self.assertRaisesRegex(OSError, "changed after snapshot creation"):
                snapshot.symbol_manifest()

    def test_structurally_corrupt_manifest_is_rebuilt(self):
        with tempfile.TemporaryDirectory() as td:
            root = init_repo(Path(td), {"A.java": "class A {}\n"})
            first = java_repository_snapshot(GitRepo(root))
            first.symbol_manifest()
            payload = json.loads(first.manifest_path.read_text(encoding="utf-8"))
            payload["symbols"] = [{"path": "A.java"}]
            first.manifest_path.write_text(json.dumps(payload), encoding="utf-8")
            fresh = java_repository_snapshot(GitRepo(root))
            symbols = fresh.symbol_manifest()
            self.assertEqual([(item["fqn"], item["path"]) for item in symbols], [("A", "A.java")])

    def test_manifest_reuses_unchanged_path_with_no_top_level_symbols(self):
        with tempfile.TemporaryDirectory() as td:
            root = init_repo(Path(td), {
                "OnlyPackage.java": "package acme;\n",
                "Value.java": "package acme; class Value {}\n",
            })
            first = java_repository_snapshot(GitRepo(root))
            first.symbol_manifest()
            (root / "Value.java").write_text("package acme; class Value2 {}\n", encoding="utf-8")
            repo = GitRepo(root)
            snapshot = java_repository_snapshot(repo)
            original_read = repo.read_file
            seen: list[str] = []
            def counted_read(path):
                seen.append(path)
                return original_read(path)
            repo.read_file = counted_read
            snapshot.symbol_manifest()
            self.assertNotIn("OnlyPackage.java", seen)
            self.assertIn("Value.java", seen)

    def test_repository_snapshot_prunes_deleted_path_shards(self):
        with tempfile.TemporaryDirectory() as td:
            root = init_repo(Path(td), {"A.java": "class A {}\n", "B.java": "class B {}\n"})
            first = java_repository_snapshot(GitRepo(root)); first.classes["A.java"]; first.classes["B.java"]
            cache = first.cache_dir
            self.assertEqual(len([p for p in cache.glob("*.json") if p.name != "manifest.json"]), 2)
            (root / "B.java").unlink(); GitRepo(root).run("rm", "--cached", "B.java")
            snapshot = java_repository_snapshot(GitRepo(root))
            self.assertEqual(snapshot.paths, ("A.java",))
            self.assertEqual(len([p for p in cache.glob("*.json") if p.name != "manifest.json"]), 1)

    def test_java_anchor_failure_is_fail_soft_and_diagnostic(self):
        repo = mock.Mock(spec=GitRepo)
        repo._tmf_java_anchor_cache = {}
        repo.read_file.side_effect = OSError("unreadable")
        with self.assertLogs("tmf.derive", level="DEBUG") as logs:
            anchor = _java_node_anchor_for(repo, "Broken.java", "Broken.m", "method")
        self.assertEqual(anchor, {"path": "Broken.java", "line_start": None, "line_end": None, "qualname": "Broken.m"})
        self.assertIn("Java anchor lookup failed", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
