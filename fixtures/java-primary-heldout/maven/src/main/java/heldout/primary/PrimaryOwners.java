package heldout.primary;
import org.springframework.context.annotation.Primary;
@Primary
class PrimaryOwners {
  @Primary Object select() { return null; }
  @Primary Object select(String key) { return key; }
}
@Primary
interface PrimaryContract {}
