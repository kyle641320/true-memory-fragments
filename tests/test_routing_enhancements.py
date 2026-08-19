"""
Test routing shape, async handoff, polymorphic branches, and understanding tier.
"""
import json
import unittest
from pathlib import Path
from tmf.store import Store
from tmf.git import GitRepo
from tmf.mcp_server import McpService


class RoutingEnhancementsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.repo = Path(__file__).parent.parent
        cls.store = Store(cls.repo)
        cls.git = GitRepo(cls.repo)
        
    def test_routing_shape_single_call(self):
        """Single synchronous call should have routing_shape with single=True"""
        service = McpService(self.repo)
        # Find a function with exactly one outgoing call
        claims = list(self.store.iter_claims())
        call_edges = [c for c in claims if c.body.get("edge_kind") == "calls"]
        
        if not call_edges:
            self.skipTest("No call edges found")
            
        # Group by source to find single-call functions
        by_source = {}
        for edge in call_edges:
            src = edge.body.get("source_id")
            if src:
                by_source.setdefault(src, []).append(edge)
        
        single_call_sources = [src for src, edges in by_source.items() if len(edges) == 1]
        if not single_call_sources:
            self.skipTest("No single-call functions found")
            
        entry = single_call_sources[0]
        fragment = service.tmf_fragment(entry, ["calls"], 1, ["function"], 10, 3)
        
        self.assertIn("routing_shape", fragment)
        shapes = fragment["routing_shape"]
        self.assertGreater(len(shapes), 0)
        
        # First hop should be single
        first_shape = shapes[0]
        self.assertTrue(first_shape.get("single"), f"Expected single=True, got {first_shape}")
        self.assertFalse(first_shape.get("branching"))
        self.assertFalse(first_shape.get("unresolved"))
        
    def test_routing_shape_branching(self):
        """Multiple outgoing calls should have routing_shape with branching=True"""
        service = McpService(self.repo)
        claims = list(self.store.iter_claims())
        call_edges = [c for c in claims if c.body.get("edge_kind") == "calls"]
        
        if not call_edges:
            self.skipTest("No call edges found")
            
        by_source = {}
        for edge in call_edges:
            src = edge.body.get("source_id")
            if src:
                by_source.setdefault(src, []).append(edge)
        
        branching_sources = [src for src, edges in by_source.items() if len(edges) > 1]
        if not branching_sources:
            self.skipTest("No branching functions found")
            
        entry = branching_sources[0]
        fragment = service.tmf_fragment(entry, ["calls"], 1, ["function"], 10, 3)
        
        shapes = fragment.get("routing_shape", [])
        self.assertGreater(len(shapes), 0)
        
        first_shape = shapes[0]
        self.assertTrue(first_shape.get("branching"), f"Expected branching=True, got {first_shape}")
        self.assertFalse(first_shape.get("single"))
        
    def test_async_handoff_pub_sub(self):
        """publishes_to edges should mark async_handoff=True"""
        service = McpService(self.repo)
        claims = list(self.store.iter_claims())
        pub_edges = [c for c in claims if c.body.get("edge_kind") == "publishes_to"]
        
        if not pub_edges:
            self.skipTest("No publishes_to edges found")
            
        pub_edge = pub_edges[0]
        source_id = pub_edge.body.get("source_id")
        
        if not source_id:
            self.skipTest("publishes_to edge has no source_id")
            
        fragment = service.tmf_fragment(source_id, ["publishes_to"], 1, ["function", "method"], 10, 3)
        shapes = fragment.get("routing_shape", [])
        
        if shapes:
            first_shape = shapes[0]
            self.assertTrue(first_shape.get("async_handoff"), 
                          f"Expected async_handoff=True for publishes_to, got {first_shape}")
            
    def test_polymorphic_branch_overrides(self):
        """overrides edges should mark polymorphic=True"""
        service = McpService(self.repo)
        claims = list(self.store.iter_claims())
        override_edges = [c for c in claims if c.body.get("edge_kind") == "overrides"]
        
        if not override_edges:
            self.skipTest("No overrides edges found")
            
        override_edge = override_edges[0]
        source_id = override_edge.body.get("source_id")
        
        if not source_id:
            self.skipTest("overrides edge has no source_id")
            
        # Fragment from a caller of the overridden method
        fragment = service.tmf_fragment(source_id, ["overrides"], 1, ["method"], 10, 3)
        shapes = fragment.get("routing_shape", [])
        
        if shapes:
            first_shape = shapes[0]
            self.assertTrue(first_shape.get("polymorphic"), 
                          f"Expected polymorphic=True for overrides, got {first_shape}")
            
    def test_understanding_tier_in_contract(self):
        """Semantic contracts should have tier=understanding"""
        claims = list(self.store.iter_claims())
        contracts = [c for c in claims if c.scope == "contract" and c.body.get("evidence") == "inferred"]
        
        if not contracts:
            self.skipTest("No inferred contracts found (TMF_MODEL_COMMAND not configured or no semantic contracts)")
            
        for contract in contracts:
            self.assertEqual(contract.body.get("tier"), "understanding",
                           f"Inferred contract {contract.id} should have tier=understanding")
            self.assertIn("verification", contract.body)
            self.assertEqual(contract.body["verification"]["evidence"], "inferred")


if __name__ == "__main__":
    unittest.main()
