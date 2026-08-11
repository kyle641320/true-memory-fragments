from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_api_claim_id
from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.store import Store
from tmf.warm import warm_repo
from tests.test_java_inherit import init_repo, run

IMPORTS = '''import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestMethod;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.DeleteMapping;
import org.springframework.web.bind.annotation.PatchMapping;
'''


@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaSpringApiNodeTests(unittest.TestCase):
    def claims(self, files):
        td = tempfile.TemporaryDirectory()
        repo = init_repo(Path(td.name), files)
        warm_repo(repo)
        return td, repo, [c for c in Store(repo).iter_claims() if c.scope == "api"]

    def test_literal_arrays_and_request_methods_build_stable_handler_apis(self):
        source = IMPORTS + '''@RestController
@RequestMapping(path={"/v1", "/v2"})
class C {
  @GetMapping(value={"/a", "/b"}) String get() { return "ok"; }
  @RequestMapping(path="/item", method={RequestMethod.POST, RequestMethod.PATCH})
  String save() { return "ok"; }
}
'''
        td, repo, claims = self.claims({"C.java": source})
        with td:
            actual = {(c.body["method"], c.body["route_path"], c.body["handler_qualname"]) for c in claims}
            expected = {(m, p + r, "C." + h) for p in ("/v1", "/v2") for m, r, h in (("GET", "/a", "get"), ("GET", "/b", "get"), ("POST", "/item", "save"), ("PATCH", "/item", "save"))}
            self.assertEqual(actual, expected)
            claim = Store(repo).get_claim(stable_api_claim_id("C.java", "GET", "/v1/a", "C.get"))
            self.assertIsNotNone(claim)
            self.assertTrue(check_freshness(GitRepo(repo), claim).fresh)
            self.assertEqual(claim.body["verification"]["method"], "java-ast-literal-route-check")
            handler = next(c for c in Store(repo).iter_claims() if c.scope == "class" and c.body.get("node_kind") == "method" and c.body.get("qualname") == "C.get")
            self.assertEqual(claim.body["handler_node_id"], handler.id)

    def test_all_composed_mapping_verbs_and_webflux_annotated_identity(self):
        source = IMPORTS + '''@RestController class C {
 @PostMapping("/p") String p(){return "";} @PutMapping("/u") String u(){return "";}
 @DeleteMapping("/d") String d(){return "";} @PatchMapping("/x") String x(){return "";}
}'''
        td, _repo, claims = self.claims({"C.java": source})
        with td:
            self.assertEqual({(c.body["method"], c.body["route_path"]) for c in claims}, {("POST","/p"),("PUT","/u"),("DELETE","/d"),("PATCH","/x")})

    def test_exact_spring_wildcard_import_composes_class_and_method_routes(self):
        source = '''import org.springframework.web.bind.annotation.*;
@RestController
@RequestMapping(path={"/api", "/internal"})
class Resource {
 @PostMapping("") String create(){return "";}
 @GetMapping(value={"/items", "/things"}) String list(){return "";}
 @PutMapping({"/items", "/items/{id}"}) String update(){return "";}
}'''
        td, _repo, claims = self.claims({"Resource.java": source})
        with td:
            self.assertEqual(
                {(c.body["method"], c.body["route_path"]) for c in claims},
                {(verb, prefix + suffix)
                 for prefix in ("/api", "/internal")
                 for verb, suffix in (("POST", ""), ("GET", "/items"), ("GET", "/things"),
                                      ("PUT", "/items"), ("PUT", "/items/{id}"))},
            )

    def test_unrelated_wildcard_and_dynamic_class_prefix_remain_unresolved(self):
        sources = {
            "Decoy.java": 'import fake.*; @RestController @RequestMapping("/api") class Decoy { @GetMapping("/x") String x(){return "";} }',
            "DynamicPrefix.java": 'import org.springframework.web.bind.annotation.*; @RestController @RequestMapping(PREFIX) class DynamicPrefix { static final String PREFIX="/api"; @GetMapping("/x") String x(){return "";} }',
        }
        td, _repo, claims = self.claims(sources)
        with td:
            self.assertEqual([], claims)

    def test_cross_file_stability_freshness_and_delete(self):
        source = IMPORTS + '@RestController class C { @GetMapping("/x") String h(){return "ok";} }'
        td, repo, claims = self.claims({"C.java": source, "Other.java": "class Other { int n=1; }"})
        with td:
            claim = claims[0]
            (repo / "Other.java").write_text("class Other { int n=2; }", encoding="utf-8")
            self.assertTrue(check_freshness(GitRepo(repo), claim).fresh)
            (repo / "C.java").write_text(source.replace('"ok"', '"changed"'), encoding="utf-8")
            self.assertFalse(check_freshness(GitRepo(repo), claim).fresh)
            (repo / "C.java").unlink()
            self.assertFalse(check_freshness(GitRepo(repo), claim).fresh)
            run(["git", "add", "-u"], repo)
            run(["git", "commit", "-m", "delete controller"], repo)
            warm_repo(repo)
            self.assertIsNone(Store(repo).get_claim(claim.id))

    def test_decoys_dynamic_ambiguous_unsupported_and_no_calls_are_rejected(self):
        valid_imports = IMPORTS
        sources = {
            "Decoy.java": 'import fake.GetMapping; import fake.RestController; @RestController class Decoy { @GetMapping("/x") String h(){return "";} }',
            "Dynamic.java": valid_imports + '@RestController class Dynamic { static final String P="/x"; @GetMapping(P) String h(){return "";} }',
            "Alias.java": valid_imports + '@RestController class Alias { @GetMapping(path="/x", value="/y") String h(){return "";} }',
            "UnknownMethod.java": valid_imports + '@RestController class UnknownMethod { @RequestMapping(path="/x") String h(){return "";} }',
            "Meta.java": valid_imports + '@RestController class Meta { @MyGet("/x") String h(){return "";} }',
            "NoController.java": valid_imports + 'class NoController { @GetMapping("/x") String h(){return "";} }',
            "Overloaded.java": valid_imports + '@RestController class Overloaded { @GetMapping("/x") String h(){return "";} String h(String x){return x;} }',
            "Functional.java": '''import org.springframework.web.reactive.function.server.RouterFunction;
import org.springframework.web.reactive.function.server.RouterFunctions;
import org.springframework.web.reactive.function.server.RequestPredicates;
class Functional { RouterFunction<?> routes(Handler h) { return RouterFunctions.route(RequestPredicates.GET("/functional"), h::get); } }''',
        }
        td, repo, claims = self.claims(sources)
        with td:
            self.assertEqual(claims, [])
            self.assertEqual([c for c in Store(repo).iter_claims() if c.scope == "call"], [])


if __name__ == "__main__":
    unittest.main()
