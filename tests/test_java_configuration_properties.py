from __future__ import annotations
import tempfile
from pathlib import Path
import unittest
from tmf.ids import stable_configuration_properties_edge_claim_id, stable_java_node_claim_id
from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.store import Store
from tmf.warm import warm_repo
from tests.test_java_inherit import init_repo

@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaConfigurationPropertiesTests(unittest.TestCase):
    def warm(self, files):
        td=tempfile.TemporaryDirectory(); repo=init_repo(Path(td.name), files); warm_repo(repo); return td, repo, Store(repo)

    def test_class_record_alias_and_factory_literal_metadata(self):
        source='''
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Bean;
@ConfigurationProperties(prefix="app.http") class HttpProps { String host; }
@ConfigurationProperties("app.db") record DbProps(String url) {}
class Config { @Bean @ConfigurationProperties(value = "app.worker") Worker worker(){ return null; } }
class Worker {}
'''
        td,repo,store=self.warm({'Props.java':source}); self.addCleanup(td.cleanup)
        expected=[('HttpProps','class','app.http'),('DbProps','class','app.db'),('Config.worker','method','app.worker')]
        for qual,kind,prefix in expected:
            node=stable_java_node_claim_id('Props.java',qual,kind)
            claim=store.get_claim(stable_configuration_properties_edge_claim_id(node,prefix))
            self.assertIsNotNone(claim); self.assertEqual(claim.body['prefix'],prefix); self.assertEqual(claim.evidence,'attributed')
            self.assertEqual(store.get_claim(node).body['graph']['configuration_properties']['prefix'],prefix)
        method=store.get_claim(stable_java_node_claim_id('Props.java','Config.worker','method'))
        self.assertEqual(method.body['graph']['callees'], [])
        self.assertEqual(method.body['graph']['writes'], [])

    def test_decoy_dynamic_unsupported_target_and_factory_are_unresolved_or_absent(self):
        files={
          'Decoy.java':'import fake.ConfigurationProperties;\n@ConfigurationProperties("fake") class Decoy {}',
          'Dynamic.java':'import org.springframework.boot.context.properties.ConfigurationProperties;\n@ConfigurationProperties(prefix=PREFIX) class Dynamic {}',
          'Factory.java':'import org.springframework.boot.context.properties.ConfigurationProperties;\nclass Factory {\n @ConfigurationProperties("x") Object make(){ return null; }\n}',
          'Field.java':'import org.springframework.boot.context.properties.ConfigurationProperties;\nclass Field { @ConfigurationProperties("x") String x; }'}
        td,repo,store=self.warm(files); self.addCleanup(td.cleanup)
        self.assertNotIn('configuration_properties',store.get_claim(stable_java_node_claim_id('Decoy.java','Decoy','class')).body['graph'])
        dynamic=store.get_claim(stable_java_node_claim_id('Dynamic.java','Dynamic','class')).body['graph']
        self.assertEqual(dynamic['configuration_properties_unresolved'][0]['reason'],'spring_configuration_properties_prefix_not_literal')
        factory=store.get_claim(stable_java_node_claim_id('Factory.java','Factory.make','method')).body['graph']
        self.assertEqual(factory['configuration_properties_unresolved'][0]['reason'],'spring_configuration_properties_factory_not_explicit_bean')
        self.assertFalse(any(c.body.get('edge_kind')=='configuration_properties' for c in store.iter_claims() if isinstance(c.body,dict)))

    def test_cross_file_coexists_without_binding_relationships_and_ids_are_stable(self):
        files={'Props.java':'package p;\nimport org.springframework.boot.context.properties.ConfigurationProperties;\n@ConfigurationProperties(prefix="svc") public class Props {}',
               'Use.java':'package p;\nclass Use { Props props; }'}
        td,repo,store=self.warm(files); self.addCleanup(td.cleanup)
        node=stable_java_node_claim_id('Props.java','Props','class'); cid=stable_configuration_properties_edge_claim_id(node,'svc')
        first=store.get_claim(cid); self.assertIsNotNone(first); self.assertEqual(len(first.bindings),1)
        warm_repo(repo); self.assertEqual(Store(repo).get_claim(cid).id,cid)
        use=Store(repo).get_claim(stable_java_node_claim_id('Use.java','Use','class')).body['graph']
        self.assertNotIn('configuration_properties',use); self.assertEqual(use['injects'],[])
