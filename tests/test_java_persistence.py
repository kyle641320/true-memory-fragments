from __future__ import annotations
import tempfile, unittest
from pathlib import Path
from tmf.ids import stable_java_node_claim_id
from tmf.java_extract import JAVA_DEGRADE_HINT, java_status
from tmf.store import Store
from tmf.warm import warm_repo
from tests.test_java_inherit import init_repo

@unittest.skipUnless(java_status().available, JAVA_DEGRADE_HINT)
class JavaPersistenceTests(unittest.TestCase):
 def graph(self, source, q, kind):
  with tempfile.TemporaryDirectory() as td:
   repo=init_repo(Path(td),{'Order.java':source}); warm_repo(repo)
   return Store(repo).get_claim(stable_java_node_claim_id('Order.java',q,kind)).body['graph']
 def test_jakarta_type_and_field_literal_metadata(self):
  s='''import jakarta.persistence.Entity;
import jakarta.persistence.Table;
import jakarta.persistence.IdClass;
import jakarta.persistence.Id;
import jakarta.persistence.Column;
@Entity
@Table(name="orders", schema="sales", catalog="main")
@IdClass(Key.class)
class Order {
 @Id
 @Column(name="order_id", table="orders")
 Long id;
}'''
  md=self.graph(s,'Order','class')['persistence_declaration']; self.assertEqual(('entity','orders','Key'),(md['persistence_kind'],md['table_name'],md['id_class']))
  fm=self.graph(s,'Order.id','field')['persistence_declaration']; self.assertEqual(('id','order_id'),(fm['identifier_kind'],fm['column_name']))
 def test_javax_embedded_id_and_join_column_method(self):
  s='''import javax.persistence.Entity;
import javax.persistence.EmbeddedId;
import javax.persistence.JoinColumn;
@Entity
class Order {
 @EmbeddedId
 Key key;
 @JoinColumn(name="customer_id", referencedColumnName="id")
 Customer customer() { return null; }
}'''
  self.assertEqual('embedded_id',self.graph(s,'Order.key','field')['persistence_declaration']['identifier_kind'])
  self.assertEqual('id',self.graph(s,'Order.customer','method')['persistence_declaration']['join_column_referenced_column_name'])
 def test_decoy_and_dynamic_are_unresolved_not_inferred(self):
  s='''import fake.Entity;
import jakarta.persistence.Table;
@Entity
@Table(name=TABLE)
class Order {}'''
  g=self.graph(s,'Order','class'); reasons={x['reason'] for x in g['persistence_declaration_unresolved']}
  self.assertEqual({'java_persistence_annotation_not_exact_explicit_import','java_persistence_attribute_not_literal'},reasons); self.assertNotIn('persistence_declaration',g)
if __name__=='__main__': unittest.main()
