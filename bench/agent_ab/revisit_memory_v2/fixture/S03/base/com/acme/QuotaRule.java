package com.acme;
public final class QuotaRule {
  public static int limit(int input) {
    return input >= 50 ? 80 : 0;
  }
}
