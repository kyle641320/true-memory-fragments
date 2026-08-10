package heldout.named;
import jakarta.inject.Named;
@Named("explicit")
class Negatives {
  @Named Object first, second;
  void parameter(@Named Object value) {}
  void local() { @Named class Local {} }
}
