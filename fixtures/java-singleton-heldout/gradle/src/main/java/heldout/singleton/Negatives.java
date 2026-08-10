package heldout.singleton;
import jakarta.inject.Singleton;
@Singleton interface WrongOwnerKind {}
@Singleton enum AnotherWrongOwnerKind { VALUE }
class Negatives {
  void local() { @Singleton class Local {} }
}
