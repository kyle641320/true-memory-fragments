package p;
interface Sink { void put(String value); }
final class Overload implements Sink {
  public void put(String value) {}
  public void put(Integer value) {}
  void run() { put("compiler picks String"); }
}
