package heldout.catalog;
import fake.persistence.Entity;
import jakarta.persistence.Table;
@Entity
@Table(name=TABLE_NAME)
class PersistenceDecoy { static final String TABLE_NAME="should_not_resolve"; }
