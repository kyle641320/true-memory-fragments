from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.store import Store
from tmf.warm import warm_repo
from tests.test_java_inherit import init_repo


def claims(repo: Path):
    return list(Store(repo).iter_claims())


class JavaFreshnessMutationTests(unittest.TestCase):
    def test_method_comment_control_semantic_delete_and_rewarm(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "A.java": "class A { int f(){ return 1; } int g(){ return f(); } }\n",
                "Other.java": "class Other { int x(){ return 2; } }\n",
            })
            warm_repo(repo); before = claims(repo); git = GitRepo(repo)
            path = repo / "A.java"; original = path.read_text()
            path.write_text(original.replace("int f()", "int f() /* control */"))
            stale = {c.id for c in before if not check_freshness(git, c).fresh}
            self.assertEqual({c.id for c in before if c.scope == "file" and any(b.path == "A.java" for b in c.bindings)}, stale)
            path.write_text(original.replace("return 1", "return 3"))
            stale = {c.id for c in before if not check_freshness(git, c).fresh}
            expected = {c.id for c in before if any(b.path == "A.java" and (b.qualname == "A.f" or (c.body.get("node_kind") == "class" and b.qualname == "A")) for b in c.bindings)} | {c.id for c in before if c.scope == "file" and any(b.path == "A.java" for b in c.bindings)}
            self.assertEqual(expected, stale)
            self.assertEqual(0, warm_repo(repo)["stale_after_rewarm"] if "stale_after_rewarm" in warm_repo(repo) else sum(not check_freshness(git,c).fresh for c in claims(repo)))

    def test_di_endpoint_delete_ambiguity_rebind_and_rewarm(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "src/main/java/api/Engine.java": "package api;\npublic interface Engine {}\n",
                "src/main/java/impl/Fast.java": "package impl;\nimport api.Engine;\nimport org.springframework.stereotype.Service;\n@Service public class Fast implements Engine {}\n",
                "src/main/java/app/App.java": "package app;\nimport api.Engine;\nimport org.springframework.beans.factory.annotation.Autowired;\nclass App { @Autowired Engine engine; }\n",
            })
            warm_repo(repo); before = claims(repo); edge = next(c for c in before if c.body.get("edge_kind") == "injects")
            self.assertEqual({"injector", "bean"}, {b.role for b in edge.bindings})
            (repo/"src/main/java/impl/Fast.java").write_text((repo/"src/main/java/impl/Fast.java").read_text().replace("@Service", ""))
            self.assertFalse(check_freshness(GitRepo(repo), edge).fresh)
            warm_repo(repo)
            refreshed = next(c for c in claims(repo) if c.body.get("edge_kind") == "injects")
            self.assertFalse(check_freshness(GitRepo(repo), edge).fresh)
            self.assertEqual({"injector", "bean"}, {b.role for b in refreshed.bindings})
            (repo/"src/main/java/impl/Fast.java").write_text((repo/"src/main/java/impl/Fast.java").read_text().replace("public class", "@Service public class"))
            (repo/"src/main/java/impl/Slow.java").write_text("package impl;\nimport api.Engine;\nimport org.springframework.stereotype.Service;\n@Service public class Slow implements Engine {}\n")
            warm_repo(repo); edges = [c for c in claims(repo) if c.body.get("edge_kind") == "injects"]
            self.assertTrue(edges)
            self.assertTrue(all({"injector", "bean"} == {b.role for b in c.bindings} for c in edges))

    def test_jpa_repository_has_typed_entity_dependency_and_rebinds(self):
        with tempfile.TemporaryDirectory() as td:
            repo = init_repo(Path(td), {
                "Owner.java": "package app;\nimport jakarta.persistence.Entity;\n@Entity public class Owner { int body(){return 1;} }\n",
                "Pet.java": "package app;\nimport jakarta.persistence.Entity;\n@Entity public class Pet {}\n",
                "OwnerRepo.java": "package app;\nimport org.springframework.data.jpa.repository.JpaRepository;\npublic interface OwnerRepo extends JpaRepository<Owner, Long> { }\n",
                "RepoAnchor.java": "class RepoAnchor {}\n",
            })
            warm_repo(repo); before = claims(repo); claim = next(c for c in before if c.body.get("qualname") == "OwnerRepo")
            dep = next(b for b in claim.bindings if b.role == "repository_domain_entity")
            self.assertEqual(("Owner.java", "Owner"), (dep.path, dep.qualname))
            (repo/"Owner.java").write_text((repo/"Owner.java").read_text().replace("return 1", "return 2"))
            self.assertFalse(check_freshness(GitRepo(repo), claim).fresh)
            (repo/"OwnerRepo.java").write_text((repo/"OwnerRepo.java").read_text().replace("<Owner,", "<Pet,"))
            warm_repo(repo); rebound = next(c for c in claims(repo) if c.body.get("qualname") == "OwnerRepo")
            dep = next(b for b in rebound.bindings if b.role == "repository_domain_entity")
            self.assertEqual(("Pet.java", "Pet"), (dep.path, dep.qualname))


if __name__ == "__main__": unittest.main()
