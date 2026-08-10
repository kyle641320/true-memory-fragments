from __future__ import annotations

import hashlib
from datetime import datetime, timezone


def now_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def stable_file_claim_id(path: str) -> str:
    digest = hashlib.sha256(path.encode("utf-8")).hexdigest()[:16]
    return f"claim_file_{digest}"


def stable_function_claim_id(path: str, qualname: str) -> str:
    digest = hashlib.sha256(f"{path}\0{qualname}".encode("utf-8")).hexdigest()[:16]
    return f"claim_fn_{digest}"


def stable_class_claim_id(path: str, qualname: str) -> str:
    digest = hashlib.sha256(f"class\0{path}\0{qualname}".encode("utf-8")).hexdigest()[:16]
    return f"claim_class_{digest}"


def stable_declaration_claim_id(path: str, qualname: str) -> str:
    digest = hashlib.sha256(f"declaration\0{path}\0{qualname}".encode("utf-8")).hexdigest()[:16]
    return f"claim_decl_{digest}"


def stable_config_claim_id(path: str, key: str) -> str:
    digest = hashlib.sha256(f"config\0{path}\0{key}".encode("utf-8")).hexdigest()[:16]
    return f"claim_config_{digest}"


def stable_api_claim_id(path: str, method: str, route_path: str, handler_qualname: str) -> str:
    digest = hashlib.sha256(f"api\0{path}\0{method.upper()}\0{route_path}\0{handler_qualname}".encode("utf-8")).hexdigest()[:16]
    return f"claim_api_{digest}"


def stable_api_relationship_claim_id(route_path_source: str, method: str, route_path: str, handler_node_id: str) -> str:
    """v2 identity: route declaration + resolved handler identity.

    This intentionally uses a new namespace.  Legacy claim_api_* IDs retain
    their historical path/verb/URI/qualname meaning and are not reinterpreted.
    """
    digest = hashlib.sha256(
        f"api_relationship_v2\0{route_path_source}\0{method.upper()}\0{route_path}\0{handler_node_id}".encode("utf-8")
    ).hexdigest()[:16]
    return f"claim_api_rel_{digest}"


def stable_java_node_claim_id(path: str, qualname: str, node_kind: str, identity_key: str | None = None) -> str:
    identity = identity_key or qualname
    digest = hashlib.sha256(f"java\0{node_kind}\0{path}\0{identity}".encode("utf-8")).hexdigest()[:16]
    return f"claim_java_{digest}"


def stable_call_edge_claim_id(caller_id: str, callee_id: str) -> str:
    digest = hashlib.sha256(f"{caller_id}\0{callee_id}".encode("utf-8")).hexdigest()[:16]
    return f"claim_edge_{digest}"


def stable_read_edge_claim_id(reader_id: str, declaration_id: str) -> str:
    digest = hashlib.sha256(f"reads\0{reader_id}\0{declaration_id}".encode("utf-8")).hexdigest()[:16]
    return f"claim_read_edge_{digest}"


def stable_write_edge_claim_id(writer_id: str, declaration_id: str) -> str:
    digest = hashlib.sha256(f"writes\0{writer_id}\0{declaration_id}".encode("utf-8")).hexdigest()[:16]
    return f"claim_write_edge_{digest}"


def stable_inherit_edge_claim_id(child_id: str, parent_id: str, relation: str) -> str:
    digest = hashlib.sha256(f"inherits\0{relation}\0{child_id}\0{parent_id}".encode("utf-8")).hexdigest()[:16]
    return f"claim_inherit_edge_{digest}"


def stable_contract_claim_id(path: str, qualname: str) -> str:
    digest = hashlib.sha256(f"contract\0{path}\0{qualname}".encode("utf-8")).hexdigest()[:16]
    return f"claim_contract_{digest}"


def stable_override_edge_claim_id(method_id: str, overridden_id: str) -> str:
    digest = hashlib.sha256(f"overrides\0{method_id}\0{overridden_id}".encode("utf-8")).hexdigest()[:16]
    return f"claim_override_edge_{digest}"


def stable_type_use_edge_claim_id(user_id: str, type_id: str, use_kind: str) -> str:
    digest = hashlib.sha256(f"uses_type\0{use_kind}\0{user_id}\0{type_id}".encode("utf-8")).hexdigest()[:16]
    return f"claim_type_use_edge_{digest}"


def stable_env_claim_id(env_name: str) -> str:
    digest = hashlib.sha256(f"env\0{env_name}".encode("utf-8")).hexdigest()[:16]
    return f"claim_env_{digest}"


def stable_env_read_edge_claim_id(reader_id: str, env_name: str) -> str:
    digest = hashlib.sha256(f"reads_env\0{reader_id}\0{env_name}".encode("utf-8")).hexdigest()[:16]
    return f"claim_env_read_edge_{digest}"


def stable_config_read_edge_claim_id(reader_id: str, config_id: str) -> str:
    digest = hashlib.sha256(f"reads_config_key\0{reader_id}\0{config_id}".encode("utf-8")).hexdigest()[:16]
    return f"claim_config_read_edge_{digest}"


def stable_inject_edge_claim_id(injector_id: str, bean_id: str, inject_kind: str) -> str:
    digest = hashlib.sha256(f"injects\0{inject_kind}\0{injector_id}\0{bean_id}".encode("utf-8")).hexdigest()[:16]
    return f"claim_inject_edge_{digest}"


def stable_configuration_properties_edge_claim_id(source_id: str, prefix: str) -> str:
    digest = hashlib.sha256(f"configuration_properties\0{source_id}\0{prefix}".encode("utf-8")).hexdigest()[:16]
    return f"claim_configuration_properties_edge_{digest}"


def stable_topic_claim_id(topic_name: str) -> str:
    digest = hashlib.sha256(f"topic\0{topic_name}".encode("utf-8")).hexdigest()[:16]
    return f"claim_topic_{digest}"


def stable_topic_pub_edge_claim_id(publisher_id: str, topic_name: str) -> str:
    digest = hashlib.sha256(f"publishes_to\0{publisher_id}\0{topic_name}".encode("utf-8")).hexdigest()[:16]
    return f"claim_topic_pub_edge_{digest}"


def stable_topic_sub_edge_claim_id(subscriber_id: str, topic_name: str) -> str:
    digest = hashlib.sha256(f"subscribes_to\0{subscriber_id}\0{topic_name}".encode("utf-8")).hexdigest()[:16]
    return f"claim_topic_sub_edge_{digest}"


def stable_cache_declaration_claim_id(method_id: str, operation: str, cache_names: tuple[str, ...]) -> str:
    digest = hashlib.sha256(f"cache_declaration\0{method_id}\0{operation}\0{'|'.join(cache_names)}".encode("utf-8")).hexdigest()[:16]
    return f"claim_cache_decl_{digest}"


def stable_scheduling_declaration_claim_id(method_id: str) -> str:
    digest = hashlib.sha256(f"scheduling_declaration\0{method_id}".encode("utf-8")).hexdigest()[:16]
    return f"claim_scheduling_decl_{digest}"


def stable_transaction_declaration_claim_id(owner_id: str) -> str:
    digest = hashlib.sha256(f"transaction_declaration\0{owner_id}".encode("utf-8")).hexdigest()[:16]
    return f"claim_transaction_decl_{digest}"

def stable_async_declaration_claim_id(owner_id: str) -> str:
    digest = hashlib.sha256(f"async_declaration\0{owner_id}".encode("utf-8")).hexdigest()[:16]
    return f"claim_async_decl_{digest}"

def stable_retry_declaration_claim_id(owner_id: str, annotation_kind: str) -> str:
    digest = hashlib.sha256(f"retry_declaration\0{owner_id}\0{annotation_kind}".encode("utf-8")).hexdigest()[:16]
    return f"claim_retry_decl_{digest}"

def stable_circuit_breaker_declaration_claim_id(owner_id: str) -> str:
    digest = hashlib.sha256(f"circuit_breaker_declaration\0{owner_id}".encode("utf-8")).hexdigest()[:16]
    return f"claim_circuit_breaker_decl_{digest}"


def stable_rate_limiter_declaration_claim_id(owner_id: str) -> str:
    digest = hashlib.sha256(f"rate_limiter_declaration\0{owner_id}".encode("utf-8")).hexdigest()[:16]
    return f"claim_rate_limiter_decl_{digest}"


def stable_bulkhead_declaration_claim_id(owner_id: str) -> str:
    digest = hashlib.sha256(f"bulkhead_declaration\0{owner_id}".encode("utf-8")).hexdigest()[:16]
    return f"claim_bulkhead_decl_{digest}"


def stable_time_limiter_declaration_claim_id(owner_id: str) -> str:
    digest = hashlib.sha256(f"time_limiter_declaration\0{owner_id}".encode("utf-8")).hexdigest()[:16]
    return f"claim_time_limiter_decl_{digest}"


def stable_resilience4j_retry_declaration_claim_id(owner_id: str) -> str:
    digest = hashlib.sha256(f"resilience4j_retry_declaration\0{owner_id}".encode("utf-8")).hexdigest()[:16]
    return f"claim_resilience4j_retry_decl_{digest}"


def stable_pre_authorize_declaration_claim_id(owner_id: str) -> str:
    digest=hashlib.sha256(f"pre_authorize_declaration\0{owner_id}".encode()).hexdigest()[:16]
    return f"claim_pre_authorize_decl_{digest}"

def stable_roles_allowed_declaration_claim_id(owner_id: str) -> str:
    digest=hashlib.sha256(f"roles_allowed_declaration\0{owner_id}".encode()).hexdigest()[:16]
    return f"claim_roles_allowed_decl_{digest}"

def stable_secured_declaration_claim_id(owner_id: str) -> str:
    digest=hashlib.sha256(f"secured_declaration\0{owner_id}".encode()).hexdigest()[:16]
    return f"claim_secured_decl_{digest}"


def stable_post_authorize_declaration_claim_id(owner_id: str) -> str:
    digest=hashlib.sha256(f"post_authorize_declaration\0{owner_id}".encode()).hexdigest()[:16]
    return f"claim_post_authorize_decl_{digest}"

def stable_exception_handler_declaration_claim_id(owner_id: str) -> str:
    digest=hashlib.sha256(f"exception_handler_declaration\0{owner_id}".encode()).hexdigest()[:16]
    return f"claim_exception_handler_decl_{digest}"


def stable_pre_filter_declaration_claim_id(owner_id: str) -> str:
    digest=hashlib.sha256(f"pre_filter_declaration\0{owner_id}".encode()).hexdigest()[:16]
    return f"claim_pre_filter_decl_{digest}"


def stable_post_filter_declaration_claim_id(owner_id: str) -> str:
    digest=hashlib.sha256(f"post_filter_declaration\0{owner_id}".encode()).hexdigest()[:16]
    return f"claim_post_filter_decl_{digest}"
