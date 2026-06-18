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
