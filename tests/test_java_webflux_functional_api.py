from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.store import Store
from tmf.warm import warm_repo
from tests.test_java_inherit import init_repo

ROUTER_IMPORTS = '''import org.springframework.web.reactive.function.server.RouterFunction;
import org.springframework.web.reactive.function.server.RouterFunctions;
import org.springframework.web.reactive.function.server.RequestPredicates;
'''
HANDLER = '''package app;
class UserHandler {
  String get(Object request) { return "ok"; }
  String save(Object request) { return "saved"; }
}
'''


@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaWebFluxFunctionalApiTests(unittest.TestCase):
    def repo(self, router: str, handler: str = HANDLER, extra: dict[str, str] | None = None):
        td = tempfile.TemporaryDirectory()
        files = {"src/app/Routes.java": "package app;\n" + ROUTER_IMPORTS + router,
                 "src/app/UserHandler.java": handler}
        files.update(extra or {})
        repo = init_repo(Path(td.name), files)
        warm_repo(repo)
        return td, repo

    def api_claims(self, repo):
        return [c for c in Store(repo).iter_claims() if c.scope == "api"]

    def test_direct_cross_file_route_has_v2_dual_bindings_and_stable_id(self):
        router = '''class Routes { RouterFunction<?> routes(UserHandler handler) {
 return RouterFunctions.route(RequestPredicates.GET("/users"), handler::get);
}}'''
        td, repo = self.repo(router)
        with td:
            claims = self.api_claims(repo)
            self.assertEqual(len(claims), 1)
            claim = claims[0]
            self.assertTrue(claim.id.startswith("claim_api_rel_"))
            self.assertEqual(claim.schema_version, "tmf.schema.v2")
            self.assertEqual([(b.role, b.path) for b in claim.bindings], [
                ("route_declaration", "src/app/Routes.java"), ("handler", "src/app/UserHandler.java")])
            self.assertTrue(check_freshness(GitRepo(repo), claim).fresh)
            old_id = claim.id
            (repo / "src/app/Routes.java").write_text((repo / "src/app/Routes.java").read_text().replace("class Routes", "// format\nclass Routes"), encoding="utf-8")
            warm_repo(repo)
            self.assertIsNotNone(Store(repo).get_claim(old_id))

    def test_flat_builder_exact_forms_only(self):
        router = '''class Routes { RouterFunction<?> routes(UserHandler h) {
 return RouterFunctions.route().GET("/u", h::get).POST("/u", h::save).build();
}}'''
        td, repo = self.repo(router)
        with td:
            self.assertEqual({(c.body["method"], c.body["route_path"]) for c in self.api_claims(repo)}, {("GET", "/u"), ("POST", "/u")})

    def test_route_and_handler_mutate_stale_independently(self):
        router = '''class Routes { RouterFunction<?> routes(UserHandler h) {
 return RouterFunctions.route(RequestPredicates.GET("/u"), h::get);
}}'''
        td, repo = self.repo(router)
        with td:
            claim = self.api_claims(repo)[0]
            (repo / "src/app/Routes.java").write_text((repo / "src/app/Routes.java").read_text().replace('"/u"', '"/v"'), encoding="utf-8")
            stale = check_freshness(GitRepo(repo), claim).stale_bindings
            self.assertTrue(any("route declaration missing" in x for x in stale), stale)
            (repo / "src/app/Routes.java").write_text("package app;\n" + ROUTER_IMPORTS + router, encoding="utf-8")
            (repo / "src/app/UserHandler.java").write_text(HANDLER.replace('return "ok"', 'return "changed"'), encoding="utf-8")
            stale = check_freshness(GitRepo(repo), claim).stale_bindings
            self.assertTrue(any("handler_hash mismatch" in x for x in stale), stale)

    def test_route_and_handler_deletion_reconcile_or_stale(self):
        router = '''class Routes { RouterFunction<?> routes(UserHandler h) {
 return RouterFunctions.route(RequestPredicates.GET("/u"), h::get);
}}'''
        td, repo = self.repo(router)
        with td:
            claim = self.api_claims(repo)[0]
            (repo / "src/app/UserHandler.java").unlink()
            self.assertTrue(any("missing" in x for x in check_freshness(GitRepo(repo), claim).stale_bindings))
            (repo / "src/app/UserHandler.java").write_text(HANDLER, encoding="utf-8")
            (repo / "src/app/Routes.java").write_text("package app; class Routes {}", encoding="utf-8")
            warm_repo(repo)
            self.assertIsNone(Store(repo).get_claim(claim.id))

    def test_ambiguity_decoys_and_unsupported_forms_emit_no_api_or_calls(self):
        bad = '''class Routes { RouterFunction<?> routes(UserHandler h) {
 RouterFunctions.route(RequestPredicates.GET(PATH), h::get);
 RouterFunctions.route(RequestPredicates.GET("/lambda"), r -> h.get(r));
 RouterFunctions.route(RequestPredicates.GET("/composed").and(x()), h::get);
 RouterFunctions.nest(RequestPredicates.path("/n"), RouterFunctions.route(RequestPredicates.GET("/x"), h::get));
 RouterFunctions.route().GET("/x", h::get).filter(f()).build();
 return null;
}}'''
        td, repo = self.repo(bad)
        with td:
            self.assertEqual(self.api_claims(repo), [])
            self.assertEqual([c for c in Store(repo).iter_claims() if c.body.get("edge_kind") == "calls" and "Router" in c.claim], [])
        overload = HANDLER.replace('String save', 'String get(String x) { return x; }\n  String save')
        direct = '''class Routes { RouterFunction<?> routes(UserHandler h) { return RouterFunctions.route(RequestPredicates.GET("/x"), h::get); }}'''
        td, repo = self.repo(direct, overload)
        with td:
            self.assertEqual(self.api_claims(repo), [])
        td, repo = self.repo(direct, HANDLER, {"src/other/UserHandler.java": "package other; " + HANDLER.split("package app;",1)[1]})
        with td:
            self.assertEqual(self.api_claims(repo), [])

    def test_exact_imports_required_and_legacy_ids_unchanged(self):
        decoy = '''import fake.RouterFunctions; import fake.RequestPredicates;
class Routes { RouterFunction<?> routes(UserHandler h) { return RouterFunctions.route(RequestPredicates.GET("/x"), h::get); }}'''
        td = tempfile.TemporaryDirectory()
        with td:
            repo = init_repo(Path(td.name), {"src/app/Routes.java": "package app;\n" + decoy, "src/app/UserHandler.java": HANDLER})
            warm_repo(repo)
            self.assertEqual(self.api_claims(repo), [])


if __name__ == "__main__":
    unittest.main()
