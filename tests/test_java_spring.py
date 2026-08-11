from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tmf.ids import stable_java_node_claim_id
from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.store import Store
from tmf.warm import warm_repo
from tests.test_java_inherit import init_repo


@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaSpringEvidenceTests(unittest.TestCase):
    def _claim(self, source: str, qualname: str):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        repo = init_repo(Path(td.name), {"App.java": source})
        warm_repo(repo)
        return Store(repo).get_claim(stable_java_node_claim_id("App.java", qualname, "class"))

    def test_exact_imported_stereotype_and_autowired_field_link(self):
        claim = self._claim('''
import org.springframework.stereotype.Service;
import org.springframework.beans.factory.annotation.Autowired;
@Service class Engine {}
class App { @Autowired Engine engine; }
''', "App")
        self.assertEqual(
            [stable_java_node_claim_id("App.java", "Engine", "class")],
            [edge["target_id"] for edge in claim.body["graph"]["injects"]],
        )
        self.assertEqual([], claim.body["graph"]["injects_unresolved"])

    def test_same_simple_name_decoys_do_not_create_beans_or_injection(self):
        claim = self._claim('''
import fake.Service;
import fake.Autowired;
@Service class Engine {}
class App { @Autowired Engine engine; }
''', "App")
        self.assertEqual([], claim.body["graph"]["injects"])
        self.assertEqual("injection_annotation_not_recognized", claim.body["graph"]["injects_unresolved"][0]["reason"])
        self.assertEqual("Autowired", claim.body["graph"]["injects_unresolved"][0]["annotation"])

    def test_external_exact_import_is_unresolved_not_a_runtime_call(self):
        source = '''
import org.springframework.beans.factory.annotation.Autowired;
class App { @Autowired ExternalClient client; void run() {} }
'''
        claim = self._claim(source, "App")
        self.assertEqual("spring_injection_type_not_resolved", claim.body["graph"]["injects_unresolved"][0]["reason"])
        # DI evidence is not overloaded onto Java invocation relationships.
        self.assertEqual([], claim.body["graph"]["injects"])
        td = tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup)
        repo = init_repo(Path(td.name), {"App.java": source}); warm_repo(repo)
        method = Store(repo).get_claim(stable_java_node_claim_id("App.java", "App.run", "method"))
        self.assertEqual([], method.body["graph"]["callees"])

    def test_ids_and_evidence_are_stable(self):
        source = '''import org.springframework.stereotype.Component;
import javax.inject.Inject;
@Component class Engine {} class App { @Inject Engine engine; }'''
        first = self._claim(source, "App").body["graph"]["injects"]
        second = self._claim(source, "App").body["graph"]["injects"]
        self.assertEqual(first, second)

    def test_explicit_constructor_injection_resolves_source_bean(self):
        source = '''
import org.springframework.stereotype.Service;
import org.springframework.beans.factory.annotation.Autowired;
@Service class Engine {}
class App { @Autowired App(Engine engine) {} void run() {} }
'''
        claim = self._claim(source, "App")
        edge = claim.body["graph"]["injects"][0]
        self.assertEqual("constructor", edge["inject_kind"])
        self.assertEqual(stable_java_node_claim_id("App.java", "Engine", "class"), edge["target_id"])

    def test_explicit_method_injection_and_bean_producer(self):
        source = '''
import org.springframework.context.annotation.Bean;
import org.springframework.beans.factory.annotation.Autowired;
class Engine {}
class Config { @Bean Engine engine() { return new Engine(); } }
class App { @Autowired void configure(Engine engine) {} }
'''
        claim = self._claim(source, "App")
        edge = claim.body["graph"]["injects"][0]
        self.assertEqual("method", edge["inject_kind"])
        self.assertEqual(stable_java_node_claim_id("App.java", "Config.engine", "method"), edge["target_id"])

    def test_literal_qualifier_disambiguates_explicit_bean_names(self):
        source = '''
import org.springframework.context.annotation.Bean;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
class Engine {}
class Config {
 @Bean("fast") Engine fastEngine() { return new Engine(); }
 @Bean("slow") Engine slowEngine() { return new Engine(); }
}
class App { @Autowired App(@Qualifier("fast") Engine engine) {} }
'''
        claim = self._claim(source, "App")
        edge = claim.body["graph"]["injects"][0]
        self.assertEqual(stable_java_node_claim_id("App.java", "Config.fastEngine", "method"), edge["target_id"])

    def test_decoy_annotations_and_unannotated_constructor_do_not_inject(self):
        source = '''
import fake.Bean; import fake.Autowired;
class Engine {} class Config { @Bean Engine engine() { return new Engine(); } }
class App { @Autowired App(Engine engine) {} }
'''
        self.assertEqual([], self._claim(source, "App").body["graph"]["injects"])

    def test_multiple_beans_and_generic_parameter_are_unresolved(self):
        source = '''
import java.util.List;
import org.springframework.context.annotation.Bean;
import org.springframework.beans.factory.annotation.Autowired;
class Engine {} class Config {
 @Bean Engine one() { return new Engine(); }
 @Bean Engine two() { return new Engine(); }
}
class App { @Autowired App(Engine engine, List<Engine> engines) {} }
'''
        graph = self._claim(source, "App").body["graph"]
        self.assertEqual([], graph["injects"])
        self.assertEqual({"spring_injection_multiple_beans", "spring_injection_parameter_not_plain_type"},
                         {x["reason"] for x in graph["injects_unresolved"]})

    def test_constructor_injection_does_not_fabricate_calls(self):
        source = '''
import org.springframework.stereotype.Service;
import org.springframework.beans.factory.annotation.Autowired;
@Service class Engine {} class App { @Autowired App(Engine engine) {} void run() {} }
'''
        td = tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup)
        repo = init_repo(Path(td.name), {"App.java": source}); warm_repo(repo)
        method = Store(repo).get_claim(stable_java_node_claim_id("App.java", "App.run", "method"))
        self.assertEqual([], method.body["graph"]["callees"])


if __name__ == "__main__":
    unittest.main()

@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaSpringCrossFileEvidenceTests(unittest.TestCase):
    def _graph(self, files, path="src/main/java/app/App.java", qualname="App"):
        td=tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup)
        repo=init_repo(Path(td.name), files); warm_repo(repo)
        return Store(repo).get_claim(stable_java_node_claim_id(path, qualname, "class")).body["graph"]

    def test_cross_file_explicit_imported_component_injection(self):
        graph=self._graph({
          "src/main/java/engine/Engine.java": "package engine;\nimport org.springframework.stereotype.Service;\n@Service public class Engine {}",
          "src/main/java/app/App.java": "package app;\nimport engine.Engine;\nimport org.springframework.beans.factory.annotation.Autowired;\nclass App { @Autowired Engine engine; }"})
        self.assertEqual([stable_java_node_claim_id("src/main/java/engine/Engine.java", "Engine", "class")], [x["target_id"] for x in graph["injects"]])

    def test_cross_file_bean_literal_qualifier_and_ambiguity(self):
        files={
          "src/main/java/engine/Engine.java": "package engine;\npublic class Engine {}",
          "src/main/java/config/Config.java": '''package config;
import engine.Engine;
import org.springframework.context.annotation.Bean;
class Config { @Bean("fast") Engine fast(){ return new Engine(); } @Bean("slow") Engine slow(){ return new Engine(); } }''',
          "src/main/java/app/App.java": '''package app;
import engine.Engine;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Qualifier;
class App { @Autowired App(@Qualifier("fast") Engine e) {} }''' }
        graph=self._graph(files)
        self.assertEqual(stable_java_node_claim_id("src/main/java/config/Config.java", "Config.fast", "method"), graph["injects"][0]["target_id"])
        files["src/main/java/app/App.java"]='package app;\nimport engine.Engine;\nimport org.springframework.beans.factory.annotation.Autowired;\nclass App { @Autowired App(Engine e) {} }'
        graph=self._graph(files)
        self.assertEqual([], graph["injects"]); self.assertEqual("spring_injection_multiple_beans", graph["injects_unresolved"][0]["reason"])

    def test_cross_file_decoy_annotation_is_rejected(self):
        graph=self._graph({
          "src/main/java/engine/Engine.java": "package engine;\nimport fake.Service;\n@Service public class Engine {}",
          "src/main/java/app/App.java": "package app;\nimport engine.Engine;\nimport org.springframework.beans.factory.annotation.Autowired;\nclass App { @Autowired Engine engine; }"})
        self.assertEqual([], graph["injects"]); self.assertEqual("spring_injection_type_not_resolved", graph["injects_unresolved"][0]["reason"])

    def test_cross_file_interface_has_one_source_proven_component_implementation(self):
        graph=self._graph({
          "src/main/java/api/Engine.java": "package api;\npublic interface Engine {}",
          "src/main/java/impl/FastEngine.java": "package impl;\nimport api.Engine;\nimport org.springframework.stereotype.Service;\n@Service public class FastEngine implements Engine {}",
          "src/main/java/app/App.java": "package app;\nimport api.Engine;\nimport org.springframework.beans.factory.annotation.Autowired;\nclass App { @Autowired Engine engine; }"})
        self.assertEqual([stable_java_node_claim_id("src/main/java/impl/FastEngine.java", "FastEngine", "class")], [x["target_id"] for x in graph["injects"]])

    def test_cross_file_interface_multiple_components_is_unknown(self):
        graph=self._graph({
          "src/main/java/api/Engine.java": "package api;\npublic interface Engine {}",
          "src/main/java/impl/FastEngine.java": "package impl;\nimport api.Engine;\nimport org.springframework.stereotype.Service;\n@Service public class FastEngine implements Engine {}",
          "src/main/java/impl/SlowEngine.java": "package impl;\nimport api.Engine;\nimport org.springframework.stereotype.Service;\n@Service public class SlowEngine implements Engine {}",
          "src/main/java/app/App.java": "package app;\nimport api.Engine;\nimport org.springframework.beans.factory.annotation.Autowired;\nclass App { @Autowired Engine engine; }"})
        self.assertEqual([], graph["injects"])
        self.assertEqual("spring_injection_multiple_beans", graph["injects_unresolved"][0]["reason"])

@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaSpringFoundationMetadataTests(unittest.TestCase):
    def _nodes(self, source):
        td=tempfile.TemporaryDirectory(); self.addCleanup(td.cleanup)
        repo=init_repo(Path(td.name), {'App.java': source}); warm_repo(repo); store=Store(repo)
        return store

    def test_literal_lifecycle_and_transaction_declarations(self):
        s='''
import org.springframework.context.annotation.Profile;
import org.springframework.context.annotation.Scope;
import org.springframework.context.annotation.Lazy;
import org.springframework.context.annotation.DependsOn;
import org.springframework.context.annotation.Primary;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.transaction.annotation.Propagation;
import org.springframework.transaction.annotation.Isolation;
@Profile({"prod","blue"}) @Scope("prototype") @Lazy(false) @DependsOn({"db","cache"}) @Primary
@Transactional(readOnly=true, propagation=Propagation.REQUIRES_NEW, isolation=Isolation.SERIALIZABLE)
class App { @Transactional(readOnly=false) void save() {} }
'''
        st=self._nodes(s); cls=st.get_claim(stable_java_node_claim_id('App.java','App','class')); md=cls.body['graph']['spring_declaration']
        self.assertEqual(['prod','blue'], md['profiles']); self.assertEqual('prototype',md['scope']); self.assertFalse(md['lazy']); self.assertTrue(md['primary'])
        self.assertEqual('REQUIRES_NEW',md['transactional']['propagation']); self.assertEqual('SERIALIZABLE',md['transactional']['isolation'])
        method=st.get_claim(stable_java_node_claim_id('App.java','App.save','method')); self.assertEqual({'boundary':'method','read_only':False}, method.body['graph']['spring_declaration']['transactional'])
        self.assertEqual([], method.body['graph']['callees'])

    def test_decoy_dynamic_spel_and_condition_are_deferred(self):
        s='''import fake.Profile;
import org.springframework.context.annotation.Scope;
import org.springframework.boot.autoconfigure.condition.ConditionalOnClass;
@Profile("prod") @Scope("${scope}") @ConditionalOnClass(String.class) class App {}'''
        c=self._nodes(s).get_claim(stable_java_node_claim_id('App.java','App','class')); reasons={x['reason'] for x in c.body['graph']['spring_declaration_unresolved']}
        self.assertIn('spring_annotation_not_exact_explicit_import',reasons); self.assertIn('spring_annotation_value_spel_or_dynamic',reasons); self.assertIn('spring_condition_classpath_or_dynamic_deferred',reasons)

    def test_exactly_one_primary_resolves_and_two_primaries_fail_closed(self):
        base='''import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Primary;
import org.springframework.beans.factory.annotation.Autowired;
class Engine {}
class Config {
%s
}
class App { @Autowired App(Engine e) {} }'''
        one=base % ' @Bean @Primary Engine one(){return new Engine();}\n @Bean Engine two(){return new Engine();}'
        g=self._nodes(one).get_claim(stable_java_node_claim_id('App.java','App','class')).body['graph']; self.assertEqual('Config.one',g['injects'][0]['target_qualname'])
        two=base % ' @Bean @Primary Engine one(){return new Engine();}\n @Bean @Primary Engine two(){return new Engine();}'
        g=self._nodes(two).get_claim(stable_java_node_claim_id('App.java','App','class')).body['graph']; self.assertEqual([],g['injects']); self.assertEqual('spring_injection_multiple_beans',g['injects_unresolved'][0]['reason'])
