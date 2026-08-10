from __future__ import annotations
import tempfile, unittest
from pathlib import Path
from tmf.ids import stable_java_node_claim_id
from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.store import Store
from tmf.warm import warm_repo
from tests.test_java_inherit import init_repo

@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaRepositoryTests(unittest.TestCase):
 def graph(self, files, path, q, kind):
  with tempfile.TemporaryDirectory() as td:
   repo=init_repo(Path(td),files); warm_repo(repo)
   return Store(repo).get_claim(stable_java_node_claim_id(path,q,kind)).body['graph']
 def test_jpa_repository_and_literal_queries(self):
  files={'User.java':'package app;\nimport jakarta.persistence.Entity;\n@Entity class User {}',
   'UserRepo.java':'''package app;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
interface UserRepo extends JpaRepository<User, Long> {
 @Query(value="select u from User u where u.name=?1")
 User findNamed(String name);
 @Query(value="select * from users", nativeQuery=true)
 User nativeOne();
 User findByEmail(String email);
}'''}
  g=self.graph(files,'UserRepo.java','UserRepo','interface')['repository_declaration']; x=g['inherited_repository_types'][0]
  self.assertEqual(('org.springframework.data.jpa.repository.JpaRepository','app.User','java.lang.Long'),(x['repository_type'],x['domain_type'],x['id_type']))
  q=self.graph(files,'UserRepo.java','UserRepo.nativeOne','method')['repository_declaration']['query_declaration']
  self.assertEqual(('native_sql',True,'select * from users'),(q['language'],q['native'],q['text']))
  d=self.graph(files,'UserRepo.java','UserRepo.findByEmail','method')['repository_declaration']; self.assertEqual('findByEmail',d['derived_query_name']); self.assertNotIn('query_declaration',d)
 def test_decoys_dynamic_and_wildcard_are_unresolved(self):
  s='''import fake.JpaRepository; import fake.Query;
interface UserRepo<T> extends JpaRepository<?, T> { @Query(value=Q) Object find(); }'''
  g=self.graph({'UserRepo.java':s},'UserRepo.java','UserRepo','interface')
  self.assertNotIn('repository_declaration',g)
if __name__=='__main__': unittest.main()
