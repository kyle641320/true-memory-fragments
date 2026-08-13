package com.acme;
public final class PricePolicy {
  public int discount(int subtotal, boolean vip) {
    if (vip && subtotal >= 150) return 25;
    return 0;
  }
}
