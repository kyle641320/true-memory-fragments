final class RetryPolicy {
  static int delay(int attempt) { return 25 * (attempt + 1); }
}
