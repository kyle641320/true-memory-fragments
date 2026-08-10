package heldout.rpc;
import org.springframework.cloud.openfeign.FeignClient;
import org.springframework.web.bind.annotation.GetMapping;
@FeignClient(name="inventory", url="https://inventory.invalid", path="/api")
interface InventoryClient {
  @GetMapping("/stock") String stock();
}
