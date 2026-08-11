from __future__ import annotations
import json, subprocess, tempfile, unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo
from tmf.java_semantic import FORMAT, JavaSemanticFactsBackend, content_sha256


def run(cmd, cwd): subprocess.run(cmd, cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

class JavaSemanticFactsTests(unittest.TestCase):
    def setUp(self):
        self.td=tempfile.TemporaryDirectory(); self.root=Path(self.td.name); self.repo=self.root/'repo'; self.repo.mkdir(); self.facts=self.root/'facts'; self.facts.mkdir()
        run(['git','init','-b','master'],self.repo); run(['git','config','user.email','x@y'],self.repo); run(['git','config','user.name','x'],self.repo)
        self.source='package p;\nclass A { void f(){ g(); } void g(){} }\n'; (self.repo/'A.java').write_text(self.source); run(['git','add','A.java'],self.repo); run(['git','commit','-m','x'],self.repo)
    def tearDown(self): self.td.cleanup()
    def doc(self, facts=None, **kw):
        base_fact={'kind':'call','source_symbol':'java:p.A#f().','target_symbol':'java:p.A#g().','source_owner':'p.A','source_descriptor':'()V','target_owner':'p.A','target_descriptor':'()V','anchor':{'start_offset':31,'end_offset':34},'range':{'start_line':1,'start_column':20,'end_line':1,'end_column':23}}
        d={'format':FORMAT,'path':'A.java','provider':'fixture','provider_version':'1','tool':'offline-fixture','tool_version':'1','classpath_fingerprint':'cp:0','build_fingerprint':'build:0','content_sha256':content_sha256(self.source),'facts':facts or [base_fact]}; d.update(kw); return d
    def ingest(self, enabled=True): return derive_claims_for_path(GitRepo(self.repo),'A.java',semantic_backend=JavaSemanticFactsBackend(self.facts,enabled=enabled))
    def test_valid_is_deterministic_and_coexists_without_changing_syntax(self):
        (self.facts/'a.json').write_text(json.dumps(self.doc()))
        a=self.ingest(); b=self.ingest(); sem=lambda xs:[x for x in xs if x.id.startswith('claim_java_semantic_')]
        self.assertEqual([x.id for x in sem(a)],[x.id for x in sem(b)]); self.assertEqual(len(sem(a)),1)
        self.assertTrue(any(x.body.get('extraction_tier')=='java-treesitter-syntactic' for x in a)); self.assertEqual(sem(a)[0].evidence,'attributed'); self.assertEqual(sem(a)[0].body['extraction_tier'],'compiler-attributed')
    def test_stale_mutation_and_deletion_emit_nothing(self):
        (self.facts/'a.json').write_text(json.dumps(self.doc(content_sha256='0'*64))); self.assertFalse(any(x.id.startswith('claim_java_semantic_') for x in self.ingest()))
        (self.repo/'A.java').write_text(self.source+'// mutate\n'); self.assertFalse(any(x.id.startswith('claim_java_semantic_') for x in self.ingest()))
        (self.facts/'a.json').unlink(); self.assertFalse(any(x.id.startswith('claim_java_semantic_') for x in self.ingest()))
    def test_path_escape_ambiguous_symbol_and_malformed_range_rejected(self):
        cases=[self.doc(path='../A.java'),self.doc(facts=[{'kind':'call','source_symbol':'f','target_symbol':'g','range':{'start_line':1,'start_column':0,'end_line':1,'end_column':1}}]),self.doc(facts=[{'kind':'call','source_symbol':'java:p.A#f().','target_symbol':'java:p.A#g().','range':{'start_line':9,'start_column':0,'end_line':9,'end_column':1}}])]
        for i,d in enumerate(cases):
            (self.facts/f'{i}.json').write_text(json.dumps(d)); self.assertFalse(any(x.id.startswith('claim_java_semantic_') for x in self.ingest())); (self.facts/f'{i}.json').unlink()
    def test_conflicting_providers_fail_closed(self):
        (self.facts/'a.json').write_text(json.dumps(self.doc()))
        other_fact={'kind':'uses_type','source_symbol':'java:p.A#f().','target_symbol':'java:p.B#','source_owner':'p.A','source_descriptor':'()V','target_owner':'p.B','target_descriptor':'Lp/B;','anchor':{'start_offset':31,'end_offset':34},'range':{'start_line':1,'start_column':20,'end_line':1,'end_column':23}}
        other=self.doc(provider='other',facts=[other_fact]); (self.facts/'b.json').write_text(json.dumps(other))
        claims=self.ingest(); self.assertFalse(any(x.id.startswith('claim_java_semantic_') for x in claims)); self.assertEqual(claims[0].body['semantic_extraction']['provider_status']['reason'],'conflicting_providers')
    def test_missing_attributed_identity_is_unknown_and_does_not_cover_ast(self):
        weak={'kind':'call','source_symbol':'java:p.A#f().','target_symbol':'java:p.A#g().','range':{'start_line':1,'start_column':20,'end_line':1,'end_column':23}}
        (self.facts/'a.json').write_text(json.dumps(self.doc(facts=[weak])))
        claims=self.ingest(); self.assertFalse(any(x.id.startswith('claim_java_semantic_') for x in claims))
        self.assertTrue(any(x.body.get('extraction_tier')=='java-treesitter-syntactic' for x in claims))

    def test_default_off_degrades_and_does_not_read_provider(self):
        (self.facts/'a.json').write_text('{broken'); claims=self.ingest(False); s=claims[0].body['semantic_extraction']; self.assertFalse(s['available']); self.assertEqual(s['provider_status']['reason'],'default_off')

if __name__=='__main__': unittest.main()
