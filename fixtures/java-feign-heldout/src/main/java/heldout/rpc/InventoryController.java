package heldout.rpc;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.bind.annotation.GetMapping;
@RestController
class InventoryController {
  @GetMapping("/api/stock") String stock() { return "ok"; }
}
