from __future__ import annotations
import tempfile, unittest
from pathlib import Path
from tmf.ids import stable_java_node_claim_id
from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.store import Store
from tmf.warm import warm_repo
from tests.test_java_inherit import init_repo, run

@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaMyBatisTests(unittest.TestCase):
 def claim(self, source, q, kind='method'):
  with tempfile.TemporaryDirectory() as td:
   repo=init_repo(Path(td),{'UserMapper.java':source}); warm_repo(repo)
   return Store(repo).get_claim(stable_java_node_claim_id('UserMapper.java',q,kind))
 def test_exact_mapper_and_four_literal_annotation_kinds(self):
  source='''import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Update;
import org.apache.ibatis.annotations.Delete;
@Mapper interface UserMapper {
 @Select({"select *", " from users where id = #{id}"}) Object find(long id);
 @Insert("insert into users values (#{id})") int add(long id);
 @Update("update users set active=true") int change();
 @Delete("delete from users where id=#{id}") int remove(long id);
}'''
  mapper=self.claim(source,'UserMapper','interface').body['graph']['mybatis_declaration']
  self.assertEqual('mybatis_mapper_interface',mapper['declaration_kind'])
  for method,kind in [('find','Select'),('add','Insert'),('change','Update'),('remove','Delete')]:
   md=self.claim(source,'UserMapper.'+method).body['graph']['mybatis_declaration']
   self.assertEqual('org.apache.ibatis.annotations.'+kind,md['annotation_kind'])
   self.assertEqual('opaque_declaration_only',md['sql_declaration']['effect'])
   self.assertFalse(any(k in md for k in ('tables','columns','reads','writes','calls','transactions','result_mapping')))
 def test_decoys_dynamic_providers_scripts_foreach_and_composed_fail_closed(self):
  source='''import fake.Mapper;
import fake.Select;
import org.apache.ibatis.annotations.Insert;
import org.apache.ibatis.annotations.Update;
import org.apache.ibatis.annotations.Delete;
import org.apache.ibatis.annotations.SelectProvider;
@Mapper interface UserMapper {
 @Select("select 1") Object decoy();
 @Insert(SQL) int dynamic();
 @Update("<script>update x</script>") int script();
 @Delete({"<foreach>", "delete x"}) int foreach();
 @SelectProvider(type=X.class, method="q") Object provider();
 @FindUsers Object composed();
}'''
  mapper=self.claim(source,'UserMapper','interface').body['graph']
  self.assertNotIn('mybatis_declaration',mapper)
  self.assertEqual('mybatis_mapper_annotation_not_exact_explicit_import',mapper['mybatis_declaration_unresolved'][0]['reason'])
  expected={'decoy':'mybatis_sql_annotation_not_exact_explicit_import','dynamic':'mybatis_sql_value_not_literal','script':'mybatis_script_annotation_deferred','foreach':'mybatis_foreach_annotation_deferred','provider':'mybatis_provider_annotation_deferred'}
  for method,reason in expected.items():
   graph=self.claim(source,'UserMapper.'+method).body['graph']
   self.assertIn(reason,{x['reason'] for x in graph['mybatis_declaration_unresolved']})
   self.assertNotIn('mybatis_declaration',graph)
  self.assertNotIn('mybatis_declaration',self.claim(source,'UserMapper.composed').body['graph'])
 def test_hash_freshness_and_delete_reconcile(self):
  source='''import org.apache.ibatis.annotations.Mapper;
import org.apache.ibatis.annotations.Select;
@Mapper interface UserMapper { @Select("select 1") Object find(); }'''
  with tempfile.TemporaryDirectory() as td:
   root=Path(td); repo=init_repo(root,{'UserMapper.java':source}); warm_repo(repo); store=Store(repo)
   claim_id=stable_java_node_claim_id('UserMapper.java','UserMapper.find','method')
   first=store.get_claim(claim_id); self.assertEqual(['select 1'],first.body['graph']['mybatis_declaration']['sql_declaration']['strings'])
   p=repo/'UserMapper.java'; p.write_text(source.replace('select 1','select 2')); run(['git','add','.'],repo); run(['git','commit','-m','mutate'],repo); warm_repo(repo)
   second=store.get_claim(claim_id); self.assertEqual(claim_id,second.id); self.assertEqual(['select 2'],second.body['graph']['mybatis_declaration']['sql_declaration']['strings']); self.assertNotEqual(first.bindings[0].fn_hash,second.bindings[0].fn_hash)
   p.unlink(); run(['git','add','-A'],repo); run(['git','commit','-m','delete'],repo); warm_repo(repo)
   self.assertIsNone(store.get_claim(claim_id))

if __name__=='__main__': unittest.main()
