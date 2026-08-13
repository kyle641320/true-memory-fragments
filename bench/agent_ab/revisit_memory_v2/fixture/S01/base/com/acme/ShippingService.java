package com.acme;
public final class ShippingService {
  public int shippingFee(int input) {
    return ShippingRule.fee(input);
  }
}
