package com.acme;
public final class UploadGateway {
  public int uploadLimit(int input) {
    return QuotaRule.limit(input);
  }
}
