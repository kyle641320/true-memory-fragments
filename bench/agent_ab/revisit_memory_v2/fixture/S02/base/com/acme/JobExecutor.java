package com.acme;
public final class JobExecutor {
  public int maxAttempts(int input) {
    return RetryRule.attempts(input);
  }
}
