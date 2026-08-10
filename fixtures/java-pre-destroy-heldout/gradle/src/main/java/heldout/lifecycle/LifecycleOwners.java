package heldout.lifecycle;
import jakarta.annotation.PreDestroy;
class LifecycleOwners {
  @PreDestroy void initialize() {}
  @PreDestroy void initialize(String ignored) {}
}
