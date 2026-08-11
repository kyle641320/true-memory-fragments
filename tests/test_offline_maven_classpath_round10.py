import json, os, subprocess, tempfile, unittest, zipfile
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'tools'))
from offline_maven_classpath import resolve

P='''<project xmlns="http://maven.apache.org/POM/4.0.0"><modelVersion>4.0.0</modelVersion>{deps}</project>'''
D='''<dependencies><dependency><groupId>{g}</groupId><artifactId>{a}</artifactId><version>{v}</version></dependency></dependencies>'''
class OfflineMavenTest(unittest.TestCase):
 def artifact(self,c,g,a,v,deps=''):
  p=c/Path(*g.split('.'))/a/v;p.mkdir(parents=True)
  with zipfile.ZipFile(p/f'{a}-{v}.jar','w') as z: z.writestr('META-INF/MANIFEST.MF','Manifest-Version: 1.0\n')
  (p/f'{a}-{v}.pom').write_text(P.format(deps=deps))
 def test_transitive_closure_is_complete_and_canonical(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td)/'r'; c=Path(td)/'cache'; (r/'app').mkdir(parents=True); c.mkdir()
   (r/'app/pom.xml').write_text(P.format(deps=D.format(g='x',a='a',v='1')))
   self.artifact(c,'x','a','1',D.format(g='x',a='b',v='2'));self.artifact(c,'x','b','2')
   d=resolve(r,'app',c); self.assertEqual(d['status'],'complete');self.assertEqual([x['coordinate'] for x in d['classpath']],['x:a:1','x:b:2']);self.assertTrue(d['classpath_fingerprint'].startswith('sha256:'))
 def test_uncertainty_is_partial(self):
  cases=['<profiles/>','<properties><x>1</x></properties>','<build><plugins/></build>','<parent><groupId>x</groupId><artifactId>p</artifactId><version>1</version></parent>','<dependencyManagement/>']
  for bad in cases:
   with self.subTest(bad=bad), tempfile.TemporaryDirectory() as td:
    r=Path(td)/'r';c=Path(td)/'c';r.mkdir();c.mkdir();(r/'pom.xml').write_text(P.format(deps=bad));self.assertEqual(resolve(r,'.',c)['status'],'partial')
 def test_xxe_and_dynamic_and_missing_are_partial(self):
  for text in ['<!DOCTYPE x [<!ENTITY e SYSTEM "file:///etc/passwd">]><project>&e;</project>',P.format(deps=D.format(g='x',a='a',v='${v}')),P.format(deps=D.format(g='x',a='a',v='1'))]:
   with tempfile.TemporaryDirectory() as td:
    r=Path(td)/'r';c=Path(td)/'c';r.mkdir();c.mkdir();(r/'pom.xml').write_text(text);self.assertEqual(resolve(r,'.',c)['status'],'partial')
 def test_symlink_cache_escape_is_partial(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td)/'r';c=Path(td)/'c';out=Path(td)/'out';r.mkdir();c.mkdir();out.mkdir();(r/'pom.xml').write_text(P.format(deps=D.format(g='x',a='a',v='1')));(c/'x').symlink_to(out,target_is_directory=True);self.assertEqual(resolve(r,'.',c)['status'],'partial')
 def test_cli_resolves_selected_module_and_runs_real_javac(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td)/'r'; c=Path(td)/'cache'; c.mkdir()
   for module in ('app','other'):
    (r/module/'src').mkdir(parents=True); (r/module/'pom.xml').write_text(P.format(deps=D.format(g='x',a='a',v='1')))
   (r/'app/src/A.java').write_text('class A { void a(){ System.out.println("x"); } }')
   self.artifact(c,'x','a','1')
   out=subprocess.check_output(['python3',str(ROOT/'tools/javac_semantic_facts.py'),str(r),'app/src/A.java','--module','app','--resolve-offline','--maven-cache',str(c)],text=True)
   d=json.loads(out); self.assertEqual(d['build_identity']['status'],'complete'); self.assertEqual(d['build_identity']['module'],'app'); self.assertGreater(len(d['facts']),0)
 def test_gradle_remains_unsupported(self):
  with tempfile.TemporaryDirectory() as td:
   r=Path(td);(r/'build.gradle').write_text('dependencies {}')
   d=json.loads(subprocess.check_output(['python3',str(ROOT/'tools/javac_semantic_facts.py'),str(r),'--module','.','--discover-only'],text=True));self.assertEqual(d['kind'],'gradle');self.assertEqual(d['status'],'partial')
if __name__=='__main__': unittest.main()
