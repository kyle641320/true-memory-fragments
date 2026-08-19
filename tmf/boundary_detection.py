"""
Boundary detection for Java/enterprise code navigation.

A boundary is a node that should stop forward traversal in call/read/write traces,
but still be reported as a reached boundary point.

For Java/Spring/enterprise code:
- Methods that publish to Kafka/message queues are boundaries
- Methods that directly write to persistence (JPA, MyBatis) are boundaries
- Plain internal helper methods are NOT boundaries

This module provides predicate functions that check indexed edge metadata,
not scope, to determine boundaries. Declaration annotations like @Transactional
are not currently indexed as reverse edges, so they cannot be used for boundary
detection without a full claim scan (too expensive for real-time queries).
"""

from .store import Store


def is_boundary_by_writes(store: Store, node_id: str) -> bool:
    """
    Check if a node is a boundary because it directly writes to persistence.
    
    A node with outgoing 'writes' edges to JPA/MyBatis/database declarations
    is a persistence boundary.
    """
    edge_ids = store.index.edge_ids(node_id, relation_kinds={"writes"}, limit=50) or []
    
    for edge_id in edge_ids:
        edge = store.get_claim(edge_id)
        if edge is None:
            continue
        if edge.body.get("edge_kind") == "writes":
            return True
    
    return False


def is_boundary_by_publishes(store: Store, node_id: str) -> bool:
    """
    Check if a node is a boundary because it publishes to a message queue/topic.
    
    A node with outgoing 'publishes_to' edges is an async boundary.
    """
    edge_ids = store.index.edge_ids(node_id, relation_kinds={"publishes_to"}, limit=10) or []
    
    for edge_id in edge_ids:
        edge = store.get_claim(edge_id)
        if edge is None:
            continue
        if edge.body.get("edge_kind") == "publishes_to":
            return True
    
    return False


def is_semantic_boundary(
    store: Store,
    node_id: str,
    check_writes: bool = True,
    check_publishes: bool = True,
) -> bool:
    """
    Combined semantic boundary check.
    
    Returns True if the node is a boundary by any of the enabled criteria.
    Currently checks only indexed edges (writes, publishes_to).
    Declaration annotations like @Transactional are not indexed as reverse edges
    and cannot be efficiently queried.
    """
    if check_writes and is_boundary_by_writes(store, node_id):
        return True
    if check_publishes and is_boundary_by_publishes(store, node_id):
        return True
    
    return False
