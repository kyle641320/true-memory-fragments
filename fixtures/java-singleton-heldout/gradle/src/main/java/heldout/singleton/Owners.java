package heldout.singleton;
import jakarta.inject.Singleton;
@Singleton
class Owners {
  @Singleton static class Nested {}
}
