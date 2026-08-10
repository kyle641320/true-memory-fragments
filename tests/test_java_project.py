from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tmf.git import GitRepo
from tmf.java_index import JavaIndexPolicy, java_project_index
from tmf.java_project import java_project_model
from tests.test_java_inherit import init_repo


class JavaProjectModelTests(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
