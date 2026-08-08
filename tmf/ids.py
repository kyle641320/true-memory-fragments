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


def stable_java_node_claim_id(path: str, qualname: str, node_kind: str) -> str:
    digest = hashlib.sha256(f"java\0{node_kind}\0{path}\0{qualname}".encode("utf-8")).hexdigest()[:16]
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


def stable_topic_claim_id(topic_name: str) -> str:
    digest = hashlib.sha256(f"topic\0{topic_name}".encode("utf-8")).hexdigest()[:16]
    return f"claim_topic_{digest}"


def stable_topic_pub_edge_claim_id(publisher_id: str, topic_name: str) -> str:
    digest = hashlib.sha256(f"publishes_to\0{publisher_id}\0{topic_name}".encode("utf-8")).hexdigest()[:16]
    return f"claim_topic_pub_edge_{digest}"


def stable_topic_sub_edge_claim_id(subscriber_id: str, topic_name: str) -> str:
    digest = hashlib.sha256(f"subscribes_to\0{subscriber_id}\0{topic_name}".encode("utf-8")).hexdigest()[:16]
    return f"claim_topic_sub_edge_{digest}"
