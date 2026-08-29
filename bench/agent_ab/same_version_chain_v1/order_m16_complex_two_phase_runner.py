#!/usr/bin/env python3
from __future__ import annotations

import argparse, difflib, json, re, shutil, subprocess, sys, textwrap, time
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(ROOT))

from bench.agent_ab.adapter import JsonBrokerAdapter  # noqa:E402
from bench.agent_ab.same_version_chain_v1 import runner as base_runner  # noqa:E402
from tmf.freshness import check_freshness  # noqa:E402
from tmf.git import GitRepo  # noqa:E402
from tmf.stale_slice import plan_stale_slice, stale_slice_prompt  # noqa:E402
from tmf.ids import now_utc  # noqa:E402
from tmf.java_extract import extract_java_methods  # noqa:E402
from tmf.schema import Binding, Claim  # noqa:E402

MODEL = base_runner.MODEL
BROKER = base_runner.BROKER
TIMEOUT = base_runner.TIMEOUT

TAG = "order_m16_complex_two_phase_payment_review"
ARMS = ["SOURCE_ONLY", "PREREAD_STALE_SOURCE", "STALE_DOC_CONTROL", "TMF_REFRESHED_MAP"]

SERVICE = "src/main/java/com/example/order/OrderService.java"
INVENTORY = "src/main/java/com/example/order/InventoryReservationService.java"
PAYMENT = "src/main/java/com/example/order/PaymentIntentService.java"
PUBLISHER = "src/main/java/com/example/order/OrderEventPublisher.java"
ORDER_REPO = "src/main/java/com/example/order/OrderRepository.java"
INVENTORY_REPO = "src/main/java/com/example/order/InventoryReservationRepository.java"
PAYMENT_REPO = "src/main/java/com/example/order/PaymentIntentRepository.java"
ORDER_MODEL = "src/main/java/com/example/order/Order.java"
ORDER_STATUS = "src/main/java/com/example/order/OrderStatus.java"
PAYMENT_MODEL = "src/main/java/com/example/order/PaymentIntent.java"
PAYMENT_STATUS = "src/main/java/com/example/order/PaymentIntentStatus.java"
HIDDEN_TEST = ".m16_hidden/OrderServiceReviewContractTest.java"
VISIBLE_TEST = "src/test/java/com/example/order/OrderServiceReviewContractTest.java"

POM = """<project xmlns="http://maven.apache.org/POM/4.0.0" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xsi:schemaLocation="http://maven.apache.org/POM/4.0.0 https://maven.apache.org/xsd/maven-4.0.0.xsd"><modelVersion>4.0.0</modelVersion><groupId>com.example</groupId><artifactId>order-m16</artifactId><version>1.0-SNAPSHOT</version><properties><maven.compiler.source>17</maven.compiler.source><maven.compiler.target>17</maven.compiler.target><project.build.sourceEncoding>UTF-8</project.build.sourceEncoding></properties><dependencies><dependency><groupId>org.junit.jupiter</groupId><artifactId>junit-jupiter</artifactId><version>5.10.2</version><scope>test</scope></dependency></dependencies><build><plugins><plugin><groupId>org.apache.maven.plugins</groupId><artifactId>maven-surefire-plugin</artifactId><version>3.2.5</version></plugin></plugins></build></project>
"""

TX = """package com.example.order;

import java.lang.annotation.ElementType;
import java.lang.annotation.Retention;
import java.lang.annotation.RetentionPolicy;
import java.lang.annotation.Target;

@Retention(RetentionPolicy.RUNTIME)
@Target({ElementType.METHOD, ElementType.TYPE})
public @interface Transactional {}
"""

OLD_ORDER_STATUS = """package com.example.order;

public enum OrderStatus {
    DRAFT,
    READY
}
"""

POST_ORDER_STATUS = """package com.example.order;

public enum OrderStatus {
    DRAFT,
    READY,
    AWAITING_REVIEW
}
"""

OLD_PAYMENT_STATUS = """package com.example.order;

public enum PaymentIntentStatus {
    CONFIRMED
}
"""

POST_PAYMENT_STATUS = """package com.example.order;

public enum PaymentIntentStatus {
    CONFIRMED,
    PENDING_REVIEW
}
"""

OLD_ORDER = """package com.example.order;

public final class Order {
    private final long id;
    private final String sku;
    private final int quantity;
    private final long customerId;
    private OrderStatus status = OrderStatus.DRAFT;

    public Order(long id, String sku, int quantity, long customerId) {
        this.id = id;
        this.sku = sku;
        this.quantity = quantity;
        this.customerId = customerId;
    }

    public long getId() { return id; }
    public String getSku() { return sku; }
    public int getQuantity() { return quantity; }
    public long getCustomerId() { return customerId; }
    public OrderStatus getStatus() { return status; }
    public void markReady() { this.status = OrderStatus.READY; }
}
"""

POST_ORDER = """package com.example.order;

public final class Order {
    private final long id;
    private final String sku;
    private final int quantity;
    private final long customerId;
    private OrderStatus status = OrderStatus.DRAFT;

    public Order(long id, String sku, int quantity, long customerId) {
        this.id = id;
        this.sku = sku;
        this.quantity = quantity;
        this.customerId = customerId;
    }

    public long getId() { return id; }
    public String getSku() { return sku; }
    public int getQuantity() { return quantity; }
    public long getCustomerId() { return customerId; }
    public OrderStatus getStatus() { return status; }
    public void markReady() { this.status = OrderStatus.READY; }
    public void markAwaitingReview() { this.status = OrderStatus.AWAITING_REVIEW; }
}
"""

PAYMENT_INTENT = """package com.example.order;

public final class PaymentIntent {
    private final long orderId;
    private final PaymentIntentStatus status;

    public PaymentIntent(long orderId, PaymentIntentStatus status) {
        this.orderId = orderId;
        this.status = status;
    }

    public long getOrderId() { return orderId; }
    public PaymentIntentStatus getStatus() { return status; }
}
"""

ORDER_REPOSITORY = """package com.example.order;

public interface OrderRepository {
    void save(Order order);
}
"""

INVENTORY_REPOSITORY = """package com.example.order;

public interface InventoryReservationRepository {
    void reserve(String sku, int quantity);
}
"""

PAYMENT_REPOSITORY = """package com.example.order;

public interface PaymentIntentRepository {
    void save(PaymentIntent paymentIntent);
}
"""

INVENTORY_SERVICE = """package com.example.order;

public class InventoryReservationService {
    private final InventoryReservationRepository repository;

    public InventoryReservationService(InventoryReservationRepository repository) {
        this.repository = repository;
    }

    public void reserveFor(Order order) {
        repository.reserve(order.getSku(), order.getQuantity());
    }
}
"""

OLD_PAYMENT_SERVICE = """package com.example.order;

public class PaymentIntentService {
    private final PaymentIntentRepository repository;

    public PaymentIntentService(PaymentIntentRepository repository) {
        this.repository = repository;
    }

    /**
     * Creates the checkout intent. In this contract all created intents are final.
     */
    public PaymentIntent createIntent(Order order) {
        PaymentIntent intent = new PaymentIntent(order.getId(), PaymentIntentStatus.CONFIRMED);
        repository.save(intent);
        return intent;
    }
}
"""

POST_PAYMENT_SERVICE = """package com.example.order;

public class PaymentIntentService {
    private final PaymentIntentRepository repository;

    public PaymentIntentService(PaymentIntentRepository repository) {
        this.repository = repository;
    }

    /**
     * Creates the checkout intent. Risk review can leave the intent not final yet.
     */
    public PaymentIntent createIntent(Order order) {
        PaymentIntentStatus status = requiresManualReview(order)
                ? PaymentIntentStatus.PENDING_REVIEW
                : PaymentIntentStatus.CONFIRMED;
        PaymentIntent intent = new PaymentIntent(order.getId(), status);
        repository.save(intent);
        return intent;
    }

    private boolean requiresManualReview(Order order) {
        return order.getCustomerId() < 0;
    }
}
"""

EVENT_PUBLISHER = """package com.example.order;

public interface OrderEventPublisher {
    void publish(String eventName, long orderId);
}
"""

OLD_SERVICE = """package com.example.order;

public class OrderService {
    private final OrderRepository orderRepository;
    private final InventoryReservationService inventoryReservationService;
    private final PaymentIntentService paymentIntentService;
    private final OrderEventPublisher eventPublisher;

    public OrderService(OrderRepository orderRepository,
                        InventoryReservationService inventoryReservationService,
                        PaymentIntentService paymentIntentService,
                        OrderEventPublisher eventPublisher) {
        this.orderRepository = orderRepository;
        this.inventoryReservationService = inventoryReservationService;
        this.paymentIntentService = paymentIntentService;
        this.eventPublisher = eventPublisher;
    }

    @Transactional
    public Order createOrder(Order order) {
        inventoryReservationService.reserveFor(order);
        paymentIntentService.createIntent(order);
        order.markReady();
        orderRepository.save(order);
        eventPublisher.publish("ORDER_CREATED", order.getId());
        return order;
    }
}
"""

POST_SERVICE = OLD_SERVICE

HIDDEN_JUNIT = """package com.example.order;

import static org.junit.jupiter.api.Assertions.*;

import java.util.ArrayList;
import java.util.List;
import org.junit.jupiter.api.Test;

class OrderServiceReviewContractTest {
    @Test
    void confirmedIntentKeepsNormalCreationEvent() {
        Fixture f = new Fixture();
        OrderService service = f.service();
        Order order = new Order(100L, "sku-ok", 2, 42L);

        Order result = service.createOrder(order);

        assertSame(order, result);
        assertEquals(OrderStatus.READY, order.getStatus());
        assertEquals(List.of("sku-ok:2"), f.inventory.reservations);
        assertEquals(List.of(PaymentIntentStatus.CONFIRMED), f.payments.savedStatuses);
        assertEquals(List.of(100L), f.orders.savedIds);
        assertEquals(List.of("ORDER_CREATED:100"), f.events.events);
    }

    @Test
    void pendingReviewDoesNotStartFulfillmentEvent() {
        Fixture f = new Fixture();
        OrderService service = f.service();
        Order order = new Order(200L, "sku-review", 1, -9L);

        service.createOrder(order);

        assertEquals(OrderStatus.AWAITING_REVIEW, order.getStatus(), "review intent should leave order waiting instead of ready");
        assertEquals(List.of("sku-review:1"), f.inventory.reservations);
        assertEquals(List.of(PaymentIntentStatus.PENDING_REVIEW), f.payments.savedStatuses);
        assertEquals(List.of(200L), f.orders.savedIds, "review orders are still persisted");
        assertTrue(f.events.events.isEmpty(), "fulfillment must not start while payment intent remains under review");
    }

    static final class Fixture {
        final FakeOrderRepository orders = new FakeOrderRepository();
        final FakeInventoryRepository inventory = new FakeInventoryRepository();
        final FakePaymentRepository payments = new FakePaymentRepository();
        final FakePublisher events = new FakePublisher();

        OrderService service() {
            return new OrderService(
                    orders,
                    new InventoryReservationService(inventory),
                    new PaymentIntentService(payments),
                    events);
        }
    }

    static final class FakeOrderRepository implements OrderRepository {
        final List<Long> savedIds = new ArrayList<>();
        public void save(Order order) { savedIds.add(order.getId()); }
    }

    static final class FakeInventoryRepository implements InventoryReservationRepository {
        final List<String> reservations = new ArrayList<>();
        public void reserve(String sku, int quantity) { reservations.add(sku + ":" + quantity); }
    }

    static final class FakePaymentRepository implements PaymentIntentRepository {
        final List<PaymentIntentStatus> savedStatuses = new ArrayList<>();
        public void save(PaymentIntent paymentIntent) { savedStatuses.add(paymentIntent.getStatus()); }
    }

    static final class FakePublisher implements OrderEventPublisher {
        final List<String> events = new ArrayList<>();
        public void publish(String eventName, long orderId) { events.add(eventName + ":" + orderId); }
    }
}
"""


def write_file(root: Path, rel: str, text: str) -> None:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


def make_repo(root: Path) -> dict[str, Any]:
    if root.exists():
        shutil.rmtree(root)
    write_file(root, "pom.xml", POM)
    write_file(root, "src/main/java/com/example/order/Transactional.java", TX)
    write_file(root, ORDER_STATUS, OLD_ORDER_STATUS)
    write_file(root, PAYMENT_STATUS, OLD_PAYMENT_STATUS)
    write_file(root, ORDER_MODEL, OLD_ORDER)
    write_file(root, PAYMENT_MODEL, PAYMENT_INTENT)
    write_file(root, ORDER_REPO, ORDER_REPOSITORY)
    write_file(root, INVENTORY_REPO, INVENTORY_REPOSITORY)
    write_file(root, PAYMENT_REPO, PAYMENT_REPOSITORY)
    write_file(root, INVENTORY, INVENTORY_SERVICE)
    write_file(root, PAYMENT, OLD_PAYMENT_SERVICE)
    write_file(root, PUBLISHER, EVENT_PUBLISHER)
    write_file(root, SERVICE, OLD_SERVICE)
    write_file(root, HIDDEN_TEST, HIDDEN_JUNIT)
    (root / ".tmf").mkdir(exist_ok=True)
    return {
        "fixture": "synthetic bounded Maven order creation payment-review chain",
        "phase_a": "PaymentIntentService.createIntent always returns CONFIRMED; createOrder reserves inventory, creates intent, marks READY, saves, and immediately publishes ORDER_CREATED.",
        "phase_b": "PaymentIntentService may return CONFIRMED or PENDING_REVIEW; pending review must persist as AWAITING_REVIEW and suppress ORDER_CREATED.",
        "hidden_tests_visible_to_agent": False,
    }


def mutate_to_phase_b(root: Path) -> None:
    write_file(root, PAYMENT_STATUS, POST_PAYMENT_STATUS)
    write_file(root, ORDER_STATUS, POST_ORDER_STATUS)
    write_file(root, ORDER_MODEL, POST_ORDER)
    write_file(root, PAYMENT, POST_PAYMENT_SERVICE)
    write_file(root, SERVICE, POST_SERVICE)


def mvn(root: Path, args: list[str], timeout: int = 120) -> dict[str, Any]:
    r = subprocess.run(["mvn", "-q", *args], cwd=root, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=timeout)
    return {"ok": r.returncode == 0, "exit": r.returncode, "stdout": r.stdout[-4000:], "stderr": r.stderr[-4000:]}


def mvn_compile(root: Path) -> dict[str, Any]:
    return mvn(root, ["-DskipTests", "compile"], 90)


def mvn_hidden_test(root: Path) -> dict[str, Any]:
    hidden = root / HIDDEN_TEST
    visible = root / VISIBLE_TEST
    old = visible.read_text(encoding="utf-8") if visible.exists() else None
    visible.parent.mkdir(parents=True, exist_ok=True)
    visible.write_text(hidden.read_text(encoding="utf-8"), encoding="utf-8")
    try:
        return mvn(root, ["test"], 120)
    finally:
        if old is None:
            try:
                visible.unlink()
            except FileNotFoundError:
                pass
        else:
            visible.write_text(old, encoding="utf-8")


def safe(root: Path, rel: str) -> Path | None:
    return base_runner.safe(root, rel)


def read_numbered(p: Path, start: int = 1, end: int | None = None) -> str:
    return base_runner.read_numbered(p, start, end)


def find_symbol_range(p: Path, symbol: str):
    return base_runner.find_symbol_range(p, symbol)


def parse_actions(raw: str):
    return base_runner.parse_actions(raw)


def visible_file(p: Path) -> bool:
    parts = set(p.parts)
    return p.is_file() and "target" not in parts and ".m16_hidden" not in parts and p.suffix in {".java", ".xml", ".md"}


def list_files(root: Path) -> list[str]:
    return sorted(str(p.relative_to(root)) for p in root.rglob("*") if visible_file(p))[:400]


def search(root: Path, q: str) -> list[str]:
    q = q.lower()
    hits = []
    for p in sorted(root.rglob("*")):
        if not visible_file(p):
            continue
        for i, l in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            if q and q in l.lower():
                hits.append(f"{p.relative_to(root)}:{i}:{l}")
    return hits[:160]


def apply_edit(root: Path, act: dict[str, Any]) -> dict[str, Any]:
    p = safe(root, str(act.get("path", "")))
    if not p or not visible_file(p):
        return {"error": "invalid path"}
    old = str(act.get("old", ""))
    new = str(act.get("new", ""))
    text = p.read_text(encoding="utf-8")
    if not old:
        return {"error": "empty old"}
    n = text.count(old)
    if n != 1:
        return {"error": f"old text occurrences={n}"}
    p.write_text(text.replace(old, new), encoding="utf-8")
    return {"ok": True, "path": str(p.relative_to(root)), "bytes": len(new.encode())}


def snapshot(root: Path) -> dict[str, str]:
    return {str(p.relative_to(root)): p.read_text(encoding="utf-8", errors="replace") for p in sorted(root.rglob("*.java")) if visible_file(p)}


def diff_files(before: dict[str, str], root: Path) -> dict[str, str]:
    files = set(before) | {str(p.relative_to(root)) for p in root.rglob("*.java") if visible_file(p)}
    out = {}
    for f in sorted(files):
        old = before.get(f, "")
        p = root / f
        new = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
        if old != new:
            out[f] = "\n".join(difflib.unified_diff(old.splitlines(), new.splitlines(), fromfile=f"a/{f}", tofile=f"b/{f}", lineterm=""))
    return out


def build_claim(root: Path, orientation: dict[str, Any] | None) -> Claim:
    src = root / SERVICE
    text = src.read_text(encoding="utf-8")
    method = next(m for m in extract_java_methods(SERVICE, text) if m.qualname.endswith("OrderService.createOrder"))
    blob = subprocess.check_output(["git", "hash-object", str(src)], text=True).strip()
    summ = (orientation or {}).get("summary") or "createOrder reserves inventory, creates a final payment intent, marks order READY, saves, and immediately publishes ORDER_CREATED."
    return Claim(
        id="order_m16:old:OrderService.createOrder",
        claim=(
            "Verified old order creation chain: OrderService.createOrder reserves inventory, "
            "calls PaymentIntentService.createIntent(order), treats the intent as final/confirmed, "
            "marks the order READY, saves it, and immediately publishes ORDER_CREATED. "
            "Phase-A orientation: " + str(summ)
        ),
        kind="structure",
        scope="method",
        bindings=[Binding(path=SERVICE, file_blob=blob, fn_hash=method.class_hash, commit=None, qualname="OrderService.createOrder", role="method", line_start=method.line_start, line_end=method.line_end, hash_kind="java_node_hash")],
        provenance="synthetic Phase-A claim from pre-mutation order-m16 fixture",
        evidence="verified",
        confidence=0.96,
        endorsed_by=None,
        last_verified=now_utc(),
        model="deterministic-bench",
        body={"language": "java", "qualname": "OrderService.createOrder", "task_id": "ORDER_M16", "mutation_expected_stale": True},
    )


def placement(root: Path) -> dict[str, Any]:
    svc = (root / SERVICE).read_text(encoding="utf-8", errors="replace")
    return {
        "branches_on_payment_status": bool(re.search(r"getStatus\s*\(\s*\)|PaymentIntentStatus", svc)),
        "marks_awaiting_review": "markAwaitingReview" in svc,
        "marks_ready": "markReady" in svc,
        "publishes_order_created": "ORDER_CREATED" in svc and "eventPublisher.publish" in svc,
        "conditional_publish_after_status": bool(re.search(r"if\s*\([^)]*(CONFIRMED|getStatus|PENDING_REVIEW)", svc, re.S)),
        "visible_tests_present": (root / VISIBLE_TEST).exists(),
    }


def deterministic_test(root: Path) -> dict[str, Any]:
    test = mvn_hidden_test(root)
    pl = placement(root)
    reasons = []
    if not test.get("ok"):
        reasons.append("hidden JUnit tests failed")
    if not pl["branches_on_payment_status"]:
        reasons.append("OrderService does not branch on payment intent status")
    if not pl["marks_awaiting_review"]:
        reasons.append("OrderService does not mark pending-review orders as awaiting review")
    if pl["visible_tests_present"]:
        reasons.append("hidden tests leaked into visible tree")
    ok = bool(test.get("ok") and pl["branches_on_payment_status"] and pl["marks_awaiting_review"] and not pl["visible_tests_present"])
    return {"ok": ok, "placement": pl, "test": test, "message": "PASS" if ok else "; ".join(reasons)}


def run_phase_a(broker: JsonBrokerAdapter, root: Path, max_turns: int):
    tools = """Available actions (respond with exactly ONE JSON object per turn, no prose):
{"action":"list"}
{"action":"read_range","path":"relative file","start":1,"end":220}
{"action":"read_symbol","path":"relative .java file","symbol":"symbol name"}
{"action":"search","query":"text"}
{"action":"compile"}
{"action":"orientation","summary":"brief source-derived understanding of order creation chain"}
"""
    system = f"""You are orienting on a small Java service before implementation work.
Fixture root: {root}
Task: Take a quick look at the order creation workflow and understand what happens after an order is submitted. Do not edit yet.
Edits and finals are not allowed in this phase. Read enough source to form a concrete orientation, then return the orientation action.
{tools}
Begin now."""
    hist, transcript = [], []
    met = {"tool_calls": 0, "source_reads": 0, "source_bytes": 0, "source_files": [], "prompt_tokens": 0, "completion_tokens": 0, "invalid": 0, "edits_rejected": 0, "compile_calls": 0}
    orientation = None
    for turn in range(max_turns):
        prompt = system + "\n" + ("\n".join(hist[-12:]) if hist else "")
        met["prompt_tokens"] += base_runner.tok(prompt)
        raw = broker.answer(prompt, budget=1)["answer"]
        met["completion_tokens"] += base_runner.tok(raw)
        acts = parse_actions(raw)
        transcript.append({"turn": turn, "raw": raw, "actions": acts})
        if not acts:
            met["invalid"] += 1
            hist += ["AGENT:" + raw, "SYSTEM: respond with exactly one JSON action, no prose."]
            continue
        act = acts[0]
        a = act.get("action")
        met["tool_calls"] += 1
        if a == "list":
            out = {"files": list_files(root)}
        elif a == "search":
            out = {"hits": search(root, str(act.get("query", "")))}
        elif a == "read_range":
            p = safe(root, str(act.get("path", "")))
            if not p or not visible_file(p):
                out = {"error": "invalid path"}
            else:
                st = max(1, int(act.get("start", 1)))
                en = int(act.get("end", st + 120))
                content = read_numbered(p, st, en)
                met["source_reads"] += 1
                met["source_bytes"] += len(content.encode())
                met["source_files"].append(str(p.relative_to(root)))
                out = {"path": str(p.relative_to(root)), "content": content}
        elif a == "read_symbol":
            p = safe(root, str(act.get("path", "")))
            sym = str(act.get("symbol", ""))
            if not p or not visible_file(p):
                out = {"error": "invalid path"}
            else:
                rng = find_symbol_range(p, sym)
                if not rng:
                    out = {"error": "symbol not found"}
                else:
                    content = read_numbered(p, rng[0], rng[1])
                    met["source_reads"] += 1
                    met["source_bytes"] += len(content.encode())
                    met["source_files"].append(str(p.relative_to(root)))
                    out = {"path": str(p.relative_to(root)), "symbol": sym, "content": content}
        elif a == "compile":
            met["compile_calls"] += 1
            out = mvn_compile(root)
        elif a == "orientation":
            if met["source_reads"] < 1:
                out = {"error": "orientation rejected: read source first"}
            else:
                orientation = act
                out = {"ok": True}
                transcript[-1]["tool_outputs"] = [{"action": act, "tool_output": out}]
                break
        elif a in {"edit", "final"}:
            met["edits_rejected"] += 1
            out = {"error": f"{a} rejected: Phase A is read-only"}
        else:
            out = {"error": "unknown action"}
        transcript[-1]["tool_outputs"] = [{"action": act, "tool_output": out}]
        hist += ["AGENT:" + raw, "TOOL:" + json.dumps([{"action": act, "tool_output": out}], ensure_ascii=False)[:12000]]
    met["source_files"] = sorted(set(met["source_files"]))
    return orientation, met, transcript


def injection(arm: str, phase_a: list[dict[str, Any]], claim: Claim, fresh: Any, root: Path) -> str:
    if arm == "PREREAD_STALE_SOURCE":
        compact = [{"turn": t.get("turn"), "action": (t.get("actions") or [{}])[0], "tool_outputs": t.get("tool_outputs")} for t in phase_a]
        return "\nEarlier in this same task you already oriented on the source. Continue with that remembered Phase-A context; do not assume a full restart. Your Phase-A transcript was:\n```json\n" + json.dumps(compact, ensure_ascii=False, indent=2)[:9000] + "\n```\n"
    if arm == "STALE_DOC_CONTROL":
        return "\nMaintenance note from the order creation handbook (not freshness-bound): order creation reserves inventory, creates the payment intent, marks the order READY, saves it, and immediately publishes ORDER_CREATED. This is intentionally direct because payment intents created by this workflow are final, so fulfillment listeners should see ORDER_CREATED in the same creation chain. Preserve that immediate event path when adjusting the chain.\n"
    if arm == "TMF_REFRESHED_MAP":
        if fresh.fresh:
            return "\nFresh TMF claim injected below:\n" + json.dumps(claim.to_dict(), ensure_ascii=False, indent=2)
        plan = plan_stale_slice(
            root,
            claim,
            question="线上有些订单在支付意图还在复核时就开始走履约了。帮我把创建链路修一下，别弄坏正常订单。",
            max_required_reads=3,
            max_optional_neighbors=4,
        )
        return (
            "\n" + stale_slice_prompt(plan)
            + "\nMachine-readable TMF stale-slice plan:\n"
            + json.dumps(plan, ensure_ascii=False, indent=2)[:6000]
            + "\n"
        )
    return ""


def run_phase_b(broker: JsonBrokerAdapter, arm: str, root: Path, phase_a: list[dict[str, Any]], claim: Claim, fresh: Any, final_gate: str, max_turns: int):
    task = "线上有些订单在支付意图还在复核时就开始走履约了。帮我把创建链路修一下，别弄坏正常订单。"
    tools = """Available actions (respond with exactly ONE JSON object per turn, no prose, no arrays, no multiple JSON objects):
{"action":"list"}
{"action":"read_range","path":"relative file","start":1,"end":220}
{"action":"read_symbol","path":"relative .java file","symbol":"symbol name"}
{"action":"search","query":"text"}
{"action":"edit","path":"relative file","old":"exact text copied from latest read output","new":"replacement text"}
{"action":"compile"}
{"action":"final","answer":"what changed","files":["relative files"]}
"""
    system = f"""You are a stateless Java coding agent in order_m16_complex_two_phase_payment_review.
Arm: {arm}
Fixture root: {root}
Task from user: {task}
Make the smallest compiling change that satisfies the current project contracts.
When editing, copy exact old text from latest read output. If an edit fails, re-read current source and retry with exact text.
Final gate mode: {final_gate}
Respond with exactly one JSON action per turn. You must perform at least one successful edit before final. Run compile before final. Compile action runs compile only, not tests. After compile succeeds, next turn send final.
{tools}
{injection(arm, phase_a, claim, fresh, root)}
Begin now."""
    hist, transcript = [], []
    met = {"tool_calls": 0, "source_bytes": 0, "source_reads": 0, "source_files": [], "prompt_tokens": 0, "completion_tokens": 0, "invalid": 0, "wall_seconds": 0.0, "successful_edits": 0, "successful_compile": False, "rejected_finals": 0, "post_edit_rejected_non_compile": 0, "post_compile_rejected_non_final": 0, "extra_actions_ignored": 0, "compile_calls": 0}
    final = None
    start = time.time()
    for turn in range(max_turns):
        prompt = system + "\n" + ("\n".join(hist[-18:]) if hist else "")
        met["prompt_tokens"] += base_runner.tok(prompt)
        raw = broker.answer(prompt, budget=1)["answer"]
        met["completion_tokens"] += base_runner.tok(raw)
        acts = parse_actions(raw)
        transcript.append({"turn": turn, "raw": raw, "actions": acts})
        if len(acts) == 1 and acts[0].get("action") is None and any(k in acts[0] for k in ("files", "answer", "message")):
            acts = [{"action": "final", **acts[0]}]
        if not acts:
            met["invalid"] += 1
            hist += ["AGENT:" + raw, "SYSTEM: respond with exactly one JSON action, no prose."]
            continue
        if len(acts) > 1:
            met["extra_actions_ignored"] += len(acts) - 1
            acts = acts[:1]
        act = acts[0]
        a = act.get("action")
        met["tool_calls"] += 1
        if met["successful_compile"] and a != "final":
            met["post_compile_rejected_non_final"] += 1
            out = {"error": "compile already succeeded; next action must be final"}
        elif met["successful_edits"] > 0 and not met["successful_compile"] and a not in {"compile", "edit"}:
            met["post_edit_rejected_non_compile"] += 1
            out = {"error": "edit already succeeded; next action must be compile unless another exact edit is required"}
        elif a == "list":
            out = {"files": list_files(root)}
        elif a == "search":
            out = {"hits": search(root, str(act.get("query", "")))}
        elif a == "read_range":
            p = safe(root, str(act.get("path", "")))
            if not p or not visible_file(p):
                out = {"error": "invalid path"}
            else:
                st = max(1, int(act.get("start", 1)))
                en = int(act.get("end", st + 120))
                content = read_numbered(p, st, en)
                met["source_bytes"] += len(content.encode())
                met["source_reads"] += 1
                met["source_files"].append(str(p.relative_to(root)))
                out = {"path": str(p.relative_to(root)), "content": content}
        elif a == "read_symbol":
            p = safe(root, str(act.get("path", "")))
            sym = str(act.get("symbol", ""))
            if not p or not visible_file(p):
                out = {"error": "invalid path"}
            else:
                rng = find_symbol_range(p, sym)
                if not rng:
                    out = {"error": "symbol not found"}
                else:
                    content = read_numbered(p, rng[0], rng[1])
                    met["source_bytes"] += len(content.encode())
                    met["source_reads"] += 1
                    met["source_files"].append(str(p.relative_to(root)))
                    out = {"path": str(p.relative_to(root)), "symbol": sym, "content": content}
        elif a == "edit":
            out = apply_edit(root, act)
            met["successful_edits"] += 1 if out.get("ok") else 0
        elif a == "compile":
            met["compile_calls"] += 1
            out = mvn_compile(root)
            if out.get("ok"):
                met["successful_compile"] = True
        elif a == "final":
            if final_gate == "hard" and met["successful_edits"] < 1:
                out = {"error": "final rejected: no successful edit"}
                met["rejected_finals"] += 1
            else:
                final = act
                transcript[-1]["tool_outputs"] = [{"action": act, "tool_output": {"ok": True}}]
                break
        else:
            out = {"error": "unknown action"}
        transcript[-1]["tool_outputs"] = [{"action": act, "tool_output": out}]
        tool_text = json.dumps([{"action": act, "tool_output": out}], ensure_ascii=False)[:14000]
        if a == "edit" and out.get("ok"):
            tool_text += "\nSYSTEM: edit succeeded. Next turn respond with exactly one compile JSON action and no prose."
        if a == "compile" and out.get("ok"):
            tool_text += "\nSYSTEM: compile succeeded. Next turn respond with exactly one final JSON action and no prose."
        hist += ["AGENT:" + raw, "TOOL:" + tool_text]
    met["wall_seconds"] = round(time.time() - start, 3)
    met["source_files"] = sorted(set(met["source_files"]))
    return final, met, transcript


def audit(diffs: dict[str, str], final: Any, root: Path) -> dict[str, Any]:
    post = deterministic_test(root)
    sem = bool(post["ok"])
    return {
        "valid_answer": bool(final is not None and bool(diffs) and post["test"].get("ok") is True),
        "compile_ok": bool(post["test"].get("ok")),  # legacy name: final hidden JUnit/post-test status
        "hidden_oracle_ok": bool(post["test"].get("ok")),
        "trap_pass": sem,
        "semantic_pass": sem,
        "trap_reason": post["placement"] | {"post_message": post["message"]},
    }


def compile_action_status(raw: dict[str, Any]) -> dict[str, Any]:
    """Classify the agent-visible compile action separately from hidden oracle tests."""
    failures: list[dict[str, Any]] = []
    successes = 0
    calls = 0
    for tr in raw.get("transcript") or []:
        for item in tr.get("tool_outputs") or []:
            act = item.get("action", {})
            out = item.get("tool_output", {})
            if act.get("action") != "compile" or not isinstance(out, dict):
                continue
            calls += 1
            if out.get("ok") is True:
                successes += 1
            elif out.get("ok") is False:
                failures.append({"turn": tr.get("turn"), "exit": out.get("exit"), "stderr_tail": str(out.get("stderr", ""))[-500:]})
    return {"calls": calls, "successes": successes, "ok": successes > 0, "failures": failures}


def classify(raw: dict[str, Any]) -> dict[str, Any]:
    tel = raw.get("telemetry", {})
    post = raw.get("post_test") or {}
    diffs = raw.get("diffs") or {}
    final = raw.get("final")
    compile_action = compile_action_status(raw)
    hidden_ok = bool(post.get("test", {}).get("ok") if isinstance(post.get("test"), dict) else post.get("ok"))
    semantic_ok = bool(post.get("ok"))

    edit_errors: list[dict[str, Any]] = []
    parse_or_invalid_turns = 0
    tool_errors: list[dict[str, Any]] = []
    for tr in raw.get("transcript") or []:
        if not tr.get("actions"):
            parse_or_invalid_turns += 1
        for item in tr.get("tool_outputs") or []:
            act = item.get("action", {})
            out = item.get("tool_output", {})
            if not isinstance(out, dict) or not out.get("error"):
                continue
            err = {"turn": tr.get("turn"), "action": act.get("action"), "error": out.get("error")}
            if act.get("action") == "edit":
                edit_errors.append(err)
            else:
                tool_errors.append(err)

    raw_pass = bool(final is not None and diffs and compile_action["ok"] and hidden_ok and semantic_ok)
    categories: list[str] = []
    if raw_pass:
        categories.append("pass")
    else:
        if compile_action["failures"]:
            categories.append("compile_action_fail")
        if final is None and diffs and compile_action["ok"] and hidden_ok:
            categories.append("no_final_after_success")
        if compile_action["ok"] and not hidden_ok:
            categories.append("hidden_oracle_fail")
        if final is not None and not diffs and compile_action["ok"]:
            categories.append("no_effect_false_completion")
        if final is None and "no_final_after_success" not in categories:
            categories.append("no_final")
        if edit_errors:
            categories.append("edit_protocol_fail")
        if parse_or_invalid_turns:
            categories.append("parse_or_invalid_action_noise")
        if tool_errors:
            categories.append("tool_error_noise")
        if tel.get("extra_actions_ignored"):
            categories.append("extra_actions_ignored")
        if not compile_action["calls"]:
            categories.append("no_compile_action")
        if not semantic_ok and hidden_ok:
            categories.append("semantic_boundary_fail")
        if not categories:
            categories.append("uncategorized_fail")

    primary = "pass" if raw_pass else categories[0]
    return {
        "pass": raw_pass,
        "primary": primary,
        "categories": categories,
        "edit_errors": edit_errors,
        "compile_action": compile_action,
        "compile_tool_failures": compile_action["failures"],
        "parse_or_invalid_turns": parse_or_invalid_turns,
        "tool_errors": tool_errors,
        "has_final": final is not None,
        "has_diff": bool(diffs),
        "hidden_oracle_ok": hidden_ok,
        "semantic_ok": semantic_ok,
        "extra_actions_ignored": int(tel.get("extra_actions_ignored", 0)),
        "result_ok_but_raw_failed": bool((not raw_pass) and hidden_ok and semantic_ok and diffs),
    }


def metrics(raw: dict[str, Any]) -> dict[str, Any]:
    post = raw.get("post_test") or {}
    cls = raw.get("failure_classification", {})
    compile_action_ok = bool(cls.get("compile_action", {}).get("ok"))
    hidden_ok = bool(cls.get("hidden_oracle_ok", post.get("ok")))
    semantic_ok = bool(post.get("ok"))
    has_diff = bool(raw.get("diffs"))
    has_final = raw.get("final") is not None
    raw_pass = bool(has_final and has_diff and compile_action_ok and hidden_ok and semantic_ok)
    task_result_pass = bool(compile_action_ok and hidden_ok and semantic_ok and has_diff)
    protocol_clean = bool(has_final and has_diff and compile_action_ok)
    semantic_evaluable = bool((compile_action_ok and has_diff) or hidden_ok)
    semantic_pass = True if task_result_pass else (False if semantic_evaluable else None)
    return {
        "raw_pass": raw_pass,
        "protocol_clean": protocol_clean,
        "semantic_evaluable": semantic_evaluable,
        "semantic_pass": semantic_pass,
        "task_result_pass": task_result_pass,
        "post_test_ok": hidden_ok,
        "compile_action_ok": compile_action_ok,
    }


def run_one(broker: JsonBrokerAdapter, arm: str, rep: int, raw_dir: Path, work_dir: Path, final_gate: str, pa_turns: int, pb_turns: int) -> dict[str, Any]:
    root = work_dir / f"ORDER_M16__{arm}__r{rep}"
    meta = make_repo(root)
    orientation, pa_met, pa_trans = run_phase_a(broker, root, pa_turns)
    claim = build_claim(root, orientation)
    pre_excerpt = (root / SERVICE).read_text(encoding="utf-8")
    mutate_to_phase_b(root)
    fresh = check_freshness(GitRepo(root), claim)
    before = snapshot(root)
    final, met, trans = run_phase_b(broker, arm, root, pa_trans, claim, fresh, final_gate, pb_turns)
    diffs = diff_files(before, root)
    post = deterministic_test(root)
    raw = {
        "task_id": "ORDER_M16",
        "arm": arm,
        "rep": rep,
        "fixture_meta": meta,
        "phase_a_orientation": orientation,
        "phase_a_telemetry": pa_met,
        "phase_a_transcript": pa_trans,
        "phase_a_old_source_excerpt": pre_excerpt,
        "hidden_oracle_visible_to_agent": False,
        "compile_action_runs_tests": False,
        "stale_claim_present": arm in {"PREREAD_STALE_SOURCE", "STALE_DOC_CONTROL", "TMF_REFRESHED_MAP"},
        "stale_claim_fresh": fresh.fresh,
        "stale_claim_withheld": bool(arm == "TMF_REFRESHED_MAP" and not fresh.fresh),
        "withheld_claim_id": claim.id if arm == "TMF_REFRESHED_MAP" and not fresh.fresh else None,
        "freshness": {"fresh": fresh.fresh, "stale_bindings": fresh.stale_bindings},
        "final": final,
        "telemetry": met,
        "post_test": post,
        "diffs": diffs,
        "audit": audit(diffs, final, root),
        "transcript": trans,
        "final_gate": final_gate,
        "phase_a_max_turns": pa_turns,
        "phase_b_max_turns": pb_turns,
    }
    raw["failure_classification"] = classify(raw)
    raw["metrics"] = metrics(raw)
    rp = raw_dir / f"ORDER_M16__{arm}__r{rep}.raw.json"
    rp.write_text(json.dumps(raw, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    keep = ["task_id", "arm", "rep", "final_gate", "phase_a_max_turns", "phase_b_max_turns", "phase_a_orientation", "phase_a_telemetry", "hidden_oracle_visible_to_agent", "compile_action_runs_tests", "stale_claim_present", "stale_claim_fresh", "stale_claim_withheld", "withheld_claim_id", "freshness", "final", "telemetry", "post_test", "audit", "failure_classification", "metrics"]
    return {k: raw[k] for k in keep} | {"raw_path": str(rp.relative_to(HERE)), "diff_bytes": sum(len(d.encode()) for d in diffs.values())}


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    by = {}
    for arm in ARMS:
        rs = [r for r in rows if r["arm"] == arm]
        by[arm] = {
            "runs": len(rs),
            "raw_pass": sum(r["metrics"]["raw_pass"] for r in rs),
            "task_result_pass": sum(r["metrics"]["task_result_pass"] for r in rs),
            "post_test_ok": sum(r["metrics"]["post_test_ok"] for r in rs),
            "semantic_evaluable": sum(r["metrics"]["semantic_evaluable"] for r in rs),
            "semantic_adjusted_pass": sum(1 for r in rs if r["metrics"]["semantic_pass"] is True),
            "stale_claim_withheld": sum(1 for r in rs if r.get("stale_claim_withheld")),
            "marks_awaiting_review": sum(1 for r in rs if r.get("post_test", {}).get("placement", {}).get("marks_awaiting_review")),
            "branches_on_payment_status": sum(1 for r in rs if r.get("post_test", {}).get("placement", {}).get("branches_on_payment_status")),
            "primary": {},
        }
        for r in rs:
            p = r["failure_classification"].get("primary", "unknown")
            by[arm]["primary"][p] = by[arm]["primary"].get(p, 0) + 1
    return {"mode": TAG, "runs": len(rows), "by_arm": by}


def write_report(out: dict[str, Any], path: Path) -> None:
    lines = [
        "# Order M16 Complex Two-Phase Hidden-Oracle Report",
        "",
        "Fixture: synthetic bounded Maven order creation chain. Phase A old behavior is benign: every created payment intent is final, order creation reserves inventory, marks READY, saves, and immediately publishes ORDER_CREATED. Phase B mutates the downstream payment intent contract so some intents remain under review; hidden JUnit tests require those orders to be AWAITING_REVIEW and suppress ORDER_CREATED while preserving normal confirmed orders.",
        "",
        "Protocol notes: the user prompt is vague and does not name files/methods/APIs/status names; hidden oracle tests are not listed/readable by the agent; compile action runs `mvn -q -DskipTests compile` only; final post-test injects and runs hidden JUnit tests.",
        "",
        "```json",
        json.dumps(out["summary"], ensure_ascii=False, indent=2),
        "```",
        "",
        "## Rows",
    ]
    for r in out["rows"]:
        lines.append(f"- rep {r['rep']} {r['arm']}: raw={r['metrics']['raw_pass']} task={r['metrics']['task_result_pass']} semantic={r['metrics']['semantic_pass']} post={r['post_test']['ok']} withheld={r.get('stale_claim_withheld')} failure={r['failure_classification']['primary']} placement={json.dumps(r['post_test']['placement'], ensure_ascii=False)} raw_path={r['raw_path']}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def setup_check() -> dict[str, Any]:
    tmp = HERE / "results" / "work" / "_order_m16_setup_check"
    make_repo(tmp)
    pre = mvn_compile(tmp)
    old_hidden_visible = (tmp / VISIBLE_TEST).exists()
    claim = build_claim(tmp, {"summary": "setup"})
    mutate_to_phase_b(tmp)
    fresh = check_freshness(GitRepo(tmp), claim)
    post_compile = mvn_compile(tmp)
    post_hidden = mvn_hidden_test(tmp)
    out = {
        "pre_compile_ok": pre.get("ok"),
        "hidden_tests_visible_before_posttest": old_hidden_visible,
        "freshness_after_mutation": {"fresh": fresh.fresh, "stale_bindings": fresh.stale_bindings},
        "post_mutation_compile_ok": post_compile.get("ok"),
        "post_baseline_hidden_tests_ok_expected_false": post_hidden.get("ok"),
        "post_placement": placement(tmp),
        "compile_action_runs_tests": False,
    }
    out["ok"] = bool(pre.get("ok") and not old_hidden_visible and fresh.fresh is False and post_compile.get("ok") and post_hidden.get("ok") is False and not placement(tmp)["visible_tests_present"])
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--tag", default=TAG)
    ap.add_argument("--final-gate", choices=["hard"], default="hard")
    ap.add_argument("--phase-a-turns", type=int, default=6)
    ap.add_argument("--phase-b-turns", type=int, default=24)
    ap.add_argument("--setup-check", action="store_true")
    args = ap.parse_args()
    if args.setup_check:
        setup_check()
        return

    results = HERE / "results"
    raw_dir = results / "raw" / args.tag
    work_dir = results / "work" / args.tag
    if raw_dir.exists():
        shutil.rmtree(raw_dir)
    if work_dir.exists():
        shutil.rmtree(work_dir)
    raw_dir.mkdir(parents=True)
    work_dir.mkdir(parents=True)

    broker = JsonBrokerAdapter(BROKER, expected_model=MODEL, timeout_seconds=TIMEOUT)
    preflight = broker.preflight().__dict__
    rows = []
    for rep in range(1, args.repeats + 1):
        for arm in ARMS:
            print(f"RUN rep={rep} arm={arm}", flush=True)
            row = run_one(broker, arm, rep, raw_dir, work_dir, args.final_gate, args.phase_a_turns, args.phase_b_turns)
            rows.append(row)
            print(f"DONE rep={rep} arm={arm} raw={row['metrics']['raw_pass']} task={row['metrics']['task_result_pass']} failure={row['failure_classification']['primary']}", flush=True)
            out = {"schema": TAG, "model": MODEL, "preflight": preflight, "rows": rows, "summary": summarize(rows)}
            (results / f"{args.tag}.json").write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    out = {"schema": TAG, "model": MODEL, "preflight": preflight, "rows": rows, "summary": summarize(rows)}
    jp = results / f"{args.tag}.json"
    rp = results / f"{args.tag.upper()}_REPORT.md"
    jp.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_report(out, rp)
    print("WROTE", jp, rp)
    print(json.dumps(out["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
