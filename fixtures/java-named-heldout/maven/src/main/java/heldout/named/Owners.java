package heldout.named;
import jakarta.inject.Named;
@Named
class Owners {
  @Named Object dependency;
  @Named Object produce() { return dependency; }
  static class Nested { @Named static Object marker; }
}
