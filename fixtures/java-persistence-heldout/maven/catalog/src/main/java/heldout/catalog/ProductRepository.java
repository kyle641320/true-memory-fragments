package heldout.catalog;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
public interface ProductRepository extends JpaRepository<Product, Long> {
  @Query(value="select p from Product p where p.key = ?1") Product lookup(Long key);
  @Query(value="select * from inventory_product where product_key = ?1", nativeQuery=true) Product nativeLookup(Long key);
  Product findByKey(Long key);
}
