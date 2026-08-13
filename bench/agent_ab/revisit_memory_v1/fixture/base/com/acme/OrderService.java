package com.acme;
public final class OrderService {
  private final PricePolicy policy;
  public OrderService(PricePolicy policy) { this.policy = policy; }
  public int checkout(int subtotal, boolean vip) {
    int discount = policy.discount(subtotal, vip);
    return subtotal - discount;
  }
  public String receiptPrefix() { return "ORDER"; }
}
