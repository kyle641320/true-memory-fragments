import json, os, subprocess, tempfile, unittest
from pathlib import Path
from tmf.derive import derive_claims_for_path
from tmf.git import GitRepo
from tmf.java_semantic import JavaSemanticFactsBackend
ROOT=Path(__file__).resolve().parents[1]
class Round9(unittest.TestCase):
 def runp(self,repo,out,extra=()):
  paths=['src/p/Api.java','src/p/Impl.java','src/p/Use.java']; subprocess.run(['python3',str(ROOT/'tools/javac_semantic_facts.py'),str(repo),*paths,*extra,'-o',str(out)],check=True)
 def fixture(self,td):
  r=Path(td)/'r'; (r/'src/p').mkdir(parents=True)
  for x in ('Api.java','Impl.java','Use.java'): (r/'src/p'/x).write_text((ROOT/'fixtures/java-semantic-round9/src/p'/x).read_text())
  subprocess.run(['git','init','-b','master'],cwd=r,check=True,stdout=subprocess.DEVNULL);subprocess.run(['git','config','user.email','x@y'],cwd=r);subprocess.run(['git','config','user.name','x'],cwd=r);subprocess.run(['git','add','.'],cwd=r);subprocess.run(['git','commit','-m','x'],cwd=r,check=True,stdout=subprocess.DEVNULL);return r
 def test_multi_file_override_polymorphic_and_participant_stale(self):
  with tempfile.TemporaryDirectory() as td:
   r=self.fixture(td); f=Path(td)/'facts';f.mkdir();o=f/'batch.json';self.runp(r,o);d=json.loads(o.read_text());self.assertEqual(len(d['documents']),3)
   kinds=[x['kind'] for q in d['documents'] for x in q['facts']];self.assertIn('overrides',kinds);self.assertIn('call',kinds)
   use=[q for q in d['documents'] if q['path'].endswith('Use.java')][0];call=[x for x in use['facts'] if x['kind']=='call'][0];self.assertEqual(call['target_owner'],'p.Api')
   b=JavaSemanticFactsBackend(f,enabled=True);self.assertTrue(any(x.id.startswith('claim_java_semantic_') for x in derive_claims_for_path(GitRepo(r),'src/p/Use.java',semantic_backend=b)))
   (r/'src/p/Api.java').write_text((r/'src/p/Api.java').read_text()+'// changed');self.assertFalse(any(x.id.startswith('claim_java_semantic_') for x in derive_claims_for_path(GitRepo(r),'src/p/Use.java',semantic_backend=b)))
 def test_classpath_canonical_hash_changes_and_missing_fails(self):
  with tempfile.TemporaryDirectory() as td:
   r=self.fixture(td); a=Path(td)/'a';a.mkdir(); (a/'x').write_text('1');o1=Path(td)/'1.json';self.runp(r,o1,('--classpath',str(a)));h1=json.loads(o1.read_text())['classpath_fingerprint'];(a/'x').write_text('2');o2=Path(td)/'2.json';self.runp(r,o2,('--classpath',str(a)));self.assertNotEqual(h1,json.loads(o2.read_text())['classpath_fingerprint'])
   z=subprocess.run(['python3',str(ROOT/'tools/javac_semantic_facts.py'),str(r),'src/p/Api.java','--classpath',str(Path(td)/'missing')]);self.assertNotEqual(z.returncode,0)
 def test_discovery_is_explicit_read_only_partial(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'pom.xml').write_text('<project/>'); marker=r/'executed'; wrapper=r/'mvnw'; wrapper.write_text('#!/bin/sh\ntouch "$1"\n'); wrapper.chmod(0o755)
   bindir=r/'bin';bindir.mkdir()
   for name in ('mvn','gradle'):
    p=bindir/name;p.write_text(f'#!/bin/sh\ntouch "{marker}"\n');p.chmod(0o755)
   env=dict(os.environ,PATH=str(bindir)+os.pathsep+os.environ.get('PATH',''))
   z=subprocess.check_output(['python3',str(ROOT/'tools/javac_semantic_facts.py'),str(r),'--module','.','--discover-only'],text=True,env=env);d=json.loads(z)
   self.assertEqual(d['kind'],'maven');self.assertEqual(d['status'],'partial');self.assertEqual(d['annotation_processing'],'disabled');self.assertNotIn('classpath',d);self.assertFalse(marker.exists())
 def test_cli_has_no_build_resolution_flags(self):
  help_text=subprocess.check_output(['python3',str(ROOT/'tools/javac_semantic_facts.py'),'--help'],text=True)
  forbidden=('--'+'resolve'+'-'+'offline','--'+'maven'+'-'+'cache')
  for flag in forbidden:self.assertNotIn(flag,help_text)
if __name__=='__main__':unittest.main()
