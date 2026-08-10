package heldout.ledger;
import javax.persistence.Entity;
import javax.persistence.EmbeddedId;
import javax.persistence.Table;
@Entity
@Table(name="ledger_entry")
public class Entry {
 @EmbeddedId
 EntryKey key;
}
class EntryKey {}
