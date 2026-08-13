package com.acme;
public final class PricePolicy {
  public int discount(int subtotal, boolean vip) {
    if (vip && subtotal >= 100) return 20;
    return 0;
  }
}
