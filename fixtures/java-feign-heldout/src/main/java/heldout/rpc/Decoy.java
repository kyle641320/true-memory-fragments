package heldout.rpc;
@interface FeignClient { String name(); }
@interface GetMapping { String value(); }
@FeignClient(name="decoy") interface Decoy { @GetMapping("/x") String x(); }
