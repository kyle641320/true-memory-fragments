package org.example;
public final class StreamCoordinator {
  private final BufferPlan policy = new BufferPlan();
  public int run(int input) { return policy.capacity(input); }
}
