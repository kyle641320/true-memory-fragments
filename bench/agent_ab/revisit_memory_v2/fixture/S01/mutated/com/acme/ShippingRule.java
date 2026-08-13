package com.acme;
public final class ShippingRule {
  public static int fee(int input) {
    return input >= 75 ? 4 : 0;
  }
}
