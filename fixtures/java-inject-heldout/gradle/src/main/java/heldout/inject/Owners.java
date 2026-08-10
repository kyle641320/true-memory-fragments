package heldout.inject;
import jakarta.inject.Inject;
class Owners {
  @Inject Owners(Object dependency) {}
  @Inject Object client;
  @Inject void setClient(Object value) {}
}
