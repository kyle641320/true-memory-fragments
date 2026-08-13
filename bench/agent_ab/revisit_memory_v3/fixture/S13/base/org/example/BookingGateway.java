package org.example;
public final class BookingGateway {
  private final SeatPolicy policy = new SeatPolicy();
  public int run(int input) { return policy.allowance(input); }
}
