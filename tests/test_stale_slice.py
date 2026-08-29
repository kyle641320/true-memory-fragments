from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from tmf.freshness import check_freshness
from tmf.git import GitRepo
from tmf.ids import stable_java_node_claim_id
from tmf.retrieve import refresh_path
from tmf.stale_slice import binding_freshness_report, plan_stale_slice
from tmf.store import Store


JAVA = """class PaymentIntent {}
class Order {
    void markReady() {}
    void markAwaitingReview() {}
}
class OrderService {
    PaymentIntent createIntent() {
        return new PaymentIntent();
    }
    void createOrder() {
        createIntent();
        publish();
    }
    void publish() {}
}
"""


def _init_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-b", "master"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(["git", "config", "user.email", "tmf@example.com"], cwd=root, check=True)
    subprocess.run(["git", "config", "user.name", "tmf"], cwd=root, check=True)
    (root / "OrderService.java").write_text(JAVA, encoding="utf-8")
    subprocess.run(["git", "add", "OrderService.java"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    subprocess.run(["git", "commit", "-m", "fixture"], cwd=root, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


class StaleSliceTests(unittest.TestCase):
    def test_binding_report_and_plan_refresh_only_stale_node(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            _init_repo(repo)
            refresh_path(repo, "OrderService.java")
            store = Store(repo)
            create_order_id = stable_java_node_claim_id("OrderService.java", "OrderService.createOrder", "method")
            create_intent_id = stable_java_node_claim_id("OrderService.java", "OrderService.createIntent", "method")
            create_order = store.get_claim(create_order_id)
            create_intent = store.get_claim(create_intent_id)
            self.assertIsNotNone(create_order)
            self.assertIsNotNone(create_intent)

            (repo / "OrderService.java").write_text(JAVA.replace("publish();", "publish();\n        audit();").replace("    void publish() {}", "    void publish() {}\n    void audit() {}"), encoding="utf-8")
            git = GitRepo(repo)
            self.assertFalse(check_freshness(git, create_order).fresh)
            self.assertTrue(check_freshness(git, create_intent).fresh, check_freshness(git, create_intent).stale_bindings)

            report = binding_freshness_report(git, create_order)
            self.assertEqual(["stale"], [item["status"] for item in report])
            self.assertIn("java_hash mismatch", report[0]["reason"])

            plan = plan_stale_slice(repo, create_order, question="payment intent review order created")
            self.assertEqual("task_relevant_stale_slice", plan["mode"])
            self.assertTrue(plan["stale_claim_withheld"])
            self.assertIn("OrderService.createOrder", [item["qualname"] for item in plan["required_reads"]])
            self.assertIn("not by rebuilding the whole graph", plan["principle"])
            self.assertIn("whole repository", plan["do_not_expand_to"])

    def test_plan_supplements_new_task_relevant_symbols_in_stale_file(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            _init_repo(repo)
            refresh_path(repo, "OrderService.java")
            store = Store(repo)
            create_order_id = stable_java_node_claim_id("OrderService.java", "OrderService.createOrder", "method")
            create_order = store.get_claim(create_order_id)
            self.assertIsNotNone(create_order)

            mutated = JAVA.replace("publish();", "publish();\n        // review path added here")
            (repo / "OrderService.java").write_text(mutated, encoding="utf-8")
            plan = plan_stale_slice(repo, create_order, question="pending review orders must await review before created event", max_required_reads=4)
            qualnames = [item["qualname"] for item in plan["required_reads"]]
            self.assertIn("OrderService.createOrder", qualnames)
            self.assertIn("Order.markAwaitingReview", qualnames)

    def test_plan_adds_structured_event_publish_side_effect_check(self):
        with tempfile.TemporaryDirectory() as td:
            repo = Path(td)
            _init_repo(repo)
            refresh_path(repo, "OrderService.java")
            store = Store(repo)
            create_order_id = stable_java_node_claim_id("OrderService.java", "OrderService.createOrder", "method")
            create_order = store.get_claim(create_order_id)
            self.assertIsNotNone(create_order)

            (repo / "OrderService.java").write_text(JAVA.replace("publish();", "publish();\n        audit();").replace("    void publish() {}", "    void publish() {}\n    void audit() {}"), encoding="utf-8")
            plan = plan_stale_slice(repo, create_order, question="pending review orders must not publish created event", max_required_reads=4)
            checks = plan["side_effect_checks"]
            publish_checks = [c for c in checks if c["kind"] == "event_publish"]
            self.assertTrue(publish_checks)
            self.assertTrue(any(c["must_resolve_before_edit"] for c in publish_checks))
            self.assertIn("pending/review/not-confirmed", publish_checks[0]["guard_hint"])


if __name__ == "__main__":
    unittest.main()
