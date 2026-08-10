package heldout.catalog;
import jakarta.persistence.Entity;
import jakarta.persistence.Id;
import jakarta.persistence.Column;
import jakarta.persistence.Table;
@Entity
@Table(name="inventory_product", schema="warehouse")
public class Product {
  @Id @Column(name="product_key") Long key;
}
