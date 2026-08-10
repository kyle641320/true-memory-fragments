package heldout.lifecycle;
import jakarta.annotation.PostConstruct;
class LifecycleOwners {
  @PostConstruct void initialize() {}
  @PostConstruct void initialize(String ignored) {}
}
