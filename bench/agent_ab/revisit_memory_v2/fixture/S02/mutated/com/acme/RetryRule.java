package com.acme;
public final class RetryRule {
  public static int attempts(int input) {
    return input >= 3 ? 2 : 0;
  }
}
