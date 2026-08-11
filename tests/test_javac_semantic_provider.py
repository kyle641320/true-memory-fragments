from __future__ import annotations
import json, subprocess, tempfile, unittest
from pathlib import Path
from tmf.java_semantic import JavaSemanticFactsBackend
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo
ROOT=Path(__file__).resolve().parents[1]
class JavacProviderTests(unittest.TestCase):
 def test_real_javac_overload_slice_and_stale_negative(self):
  with tempfile.TemporaryDirectory() as td:
   repo=Path(td)/'repo'; repo.mkdir(); src=repo/'src/p/Overload.java'; src.parent.mkdir(parents=True); src.write_text((ROOT/'fixtures/java-semantic-round8/src/p/Overload.java').read_text())
   subprocess.run(['git','init','-b','master'],cwd=repo,check=True,stdout=subprocess.DEVNULL); subprocess.run(['git','config','user.email','x@y'],cwd=repo); subprocess.run(['git','config','user.name','x'],cwd=repo); subprocess.run(['git','add','.'],cwd=repo); subprocess.run(['git','commit','-m','x'],cwd=repo,check=True,stdout=subprocess.DEVNULL)
   facts=Path(td)/'facts'; facts.mkdir(); out=facts/'overload.json'
   subprocess.run(['python3',str(ROOT/'tools/javac_semantic_facts.py'),str(repo),'src/p/Overload.java','-o',str(out)],check=True)
   doc=json.loads(out.read_text()); self.assertEqual(doc['provider'],'jdk-javac-api'); self.assertEqual(doc['facts'][0]['target_descriptor'],'(Ljava/lang/String;)V')
   claims=derive_claims_for_path(GitRepo(repo),'src/p/Overload.java',semantic_backend=JavaSemanticFactsBackend(facts,enabled=True)); sem=[x for x in claims if x.id.startswith('claim_java_semantic_')]
   calls=[x for x in sem if x.body['semantic_fact_kind']=='call']; self.assertEqual(len(calls),1); self.assertEqual(calls[0].body['target_owner'],'p.Overload')
   src.write_text(src.read_text()+'// stale\n'); claims=derive_claims_for_path(GitRepo(repo),'src/p/Overload.java',semantic_backend=JavaSemanticFactsBackend(facts,enabled=True)); self.assertFalse(any(x.id.startswith('claim_java_semantic_') for x in claims))
 def test_compile_failure_emits_no_document(self):
  with tempfile.TemporaryDirectory() as td:
   repo=Path(td); (repo/'Bad.java').write_text('class Bad { void x(){ missing( } }')
   r=subprocess.run(['python3',str(ROOT/'tools/javac_semantic_facts.py'),str(repo),'Bad.java'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
   self.assertNotEqual(r.returncode,0); self.assertEqual(r.stdout,b'')
if __name__=='__main__': unittest.main()
