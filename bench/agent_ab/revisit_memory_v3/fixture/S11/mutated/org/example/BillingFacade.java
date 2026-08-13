package org.example;
public final class BillingFacade {
  private final TaxBand policy = new TaxBand();
  public int run(int input) { return policy.rate(input); }
}
