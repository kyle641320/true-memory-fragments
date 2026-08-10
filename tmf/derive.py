from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from .edges import resolve_call_edges, resolve_read_edges, resolve_write_edges, resolve_env_read_edges, resolve_config_key_read_edges
from .extract import ApiNode, ClassNode, ConfigNode, DeclarationNode, FunctionNode, extract_apis, extract_classes, extract_configs, extract_declarations, extract_functions, extract_sql_declarations, function_interface
from .backends import SemanticExtractorBackend
from .contracts import derive_contract_candidate_with_command, sanitize_contract_candidate
from .java_extract import JAVA_DEGRADE_HINT, extract_java_apis, extract_java_functional_apis, extract_java_feign_apis, extract_java_classes, extract_java_fields, extract_java_methods, java_status, resolve_java_inherit_edges, resolve_java_call_edges, resolve_java_field_edges, resolve_java_override_edges, resolve_java_type_use_edges, resolve_java_inject_edges, resolve_java_topic_edges, resolve_java_saga_definitions, resolve_java_configuration_properties, resolve_java_spring_declarations, resolve_java_persistence_declarations, resolve_java_repository_declarations, resolve_java_mybatis_declarations, resolve_java_cache_declarations, resolve_java_scheduling_declarations, resolve_java_transaction_declarations, resolve_java_async_declarations, resolve_java_retry_declarations, resolve_java_circuit_breaker_declarations, resolve_java_rate_limiter_declarations, resolve_java_bulkhead_declarations, resolve_java_time_limiter_declarations, resolve_java_resilience4j_retry_declarations, resolve_java_pre_authorize_declarations, resolve_java_roles_allowed_declarations, resolve_java_secured_declarations, resolve_java_post_authorize_declarations, resolve_java_exception_handler_declarations, resolve_java_controller_advice_declarations, resolve_java_pre_filter_declarations, resolve_java_post_filter_declarations, java_method_interface, java_node_id
from .llm import DeriverModel
from .model_derive import derive_model_function_claims
from .git import GitRepo
from .ids import now_utc, stable_api_claim_id, stable_api_relationship_claim_id, stable_call_edge_claim_id, stable_class_claim_id, stable_config_claim_id, stable_declaration_claim_id, stable_file_claim_id, stable_function_claim_id, stable_java_node_claim_id, stable_read_edge_claim_id, stable_write_edge_claim_id, stable_inherit_edge_claim_id, stable_override_edge_claim_id, stable_contract_claim_id, stable_type_use_edge_claim_id, stable_env_claim_id, stable_env_read_edge_claim_id, stable_config_read_edge_claim_id, stable_inject_edge_claim_id, stable_configuration_properties_edge_claim_id, stable_topic_claim_id, stable_topic_pub_edge_claim_id, stable_topic_sub_edge_claim_id, stable_cache_declaration_claim_id, stable_scheduling_declaration_claim_id, stable_transaction_declaration_claim_id, stable_async_declaration_claim_id, stable_retry_declaration_claim_id, stable_circuit_breaker_declaration_claim_id, stable_rate_limiter_declaration_claim_id, stable_bulkhead_declaration_claim_id, stable_time_limiter_declaration_claim_id, stable_resilience4j_retry_declaration_claim_id, stable_pre_authorize_declaration_claim_id, stable_roles_allowed_declaration_claim_id, stable_secured_declaration_claim_id, stable_post_authorize_declaration_claim_id, stable_exception_handler_declaration_claim_id, stable_controller_advice_declaration_claim_id, stable_pre_filter_declaration_claim_id, stable_post_filter_declaration_claim_id
from .schema import Binding, Claim
from .verify import verify_observed_claim

MODEL = "tmf-v1-heuristic"


def derive_cache_declaration_claim(repo: GitRepo, item) -> Claim:
    return Claim(id=stable_cache_declaration_claim_id(item.method_id, item.operation, item.cache_names),
        claim=f"Java method {item.method_qualname} declares Spring Cache {item.operation} metadata for {', '.join(item.cache_names)}.",
        kind="structure", scope="declaration",
        bindings=[Binding(path=item.path, file_blob=repo.blob_sha(item.path), fn_hash=item.annotation_hash,
            commit=repo.head(), qualname=item.method_qualname, role="cache_annotation", line_start=item.line_start,
            line_end=item.line_end, hash_kind="java_token_sha256")], provenance="git", evidence="observed",
        confidence=1.0, endorsed_by=None, last_verified=now_utc(), model=MODEL,
        body={"language":"java", "edge_kind":"declares_cache_metadata", "operation":item.operation,
            "cache_names":list(item.cache_names), "key":item.key, "condition":item.condition, "unless":item.unless,
            "spel_handling":"opaque-never-evaluated", "method_id":item.method_id, "method_qualname":item.method_qualname,
            "resolution":item.resolution, "coverage":"partial", "tier":"observed",
            "notes":["Declaration metadata only; no cache hit, storage, serialization, ordering, proxy, transaction, or runtime effect is inferred."]})


def derive_scheduling_declaration_claim(repo: GitRepo, item) -> Claim:
    return Claim(id=stable_scheduling_declaration_claim_id(item.method_id),
        claim=f"Java method {item.method_qualname} declares literal Spring scheduling metadata.", kind="structure", scope="declaration",
        bindings=[Binding(path=item.path, file_blob=repo.blob_sha(item.path), fn_hash=item.annotation_hash, commit=repo.head(), qualname=item.method_qualname, role="scheduled_annotation", line_start=item.line_start, line_end=item.line_end, hash_kind="java_token_sha256")],
        provenance="git", evidence="observed", confidence=1.0, endorsed_by=None, last_verified=now_utc(), model=MODEL,
        body={"language":"java", "edge_kind":"declares_scheduling_metadata", "method_id":item.method_id, "method_qualname":item.method_qualname,
              "fixed_rate":item.fixed_rate, "fixed_delay":item.fixed_delay, "initial_delay":item.initial_delay, "cron":item.cron, "zone":item.zone, "time_unit":item.time_unit,
              "values_handling":"opaque-never-calculated", "resolution":item.resolution, "coverage":"partial", "tier":"observed",
              "notes":["Source declaration only; no schedule calculation, invocation, timezone semantics, concurrency, proxy, EnableScheduling, inheritance, composition, placeholders, SpEL, or runtime execution is inferred."]})


def derive_transaction_declaration_claim(repo: GitRepo, item) -> Claim:
    return Claim(id=stable_transaction_declaration_claim_id(item.owner_id), claim=f"Java {item.owner_kind} {item.owner_qualname} directly declares literal Spring transaction annotation metadata.", kind="structure", scope="declaration",
        bindings=[Binding(path=item.path,file_blob=repo.blob_sha(item.path),fn_hash=item.annotation_hash,commit=repo.head(),qualname=item.owner_qualname,role="transactional_annotation",line_start=item.line_start,line_end=item.line_end,hash_kind="java_token_sha256")],
        provenance="git",evidence="observed",confidence=1.0,endorsed_by=None,last_verified=now_utc(),model=MODEL,
        body={"language":"java","edge_kind":"declares_transaction_metadata","owner_id":item.owner_id,"owner_qualname":item.owner_qualname,"owner_kind":item.owner_kind,"declaration_precedence":"method_over_class_source_metadata" if item.owner_kind=="method" else "class_source_metadata","propagation":item.propagation,"isolation":item.isolation,"read_only":item.read_only,"timeout":item.timeout,"transaction_manager":item.transaction_manager,"rollback_for":list(item.rollback_for),"no_rollback_for":list(item.no_rollback_for),"rollback_for_class_name":list(item.rollback_for_class_name),"no_rollback_for_class_name":list(item.no_rollback_for_class_name),"values_handling":"opaque-never-interpreted","resolution":item.resolution,"coverage":"partial","tier":"observed","notes":["Direct source annotation metadata only; no boundary, database effect, rollback behavior, proxying, propagation execution, manager resolution, call graph, inheritance, composition, or runtime semantics is inferred."]})



def derive_async_declaration_claim(repo: GitRepo, item) -> Claim:
    return Claim(id=stable_async_declaration_claim_id(item.owner_id), claim=f"Java {item.owner_kind} {item.owner_qualname} directly declares Spring Async metadata.", kind="structure", scope="declaration", bindings=[Binding(path=item.path,file_blob=repo.blob_sha(item.path),fn_hash=item.annotation_hash,commit=repo.head(),qualname=item.owner_qualname,role="async_annotation",line_start=item.line_start,line_end=item.line_end,hash_kind="java_token_sha256")], provenance="git",evidence="observed",confidence=1.0,endorsed_by=None,last_verified=now_utc(),model=MODEL, body={"language":"java","edge_kind":"declares_async_metadata","owner_id":item.owner_id,"owner_qualname":item.owner_qualname,"owner_kind":item.owner_kind,"declaration_precedence":"method_over_class_source_metadata" if item.owner_kind=="method" else "class_source_metadata","executor_qualifier":item.executor_qualifier,"values_handling":"opaque-never-resolved","resolution":item.resolution,"coverage":"partial","tier":"observed","notes":["Direct source annotation metadata only; no runtime calls, executor resolution, threads, scheduling, proxy, exception, ordering, EnableAsync, inheritance, composition, or external symbols are inferred."]})


def derive_retry_declaration_claim(repo: GitRepo, item) -> Claim:
    return Claim(id=stable_retry_declaration_claim_id(item.owner_id,item.annotation_kind), claim=f"Java {item.owner_kind} {item.owner_qualname} directly declares Spring Retry {item.annotation_kind} metadata.", kind="structure", scope="declaration", bindings=[Binding(path=item.path,file_blob=repo.blob_sha(item.path),fn_hash=item.annotation_hash,commit=repo.head(),qualname=item.owner_qualname,role=f"{item.annotation_kind}_annotation",line_start=item.line_start,line_end=item.line_end,hash_kind="java_token_sha256")], provenance="git",evidence="observed",confidence=1.0,endorsed_by=None,last_verified=now_utc(),model=MODEL,body={"language":"java","edge_kind":"declares_retry_metadata","owner_id":item.owner_id,"owner_qualname":item.owner_qualname,"owner_kind":item.owner_kind,"annotation_kind":item.annotation_kind,"metadata":{k:list(v) if isinstance(v,tuple) else v for k,v in item.metadata.items()},"values_handling":"opaque-never-interpreted","resolution":item.resolution,"coverage":"partial","tier":"observed","notes":["Direct annotation metadata only; no retries, runtime attempts/backoff, exception matching, recovery dispatch, proxies, calls, inheritance/composition, or external symbols are inferred."]})

def derive_circuit_breaker_declaration_claim(repo: GitRepo, item) -> Claim:
    return Claim(id=stable_circuit_breaker_declaration_claim_id(item.owner_id),claim=f"Java {item.owner_kind} {item.owner_qualname} directly declares Resilience4j CircuitBreaker metadata.",kind="structure",scope="declaration",bindings=[Binding(path=item.path,file_blob=repo.blob_sha(item.path),fn_hash=item.annotation_hash,commit=repo.head(),qualname=item.owner_qualname,role="circuit_breaker_annotation",line_start=item.line_start,line_end=item.line_end,hash_kind="java_token_sha256")],provenance="git",evidence="observed",confidence=1.0,endorsed_by=None,last_verified=now_utc(),model=MODEL,body={"language":"java","edge_kind":"declares_circuit_breaker_metadata","owner_id":item.owner_id,"owner_qualname":item.owner_qualname,"owner_kind":item.owner_kind,"name":item.name,"fallback_method":item.fallback_method,"values_handling":"opaque-never-resolved","resolution":item.resolution,"coverage":"partial","tier":"observed","notes":["Direct declaration metadata only; no circuit state, failure classification, thresholds, fallback dispatch, configuration, proxy/AOP, calls, inheritance/composition, or runtime behavior is inferred."]})

def derive_rate_limiter_declaration_claim(repo: GitRepo, item) -> Claim:
    return Claim(id=stable_rate_limiter_declaration_claim_id(item.owner_id),claim=f"Java {item.owner_kind} {item.owner_qualname} directly declares Resilience4j RateLimiter metadata.",kind="structure",scope="declaration",bindings=[Binding(path=item.path,file_blob=repo.blob_sha(item.path),fn_hash=item.annotation_hash,commit=repo.head(),qualname=item.owner_qualname,role="rate_limiter_annotation",line_start=item.line_start,line_end=item.line_end,hash_kind="java_token_sha256")],provenance="git",evidence="observed",confidence=1.0,endorsed_by=None,last_verified=now_utc(),model=MODEL,body={"language":"java","edge_kind":"declares_rate_limiter_metadata","owner_id":item.owner_id,"owner_qualname":item.owner_qualname,"owner_kind":item.owner_kind,"name":item.name,"fallback_method":item.fallback_method,"values_handling":"opaque-never-resolved","resolution":item.resolution,"coverage":"partial","tier":"observed","notes":["Direct declaration metadata only; no permits, waiting, refresh periods, fallback dispatch, configuration, proxy/AOP, calls, inheritance/composition, or runtime behavior is inferred."]})


def derive_bulkhead_declaration_claim(repo: GitRepo, item) -> Claim:
    return Claim(id=stable_bulkhead_declaration_claim_id(item.owner_id),claim=f"Java {item.owner_kind} {item.owner_qualname} directly declares Resilience4j Bulkhead metadata.",kind="structure",scope="declaration",bindings=[Binding(path=item.path,file_blob=repo.blob_sha(item.path),fn_hash=item.annotation_hash,commit=repo.head(),qualname=item.owner_qualname,role="bulkhead_annotation",line_start=item.line_start,line_end=item.line_end,hash_kind="java_token_sha256")],provenance="git",evidence="observed",confidence=1.0,endorsed_by=None,last_verified=now_utc(),model=MODEL,body={"language":"java","edge_kind":"declares_bulkhead_metadata","owner_id":item.owner_id,"owner_qualname":item.owner_qualname,"owner_kind":item.owner_kind,"name":item.name,"fallback_method":item.fallback_method,"values_handling":"opaque-never-resolved","resolution":item.resolution,"coverage":"partial","tier":"observed","notes":["Direct declaration metadata only; no concurrency limits, queueing, isolation, fallback dispatch, configuration, proxy/AOP, calls, inheritance/composition, or runtime behavior is inferred."]})


def derive_time_limiter_declaration_claim(repo: GitRepo, item) -> Claim:
    return Claim(id=stable_time_limiter_declaration_claim_id(item.owner_id),claim=f"Java {item.owner_kind} {item.owner_qualname} directly declares Resilience4j TimeLimiter metadata.",kind="structure",scope="declaration",bindings=[Binding(path=item.path,file_blob=repo.blob_sha(item.path),fn_hash=item.annotation_hash,commit=repo.head(),qualname=item.owner_qualname,role="time_limiter_annotation",line_start=item.line_start,line_end=item.line_end,hash_kind="java_token_sha256")],provenance="git",evidence="observed",confidence=1.0,endorsed_by=None,last_verified=now_utc(),model=MODEL,body={"language":"java","edge_kind":"declares_time_limiter_metadata","owner_id":item.owner_id,"owner_qualname":item.owner_qualname,"owner_kind":item.owner_kind,"name":item.name,"fallback_method":item.fallback_method,"values_handling":"opaque-never-resolved","resolution":item.resolution,"coverage":"partial","tier":"observed","notes":["Direct declaration metadata only; no timing, cancellation, futures/reactive behavior, fallback dispatch, configuration, proxy/AOP, calls, inheritance/composition, or runtime behavior is inferred."]})


def derive_pre_authorize_declaration_claim(repo,item):
    return Claim(id=stable_pre_authorize_declaration_claim_id(item.owner_id),claim=f"Java {item.owner_kind} {item.owner_qualname} directly declares Spring Security PreAuthorize metadata.",kind="structure",scope="declaration",bindings=[Binding(path=item.path,file_blob=repo.blob_sha(item.path),fn_hash=item.annotation_hash,commit=repo.head(),qualname=item.owner_qualname,role="pre_authorize_annotation",line_start=item.line_start,line_end=item.line_end,hash_kind="java_token_sha256")],provenance="git",evidence="observed",confidence=1.0,endorsed_by=None,last_verified=now_utc(),model=MODEL,body={"language":"java","edge_kind":"declares_pre_authorize_metadata","owner_id":item.owner_id,"owner_qualname":item.owner_qualname,"owner_kind":item.owner_kind,"expression":item.expression,"values_handling":"opaque-never-interpreted","resolution":item.resolution,"coverage":"partial","tier":"observed","notes":["No runtime authorization, expression truth, role hierarchy, proxy/AOP, config, calls, inheritance/composition, or external symbols inferred."]})

def derive_roles_allowed_declaration_claim(repo,item):
    return Claim(id=stable_roles_allowed_declaration_claim_id(item.owner_id),claim=f"Java {item.owner_kind} {item.owner_qualname} directly declares {item.source_namespace} RolesAllowed metadata.",kind="structure",scope="declaration",bindings=[Binding(path=item.path,file_blob=repo.blob_sha(item.path),fn_hash=item.annotation_hash,commit=repo.head(),qualname=item.owner_qualname,role="roles_allowed_annotation",line_start=item.line_start,line_end=item.line_end,hash_kind="java_token_sha256")],provenance="git",evidence="observed",confidence=1.0,endorsed_by=None,last_verified=now_utc(),model=MODEL,body={"language":"java","edge_kind":"declares_roles_allowed_metadata","owner_id":item.owner_id,"owner_qualname":item.owner_qualname,"owner_kind":item.owner_kind,"roles":list(item.roles),"source_namespace":item.source_namespace,"values_handling":"opaque-never-interpreted","resolution":item.resolution,"coverage":"partial","tier":"observed","notes":["No authorization decision, role hierarchy, proxy/AOP, calls, inheritance/composition, or runtime enforcement inferred."]})

def derive_secured_declaration_claim(repo,item):
    return Claim(id=stable_secured_declaration_claim_id(item.owner_id),claim=f"Java {item.owner_kind} {item.owner_qualname} directly declares Spring Security Secured metadata.",kind="structure",scope="declaration",bindings=[Binding(path=item.path,file_blob=repo.blob_sha(item.path),fn_hash=item.annotation_hash,commit=repo.head(),qualname=item.owner_qualname,role="secured_annotation",line_start=item.line_start,line_end=item.line_end,hash_kind="java_token_sha256")],provenance="git",evidence="observed",confidence=1.0,endorsed_by=None,last_verified=now_utc(),model=MODEL,body={"language":"java","edge_kind":"declares_secured_metadata","owner_id":item.owner_id,"owner_qualname":item.owner_qualname,"owner_kind":item.owner_kind,"roles":list(item.roles),"values_handling":"opaque-never-interpreted","resolution":item.resolution,"coverage":"partial","tier":"observed","notes":["No role hierarchy, authorization decision, proxy/AOP, config, calls, inheritance/composition, aliases/meta-annotations, or runtime enforcement inferred."]})

def derive_post_authorize_declaration_claim(repo,item):
    return Claim(id=stable_post_authorize_declaration_claim_id(item.owner_id),claim=f"Java {item.owner_kind} {item.owner_qualname} directly declares Spring Security PostAuthorize metadata.",kind="structure",scope="declaration",bindings=[Binding(path=item.path,file_blob=repo.blob_sha(item.path),fn_hash=item.annotation_hash,commit=repo.head(),qualname=item.owner_qualname,role="post_authorize_annotation",line_start=item.line_start,line_end=item.line_end,hash_kind="java_token_sha256")],provenance="git",evidence="observed",confidence=1.0,endorsed_by=None,last_verified=now_utc(),model=MODEL,body={"language":"java","edge_kind":"declares_post_authorize_metadata","owner_id":item.owner_id,"owner_qualname":item.owner_qualname,"owner_kind":item.owner_kind,"expression":item.expression,"values_handling":"opaque-never-interpreted","resolution":item.resolution,"coverage":"partial","tier":"observed","notes":["No runtime authorization, expression truth, security context, role hierarchy, proxy/AOP, config, calls, inheritance/composition, meta-annotations, aliases, or external symbols inferred."]})
def derive_exception_handler_declaration_claim(repo,item):
    return Claim(id=stable_exception_handler_declaration_claim_id(item.owner_id),claim=f"Java method {item.owner_qualname} directly declares Spring Web ExceptionHandler metadata.",kind="structure",scope="declaration",bindings=[Binding(path=item.path,file_blob=repo.blob_sha(item.path),fn_hash=item.annotation_hash,commit=repo.head(),qualname=item.owner_qualname,role="exception_handler_annotation",line_start=item.line_start,line_end=item.line_end,hash_kind="java_token_sha256")],provenance="git",evidence="observed",confidence=1.0,endorsed_by=None,last_verified=now_utc(),model=MODEL,body={"language":"java","edge_kind":"declares_exception_handler_metadata","owner_id":item.owner_id,"owner_qualname":item.owner_qualname,"owner_kind":item.owner_kind,"exception_types":list(item.exception_types),"values_handling":"opaque-never-resolved","resolution":item.resolution,"coverage":"partial","tier":"observed","notes":["No exception dispatch, matching, response mapping, controller advice scope, inheritance, calls, aliases, proxy/AOP, or runtime behavior inferred."]})
def derive_controller_advice_declaration_claim(repo,item):
    return Claim(id=stable_controller_advice_declaration_claim_id(item.owner_id),claim=f"Java {item.owner_kind} {item.owner_qualname} directly declares Spring Web ControllerAdvice presence.",kind="structure",scope="declaration",bindings=[Binding(path=item.path,file_blob=repo.blob_sha(item.path),fn_hash=item.annotation_hash,commit=repo.head(),qualname=item.owner_qualname,role="controller_advice_annotation",line_start=item.line_start,line_end=item.line_end,hash_kind="java_token_sha256")],provenance="git",evidence="observed",confidence=1.0,endorsed_by=None,last_verified=now_utc(),model=MODEL,body={"language":"java","edge_kind":"declares_controller_advice_presence","owner_id":item.owner_id,"owner_qualname":item.owner_qualname,"owner_kind":item.owner_kind,"source_namespace":"org.springframework.web.bind.annotation","metadata_handling":"unsupported-fail-closed","resolution":item.resolution,"coverage":"partial","tier":"observed","notes":["Presence only; no runtime scope, exception dispatch, bean discovery, advice behavior, inheritance, aliases, or meta-annotations inferred."]})
def derive_pre_filter_declaration_claim(repo,item):
    return Claim(id=stable_pre_filter_declaration_claim_id(item.owner_id),claim=f"Java {item.owner_kind} {item.owner_qualname} directly declares Spring Security PreFilter metadata.",kind="structure",scope="declaration",bindings=[Binding(path=item.path,file_blob=repo.blob_sha(item.path),fn_hash=item.annotation_hash,commit=repo.head(),qualname=item.owner_qualname,role="pre_filter_annotation",line_start=item.line_start,line_end=item.line_end,hash_kind="java_token_sha256")],provenance="git",evidence="observed",confidence=1.0,endorsed_by=None,last_verified=now_utc(),model=MODEL,body={"language":"java","edge_kind":"declares_pre_filter_metadata","owner_id":item.owner_id,"owner_qualname":item.owner_qualname,"owner_kind":item.owner_kind,"expression":item.expression,"filter_target":item.filter_target,"values_handling":"opaque-never-interpreted","resolution":item.resolution,"coverage":"partial","tier":"observed","notes":["No runtime authorization, expression truth, security context, role hierarchy, proxy/AOP, config, calls, inheritance/composition, meta-annotations, aliases, or external symbols inferred."]})

def derive_post_filter_declaration_claim(repo,item):
    return Claim(id=stable_post_filter_declaration_claim_id(item.owner_id),claim=f"Java {item.owner_kind} {item.owner_qualname} directly declares Spring Security PostFilter metadata.",kind="structure",scope="declaration",bindings=[Binding(path=item.path,file_blob=repo.blob_sha(item.path),fn_hash=item.annotation_hash,commit=repo.head(),qualname=item.owner_qualname,role="post_filter_annotation",line_start=item.line_start,line_end=item.line_end,hash_kind="java_token_sha256")],provenance="git",evidence="observed",confidence=1.0,endorsed_by=None,last_verified=now_utc(),model=MODEL,body={"language":"java","edge_kind":"declares_post_filter_metadata","owner_id":item.owner_id,"owner_qualname":item.owner_qualname,"owner_kind":item.owner_kind,"expression":item.expression,"values_handling":"opaque-never-interpreted","resolution":item.resolution,"coverage":"partial","tier":"observed","notes":["No filtering, authorization, security context, proxy/AOP, config, calls, inheritance/composition, aliases/meta-annotations, or runtime enforcement inferred."]})

def derive_resilience4j_retry_declaration_claim(repo: GitRepo, item) -> Claim:
    return Claim(id=stable_resilience4j_retry_declaration_claim_id(item.owner_id), claim=f"Java {item.owner_kind} {item.owner_qualname} directly declares Resilience4j Retry metadata.", kind="structure", scope="declaration", bindings=[Binding(path=item.path,file_blob=repo.blob_sha(item.path),fn_hash=item.annotation_hash,commit=repo.head(),qualname=item.owner_qualname,role="resilience4j_retry_annotation",line_start=item.line_start,line_end=item.line_end,hash_kind="java_token_sha256")], provenance="git", evidence="observed", confidence=1.0, endorsed_by=None, last_verified=now_utc(), model=MODEL, body={"language":"java","edge_kind":"declares_resilience4j_retry_metadata","declaration_kind":"resilience4j_retry","owner_id":item.owner_id,"owner_qualname":item.owner_qualname,"owner_kind":item.owner_kind,"name":item.name,"fallback_method":item.fallback_method,"values_handling":"opaque-never-resolved","resolution":item.resolution,"coverage":"partial","tier":"observed","notes":["Distinct from Spring Retryable; no runtime retries/backoff/exception matching/config/fallback dispatch/proxy/AOP/calls/inheritance/composition/external symbols inferred."]})


def _anchor(path: str, line_start: int | None, line_end: int | None, qualname: str | None) -> dict:
    return {"path": path, "line_start": line_start, "line_end": line_end, "qualname": qualname}


@lru_cache(maxsize=8192)
def _function_anchor_cached(root: str, path: str, qualname: str, blob: str | None) -> tuple[int | None, int | None]:
    try:
        source = (Path(root) / path).read_text(encoding="utf-8")
        for fn in extract_functions(path, source):
            if fn.qualname == qualname:
                return fn.line_start, fn.line_end
    except Exception:
        pass
    return None, None


@lru_cache(maxsize=8192)
def _declaration_anchor_cached(root: str, path: str, qualname: str, blob: str | None) -> tuple[int | None, int | None]:
    try:
        source = (Path(root) / path).read_text(encoding="utf-8")
        for decl in [*extract_declarations(path, source), *extract_java_fields(path, source)]:
            if decl.qualname == qualname:
                return decl.line_start, decl.line_end
    except Exception:
        pass
    return None, None


def _function_anchor_for(repo: GitRepo, path: str | None, qualname: str | None) -> dict:
    if not path or not qualname:
        return _anchor(path, None, None, qualname)
    blob = repo.blob_sha(path)
    line_start, line_end = _function_anchor_cached(str(repo.root), path, qualname, blob)
    return _anchor(path, line_start, line_end, qualname)


def _declaration_anchor_for(repo: GitRepo, path: str | None, qualname: str | None) -> dict:
    if not path or not qualname:
        return _anchor(path, None, None, qualname)
    blob = repo.blob_sha(path)
    line_start, line_end = _declaration_anchor_cached(str(repo.root), path, qualname, blob)
    return _anchor(path, line_start, line_end, qualname)


def _keywords(text: str, limit: int = 16) -> list[str]:
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_]{2,}", text)
    stop = {"the", "and", "for", "from", "with", "return", "class", "def", "import", "const", "let", "var"}
    seen: set[str] = set()
    out: list[str] = []
    for word in words:
        key = word.lower()
        if key in stop or key in seen:
            continue
        seen.add(key)
        out.append(word)
        if len(out) >= limit:
            break
    return out


def derive_file_claim(repo: GitRepo, path: str) -> Claim:
    text = repo.read_file(path)
    blob = repo.blob_sha(path)
    head = repo.head()
    keywords = _keywords(text)
    line_count = len(text.splitlines())
    functions = extract_functions(path, text)
    try:
        java_count = len(extract_java_classes(path, text)) + len(extract_java_methods(path, text)) + len(extract_java_fields(path, text))
    except Exception:
        java_count = 0
    claim_text = f"File {path} exposes observable identifiers: {', '.join(keywords[:8]) or 'no extracted identifiers'}."
    claim = Claim(
        id=stable_file_claim_id(path),
        claim=claim_text,
        kind="structure",
        scope="file",
        bindings=[Binding(path=path, file_blob=blob, fn_hash=None, commit=head)],
        provenance="git",
        evidence="observed",
        confidence=0.35,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "summary": f"v1 observed {line_count} lines, {len(keywords)} unique code-like identifiers, {len(functions)} Python functions, and {java_count} Java syntactic nodes; exact behavior lives in source anchors.",
            "keywords": keywords,
            "function_nodes": [fn.qualname for fn in functions],
            "java_nodes": java_count,
            "anchors": [{"path": path, "line_start": 1, "line_end": max(1, min(line_count, 40))}],
            "notes": ["File-level heuristic; use source as ground truth for precise behavior."],
        },
    )
    return verify_observed_claim(claim, text)


def derive_function_claim(repo: GitRepo, fn: FunctionNode, graph: dict | None = None) -> Claim:
    text = repo.read_file(fn.path)
    blob = repo.blob_sha(fn.path)
    head = repo.head()
    graph = graph or {}
    claim_text = f"Function {fn.qualname} in {fn.path} is a Python function node bound by worktree file_blob and token-stream fn_hash."
    claim = Claim(
        id=stable_function_claim_id(fn.path, fn.qualname),
        claim=claim_text,
        kind="structure",
        scope="function",
        bindings=[Binding(path=fn.path, file_blob=blob, fn_hash=fn.fn_hash, commit=head, qualname=fn.qualname)],
        provenance="git",
        evidence="observed",
        confidence=0.4,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "summary": f"v1 observed Python function {fn.qualname}; exact behavior lives in source anchors.",
            "keywords": fn.keywords,
            "qualname": fn.qualname,
            "interface": function_interface(text, fn),
            "anchors": [{"path": fn.path, "line_start": fn.line_start, "line_end": fn.line_end}],
            "graph": graph,
            "notes": ["fn_hash is computed from Python tokenize token stream over the current working-tree function span; comments/trivia ignored, literals/identifiers preserved."],
        },
    )
    return verify_observed_claim(claim, text)


def derive_class_claim(repo: GitRepo, cls: ClassNode) -> Claim:
    text = repo.read_file(cls.path)
    blob = repo.blob_sha(cls.path)
    head = repo.head()
    claim = Claim(
        id=stable_class_claim_id(cls.path, cls.qualname),
        claim=f"Class {cls.qualname} in {cls.path} is a Python class node bound by worktree file_blob and token-stream class_hash.",
        kind="structure",
        scope="class",
        bindings=[Binding(path=cls.path, file_blob=blob, fn_hash=cls.class_hash, commit=head, qualname=cls.qualname)],
        provenance="git",
        evidence="observed",
        confidence=0.4,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "summary": f"v2 observed Python class {cls.qualname}; class span includes method bodies, so method edits intentionally stale the class node.",
            "keywords": cls.keywords,
            "qualname": cls.qualname,
            "anchors": [{"path": cls.path, "line_start": cls.line_start, "line_end": cls.line_end}],
            "notes": ["class_hash uses the same token-stream span hash rules as functions; comments/trivia ignored, literals/identifiers preserved.", "Class span includes methods by design, causing safe over-invalidation when method bodies change."],
        },
    )
    return verify_observed_claim(claim, text)


def derive_declaration_claim(repo: GitRepo, decl: DeclarationNode) -> Claim:
    text = repo.read_file(decl.path)
    blob = repo.blob_sha(decl.path)
    head = repo.head()
    claim = Claim(
        id=stable_declaration_claim_id(decl.path, decl.qualname),
        claim=f"Declaration {decl.qualname} in {decl.path} is a {decl.language} {decl.declaration_kind} bound by worktree file_blob and normalized declaration hash.",
        kind="structure",
        scope="declaration",
        bindings=[Binding(path=decl.path, file_blob=blob, fn_hash=decl.declaration_hash, commit=head, qualname=decl.qualname)],
        provenance="git",
        evidence="observed",
        confidence=0.35,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "summary": f"v2 observed {decl.language} declaration {decl.qualname} ({decl.declaration_kind}); exact value lives in source anchors.",
            "keywords": decl.keywords,
            "qualname": decl.qualname,
            "declaration_kind": decl.declaration_kind,
            "language": decl.language,
            "anchors": [{"path": decl.path, "line_start": decl.line_start, "line_end": decl.line_end}],
            "notes": ["declaration_hash is source-bound; Python uses token-stream spans, SQL CREATE TABLE/VIEW uses the matched static CREATE clause. Dynamic SQL is not parsed."],
        },
    )
    return verify_observed_claim(claim, text)

def derive_java_node_claim(repo: GitRepo, node: ClassNode | DeclarationNode) -> Claim:
    text = repo.read_file(node.path)
    blob = repo.blob_sha(node.path)
    head = repo.head()
    is_decl = isinstance(node, DeclarationNode)
    node_kind = node.declaration_kind if is_decl else node.node_kind
    node_hash = node.declaration_hash if is_decl else node.class_hash
    scope = "declaration" if is_decl else "class"
    claim = Claim(
        id=java_node_id(node),
        claim=f"Java {node_kind} {node.qualname} in {node.path} is a tree-sitter syntactic node bound by worktree file_blob and token-stream hash.",
        kind="structure",
        scope=scope,
        bindings=[Binding(path=node.path, file_blob=blob, fn_hash=node_hash, commit=head, qualname=node.qualname)],
        provenance="git",
        evidence="observed",
        confidence=0.35,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "summary": f"Observed Java {node_kind} {node.qualname} syntactically; Java inheritance edges may be derived conservatively when extends/implements targets resolve without ambiguity.",
            "keywords": node.keywords,
            "qualname": node.qualname,
            "identity_key": None if is_decl else node.identity_key,
            "language": "java",
            "node_kind": node_kind,
            "extraction_tier": "java-treesitter-syntactic",
            "semantic_backend": {"available": False, "mode": "stub", "degrade": "semantic read-through/background interface reserved; SCIP/LSP not implemented in step0"},
            "interface": java_method_interface(text, node) if node_kind in {"method", "constructor"} else None,
            "anchors": [{"path": node.path, "line_start": node.line_start, "line_end": node.line_end, "qualname": node.qualname}],
            "notes": ["Java hash is computed from tree-sitter leaf token type+text; comments/whitespace dropped, punctuation/keywords/identifiers/literals/modifiers/annotations included.", "Java inheritance edges are syntactic-only and conservative: unresolved external/JDK, wildcard, or ambiguous supertypes are reported without linking."],
        },
    )
    return verify_observed_claim(claim, text)




def _contract_from_interface(interface: dict, graph: dict | None = None) -> dict:
    graph = graph or {}
    params = []
    for p in interface.get("params", []):
        name = p.get("name")
        if isinstance(name, str):
            params.append({"name": name, "meaning": f"parameter {name}", "confidence": 0.6, "evidence": "observed"})
    ret = interface.get("return", {}) if isinstance(interface.get("return"), dict) else {}
    shape = ret.get("shape")
    if ret.get("has_value") or shape == "value":
        meaning = "returns a value"
    elif shape == "annotation_only":
        meaning = f"declares return type {ret.get('annotation')}"
    else:
        meaning = "no value returned"
    raises = [{"exception": str(x), "condition": "literal raise observed", "confidence": 0.6, "evidence": "observed"} for x in interface.get("raises", []) if isinstance(x, str)]
    side_effects = []
    writes = graph.get("writes", []) if isinstance(graph, dict) else []
    if writes:
        for w in writes:
            side_effects.append({"kind": "writes", "target": w.get("target_qualname") or w.get("target_id"), "confidence": 0.6, "evidence": "observed"})
    return {
        "purpose": "mechanical function interface facts",
        "params": params,
        "returns": {"meaning": meaning, "conditions": [], "confidence": 0.6, "evidence": "observed"},
        "raises": raises,
        "side_effects": side_effects,
        "gotchas": [],
    }


def _contract_checks(interface: dict, slots: dict) -> dict:
    param_names = [p.get("name") for p in interface.get("params", []) if isinstance(p, dict)]
    slot_params = [p for p in slots.get("params", []) if p.get("name") in param_names]
    slots["params"] = slot_params
    allowed_raises = set(interface.get("raises", []))
    slots["raises"] = [r for r in slots.get("raises", []) if r.get("exception") in allowed_raises]
    ret = interface.get("return", {}) if isinstance(interface.get("return"), dict) else {}
    if not ret.get("has_value") and ret.get("shape") not in {"annotation_only", "value"}:
        if "returns" in slots:
            slots["returns"]["meaning"] = "no value returned"
    return {"accepted": True, "mechanical_source": "interface", "param_names": param_names, "allowed_raises": sorted(allowed_raises)}


def derive_contract_claim(repo: GitRepo, fn: FunctionNode, graph: dict | None = None) -> Claim | None:
    # Contracts are only useful for non-trivial bodies. Keep tiny functions as source-is-best.
    if (fn.line_end - fn.line_start + 1) < 5:
        return None
    text = repo.read_file(fn.path)
    interface = function_interface(text, fn)
    if not interface:
        return None
    blob = repo.blob_sha(fn.path)
    head = repo.head()
    mechanical_slots = _contract_from_interface(interface, graph=graph)
    model_candidate = derive_contract_candidate_with_command(
        command=None,
        path=fn.path,
        source_text=text,
        interface=interface,
        anchors=[{"path": fn.path, "line_start": fn.line_start, "line_end": fn.line_end, "qualname": fn.qualname}],
    )
    if model_candidate:
        sanitized = sanitize_contract_candidate(model_candidate, interface, graph=graph, language="python")
        slots = sanitized["slots"]
        checks = sanitized["_contract_checks"]
        slot_confidence = sanitized["slot_confidence"]
        contract_version = "contract.v2.semantic_sanitized"
        evidence = "inferred"
        confidence = min(max(slot_confidence.values(), default=0.35), 0.6)
        model_id = "tmf-contract-command-json"
    else:
        slots = mechanical_slots
        checks = _contract_checks(interface, slots)
        slot_confidence = {"purpose": 0.35, "params": 0.6, "returns": 0.6, "raises": 0.6, "side_effects": 0.6, "gotchas": 0.35}
        contract_version = "contract.v1.mechanical"
        evidence = "observed"
        confidence = 0.45
        model_id = MODEL
    claim = Claim(
        id=stable_contract_claim_id(fn.path, fn.qualname),
        claim=f"Contract for function {fn.qualname} in {fn.path} is mechanically derived from interface facts.",
        kind="structure",
        scope="contract",
        bindings=[Binding(path=fn.path, file_blob=blob, fn_hash=fn.fn_hash, commit=head, qualname=fn.qualname)],
        provenance="git",
        evidence=evidence,
        confidence=confidence,
        endorsed_by=None,
        last_verified=now_utc(),
        model=model_id,
        body={
            "qualname": fn.qualname,
            "language": "python",
            "contract_version": contract_version,
            "interface": interface,
            "slots": slots,
            "slot_confidence": slot_confidence,
            "anchors": [{"path": fn.path, "line_start": fn.line_start, "line_end": fn.line_end, "qualname": fn.qualname}],
            "_contract_checks": checks,
            "model_candidate_raw": model_candidate,
            "notes": ["Mechanical contract slots are observed interface facts capped at 0.6 by convention; semantic contract slots are attributed/inferred and sanitizer-capped when TMF_MODEL_COMMAND is configured.", "Binding uses full function body fn_hash, so body changes stale the contract."],
        },
    )
    if evidence == "observed":
        return verify_observed_claim(claim, text)
    claim.body["verification"] = {"method": "semantic-contract-sanitizer", "supported": True, "evidence": "inferred"}
    return claim



def _contract_from_java_interface(interface: dict) -> dict:
    params = []
    for p in interface.get("params", []):
        name = p.get("name")
        if isinstance(name, str):
            params.append({"name": name, "meaning": f"parameter {name}", "confidence": 0.6, "evidence": "observed"})
    return_type = interface.get("return_type")
    returns = "no value returned" if return_type in {None, "void"} else f"returns {return_type}"
    raises = [{"exception": str(x), "condition": "throws/throw observed", "confidence": 0.6, "evidence": "observed"} for x in interface.get("throws", []) if isinstance(x, str)]
    return {"purpose": "mechanical Java method interface facts", "params": params, "returns": {"meaning": returns, "conditions": [], "confidence": 0.6, "evidence": "observed"}, "raises": raises, "side_effects": [], "gotchas": []}


def derive_java_contract_claim(repo: GitRepo, node: ClassNode, graph: dict | None = None) -> Claim | None:
    if node.node_kind not in {"method", "constructor"} or (node.line_end - node.line_start + 1) < 5:
        return None
    text = repo.read_file(node.path)
    interface = java_method_interface(text, node)
    if not interface:
        return None
    blob = repo.blob_sha(node.path)
    head = repo.head()
    mechanical_slots = _contract_from_java_interface(interface)
    model_candidate = derive_contract_candidate_with_command(
        command=None,
        path=node.path,
        source_text=text,
        interface=interface,
        anchors=[{"path": node.path, "line_start": node.line_start, "line_end": node.line_end, "qualname": node.qualname}],
    )
    if model_candidate:
        sanitized = sanitize_contract_candidate(model_candidate, interface, graph=graph, language="java")
        slots = sanitized["slots"]
        checks = sanitized["_contract_checks"]
        slot_confidence = sanitized["slot_confidence"]
        contract_version = "contract.v2.semantic_sanitized"
        evidence = "inferred"
        confidence = min(max(slot_confidence.values(), default=0.35), 0.6)
        model_id = "tmf-contract-command-json"
    else:
        slots = mechanical_slots
        checks = {"accepted": True, "mechanical_source": "java_interface", "param_names": [p.get("name") for p in interface.get("params", [])], "allowed_raises": sorted(interface.get("throws", [])), "checks": []}
        slot_confidence = {"purpose": 0.35, "params": 0.6, "returns": 0.6, "raises": 0.6, "side_effects": 0.6, "gotchas": 0.35}
        contract_version = "contract.v1.mechanical"
        evidence = "observed"
        confidence = 0.45
        model_id = MODEL
    claim = Claim(
        id=stable_contract_claim_id(node.path, node.qualname),
        claim=f"Contract for Java method {node.qualname} in {node.path} is derived from Java interface facts and optional sanitized semantic model output.",
        kind="structure",
        scope="contract",
        bindings=[Binding(path=node.path, file_blob=blob, fn_hash=node.class_hash, commit=head, qualname=node.qualname)],
        provenance="git",
        evidence=evidence,
        confidence=confidence,
        endorsed_by=None,
        last_verified=now_utc(),
        model=model_id,
        body={"qualname": node.qualname, "language": "java", "node_kind": node.node_kind, "extraction_tier": "java-contract", "contract_version": contract_version, "interface": interface, "slots": slots, "slot_confidence": slot_confidence, "anchors": [{"path": node.path, "line_start": node.line_start, "line_end": node.line_end, "qualname": node.qualname}], "_contract_checks": checks, "model_candidate_raw": model_candidate, "notes": ["Offline mechanical Java contract only when no model command is configured; semantic contract slots are attributed/inferred and sanitizer-capped when TMF_MODEL_COMMAND is configured.", "Binding uses full method body hash, so body changes stale the contract."]},
    )
    if evidence == "observed":
        return verify_observed_claim(claim, text)
    claim.body["verification"] = {"method": "semantic-contract-sanitizer", "supported": True, "evidence": "inferred"}
    return claim

def derive_config_claim(repo: GitRepo, node: ConfigNode) -> Claim:
    text = repo.read_file(node.path)
    blob = repo.blob_sha(node.path)
    head = repo.head()
    claim = Claim(
        id=stable_config_claim_id(node.path, node.key),
        claim=f"Config key {node.key} in {node.path} is a top-level {node.config_kind} key bound by normalized value hash.",
        kind="structure",
        scope="config",
        bindings=[Binding(path=node.path, file_blob=blob, fn_hash=node.config_hash, commit=head, qualname=node.key)],
        provenance="git",
        evidence="observed",
        confidence=0.35,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "summary": f"v2 observed top-level {node.config_kind} config key {node.key}; exact value lives in source fallback.",
            "keywords": node.keywords,
            "qualname": node.key,
            "config_kind": node.config_kind,
            "anchors": [{"path": node.path, "line_start": node.line_start, "line_end": node.line_end}],
            "notes": ["config_hash is computed from canonical parsed top-level key value; whitespace and object key order are ignored, value changes stale the node."],
        },
    )
    return verify_observed_claim(claim, text)



def derive_api_claim(repo: GitRepo, api: ApiNode) -> Claim:
    text = repo.read_file(api.path)
    blob = repo.blob_sha(api.path)
    head = repo.head()
    relationship = bool(api.route_path_source and api.handler_path and api.handler_hash and api.handler_node_id)
    claim = Claim(
        id=(stable_api_relationship_claim_id(api.route_path_source, api.method, api.route_path, api.handler_node_id)
            if relationship else stable_api_claim_id(api.path, api.method, api.route_path, api.handler_qualname)),
        claim=f"API route {api.method} {api.route_path} in {api.path} is handled by {api.handler_qualname}.",
        kind="structure",
        scope="api",
        bindings=([
            Binding(path=api.route_path_source, file_blob=repo.blob_sha(api.route_path_source), fn_hash=api.route_hash, commit=head,
                    qualname=api.route_qualname, role="route_declaration", line_start=api.route_line_start,
                    line_end=api.route_line_end, hash_kind="java_ast_span"),
            Binding(path=api.handler_path, file_blob=repo.blob_sha(api.handler_path), fn_hash=api.handler_hash, commit=head,
                    qualname=api.handler_qualname, role="handler", line_start=None, line_end=None,
                    hash_kind="java_node"),
        ] if relationship else [Binding(path=api.path, file_blob=blob, fn_hash=api.api_hash, commit=head, qualname=api.handler_qualname)]),
        provenance="git",
        evidence="observed",
        confidence=0.45,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "summary": f"v2 observed API route {api.method} {api.route_path} handled by {api.handler_qualname}.",
            "keywords": api.keywords,
            "method": api.method,
            "route_path": api.route_path,
            "path": api.route_path,
            "http_methods": [api.method.lower() if api.method.upper() == "UNSPECIFIED" else api.method.upper()],
            "language": "java" if api.path.endswith(".java") else "python",
            "handler_qualname": api.handler_qualname,
            "handler_node_id": api.handler_node_id,
            "service_name": api.service_name,
            "service_url": api.service_url,
            "rpc_adapter": api.adapter,
            "api_binding_model": "dual-v2" if relationship else "legacy-single-v1",
            "route_source_path": api.route_path_source,
            "route_qualname": api.route_qualname,
            "handler_path": api.handler_path,
            "qualname": api.handler_qualname,
            "anchors": ([
                {"path": api.route_path_source, "line_start": api.route_line_start, "line_end": api.route_line_end, "role": "route_declaration"},
                {"path": api.handler_path, "line_start": None, "line_end": None, "qualname": api.handler_qualname, "role": "handler"},
            ] if relationship else [{"path": api.path, "line_start": api.line_start, "line_end": api.line_end}]),
            "notes": ["api_hash includes recognized route decorators plus handler body using the same token-stream span hash rules as functions."],
        },
    )
    if api.path.endswith(".java"):
        claim.body["verification"] = {
            "method": "java-ast-literal-route-check",
            "supported": True,
        }
        return claim
    return verify_observed_claim(claim, text)

def derive_call_edge_claim(repo: GitRepo, edge, anchor_by_id: dict[str, dict] | None = None) -> Claim | None:
    if not edge.caller_path or not edge.callee_path or not edge.caller_fn_hash or not edge.callee_fn_hash:
        return None
    caller_blob = repo.blob_sha(edge.caller_path)
    callee_blob = repo.blob_sha(edge.callee_path)
    head = repo.head()
    anchor_by_id = anchor_by_id or {}
    language = getattr(edge, "language", "python")
    caller_anchor = anchor_by_id.get(edge.caller_id)
    if caller_anchor is None:
        caller_anchor = _java_node_anchor_for(repo, edge.caller_path, edge.caller_qualname, getattr(edge, "caller_node_kind", "method")) if language == "java" else _function_anchor_for(repo, edge.caller_path, edge.caller_qualname)
    callee_anchor = anchor_by_id.get(edge.callee_id)
    if callee_anchor is None:
        callee_anchor = _java_node_anchor_for(repo, edge.callee_path, edge.callee_qualname, getattr(edge, "callee_node_kind", "method")) if language == "java" else _function_anchor_for(repo, edge.callee_path, edge.callee_qualname)
    return Claim(
        id=stable_call_edge_claim_id(edge.caller_id, edge.callee_id),
        claim=f"{edge.caller_id} calls {edge.callee_qualname}.",
        kind="structure",
        scope="cross-repo",
        bindings=[
            Binding(path=edge.caller_path, file_blob=caller_blob, fn_hash=edge.caller_fn_hash, commit=head, qualname=edge.caller_qualname),
            Binding(path=edge.callee_path, file_blob=callee_blob, fn_hash=edge.callee_fn_hash, commit=head, qualname=edge.callee_qualname),
        ],
        provenance="git",
        evidence="observed",
        confidence=0.55,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "edge_kind": "calls",
            "caller_id": edge.caller_id,
            "callee_id": edge.callee_id,
            "caller_path": edge.caller_path,
            "callee_path": edge.callee_path,
            "callee_qualname": edge.callee_qualname,
            "resolution": edge.resolution,
            "language": language,
            "caller_anchor": caller_anchor,
            "callee_anchor": callee_anchor,
            "anchors": [],
            "notes": ["Call edge is observed only when statically resolved without ambiguity; source remains authority."],
        },
    )



def derive_override_edge_claim(repo: GitRepo, edge) -> Claim | None:
    if not edge.method_path or not edge.overridden_path or not edge.method_hash or not edge.overridden_hash:
        return None
    method_blob = repo.blob_sha(edge.method_path)
    overridden_blob = repo.blob_sha(edge.overridden_path)
    head = repo.head()
    return Claim(
        id=stable_override_edge_claim_id(edge.method_id, edge.overridden_id),
        claim=f"{edge.method_id} is an override candidate for {edge.overridden_qualname}.",
        kind="structure",
        scope="cross-repo",
        bindings=[
            Binding(path=edge.method_path, file_blob=method_blob, fn_hash=edge.method_hash, commit=head, qualname=edge.method_qualname),
            Binding(path=edge.overridden_path, file_blob=overridden_blob, fn_hash=edge.overridden_hash, commit=head, qualname=edge.overridden_qualname),
        ],
        provenance="git",
        evidence="inferred",
        confidence=0.55,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "edge_kind": "overrides",
            "language": "java",
            "method_id": edge.method_id,
            "overridden_id": edge.overridden_id,
            "method_path": edge.method_path,
            "overridden_path": edge.overridden_path,
            "overridden_qualname": edge.overridden_qualname,
            "resolution": edge.resolution,
            "method_anchor": _java_node_anchor_for(repo, edge.method_path, edge.method_qualname, "method"),
            "overridden_anchor": _java_node_anchor_for(repo, edge.overridden_path, edge.overridden_qualname, "method"),
            "anchors": [],
            "notes": ["Java override edge is an inferred candidate from same-file inheritance and matching method signature only; external/cross-file and ambiguous cases remain unresolved."],
        },
    )



def derive_type_use_edge_claim(repo: GitRepo, edge) -> Claim | None:
    if not edge.user_path or not edge.type_path or not edge.user_hash or not edge.type_hash:
        return None
    user_blob = repo.blob_sha(edge.user_path)
    type_blob = repo.blob_sha(edge.type_path)
    head = repo.head()
    return Claim(
        id=stable_type_use_edge_claim_id(edge.user_id, edge.type_id, edge.use_kind),
        claim=f"{edge.user_id} uses Java type {edge.type_qualname} as {edge.use_kind}.",
        kind="structure",
        scope="cross-repo",
        bindings=[
            Binding(path=edge.user_path, file_blob=user_blob, fn_hash=edge.user_hash, commit=head, qualname=edge.user_qualname),
            Binding(path=edge.type_path, file_blob=type_blob, fn_hash=edge.type_hash, commit=head, qualname=edge.type_qualname),
        ],
        provenance="git",
        evidence="observed",
        confidence=0.55,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "edge_kind": "uses_type",
            "language": "java",
            "user_id": edge.user_id,
            "type_id": edge.type_id,
            "type_qualname": edge.type_qualname,
            "use_kind": edge.use_kind,
            "user_path": edge.user_path,
            "type_path": edge.type_path,
            "user_qualname": edge.user_qualname,
            "resolution": edge.resolution,
            "user_anchor": _java_node_anchor_for(repo, edge.user_path, edge.user_qualname, edge.user_node_kind or "method"),
            "type_anchor": _java_node_anchor_for(repo, edge.type_path, edge.type_qualname, edge.type_node_kind or "class"),
            "anchors": [],
            "notes": ["Java uses_type edge is observed only for same-file or explicit-import unique type resolution; external/JDK/wildcard/ambiguous types stay unresolved."],
        },
    )





def derive_topic_claim(repo: GitRepo, topic_name: str) -> Claim:
    return Claim(
        id=stable_topic_claim_id(topic_name), claim=f"Kafka topic {topic_name} is referenced by code in this repository.", kind="structure", scope="api", bindings=[], provenance="git", evidence="attributed", confidence=0.5, endorsed_by=None, last_verified=now_utc(), model=MODEL,
        body={"node_kind": "topic", "topic_name": topic_name, "graph": {}, "notes": ["Topic node is an attributed pub-sub rendezvous point; TMF does not infer direct producer-consumer coupling."]},
    )


def derive_inject_edge_claim(repo: GitRepo, edge) -> Claim | None:
    if not edge.injector_path or not edge.bean_path or not edge.injector_hash or not edge.bean_hash:
        return None
    head = repo.head()
    return Claim(
        id=stable_inject_edge_claim_id(edge.injector_id, edge.bean_id, edge.inject_kind),
        claim=f"{edge.injector_id} is attributed to inject Spring bean {edge.bean_qualname}.", kind="structure", scope="cross-repo",
        bindings=[Binding(path=edge.injector_path, file_blob=repo.blob_sha(edge.injector_path), fn_hash=edge.injector_hash, commit=head, qualname=edge.injector_qualname), Binding(path=edge.bean_path, file_blob=repo.blob_sha(edge.bean_path), fn_hash=edge.bean_hash, commit=head, qualname=edge.bean_qualname)],
        provenance="git", evidence="attributed", confidence=min(float(getattr(edge, "confidence", 0.55)), 0.6), endorsed_by=None, last_verified=now_utc(), model=MODEL,
        body={"edge_kind": "injects", "injector_id": edge.injector_id, "bean_id": edge.bean_id, "bean_qualname": edge.bean_qualname, "inject_kind": edge.inject_kind, "injector_path": edge.injector_path, "bean_path": edge.bean_path, "injector_qualname": edge.injector_qualname, "resolution": edge.resolution, "coverage": "partial", "tier": "attributed", "notes": ["Spring DI edge is framework-attributed, not syntactically observed; confidence capped at 0.6."]},
    )


def derive_configuration_properties_claim(repo: GitRepo, edge) -> Claim:
    return Claim(
        id=stable_configuration_properties_edge_claim_id(edge.source_id, edge.prefix),
        claim=f"{edge.source_id} declares Spring ConfigurationProperties prefix {edge.prefix}.",
        kind="structure", scope="config",
        bindings=[Binding(path=edge.source_path, file_blob=repo.blob_sha(edge.source_path), fn_hash=edge.source_hash, commit=repo.head(), qualname=edge.source_qualname)],
        provenance="git", evidence="attributed", confidence=min(edge.confidence, 0.6), endorsed_by=None,
        last_verified=now_utc(), model=MODEL,
        body={"edge_kind": "configuration_properties", "source_id": edge.source_id, "source_path": edge.source_path,
              "source_qualname": edge.source_qualname, "target_kind": edge.target_kind, "prefix": edge.prefix,
              "resolution": edge.resolution, "coverage": "partial", "tier": "attributed",
              "notes": ["Literal annotation metadata only; no runtime binding, property keys, member writes, validation, scanning, or calls are inferred."]},
    )


def derive_topic_edge_claim(repo: GitRepo, edge) -> Claim | None:
    if not edge.source_path or not edge.source_hash:
        return None
    edge_id = stable_topic_pub_edge_claim_id(edge.source_id, edge.topic_name) if edge.edge_kind == "publishes_to" else stable_topic_sub_edge_claim_id(edge.source_id, edge.topic_name)
    head = repo.head()
    bindings = [Binding(path=edge.source_path, file_blob=repo.blob_sha(edge.source_path), fn_hash=edge.source_hash, commit=head, qualname=edge.source_qualname)]
    if getattr(edge, "dependency_path", None):
        bindings.append(Binding(path=edge.dependency_path, file_blob=repo.blob_sha(edge.dependency_path), fn_hash=None, commit=head, qualname=getattr(edge, "dependency_qualname", None)))
    return Claim(
        id=edge_id, claim=f"{edge.source_id} {edge.edge_kind} message topic/channel {edge.topic_name}.", kind="structure", scope="cross-repo",
        bindings=bindings,
        provenance="git", evidence="attributed", confidence=min(float(getattr(edge, "confidence", 0.5)), 0.6), endorsed_by=None, last_verified=now_utc(), model=MODEL,
        body={"edge_kind": edge.edge_kind, "source_id": edge.source_id, "topic_id": stable_topic_claim_id(edge.topic_name), "topic_name": edge.topic_name, "source_path": edge.source_path, "source_qualname": edge.source_qualname, "source_anchor": _java_node_anchor_for(repo, edge.source_path, edge.source_qualname, "method"), "dependency_path": getattr(edge, "dependency_path", None), "dependency_qualname": getattr(edge, "dependency_qualname", None), "group_id": getattr(edge, "group_id", None), "payload_type": getattr(edge, "payload_type", None), "resolution": edge.resolution, "coverage": "partial", "tier": "attributed", "notes": ["Messaging pub-sub edges attach producers/consumers to a literal topic/channel node only; group and payload are declaration/observed expression metadata, not runtime delivery semantics."]},
    )


def derive_env_claim(repo: GitRepo, env_name: str) -> Claim:
    return Claim(
        id=stable_env_claim_id(env_name),
        claim=f"Environment variable {env_name} is read by code in this repository.",
        kind="structure",
        scope="config",
        bindings=[],
        provenance="git",
        evidence="observed",
        confidence=0.4,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={"node_kind": "env", "env_name": env_name, "keywords": [env_name], "notes": ["Env nodes are keyed only by variable name; TMF does not infer type, value, or source."], "graph": {}},
    )


def derive_env_read_edge_claim(repo: GitRepo, edge) -> Claim | None:
    if not edge.reader_path or not edge.reader_fn_hash:
        return None
    reader_blob = repo.blob_sha(edge.reader_path)
    head = repo.head()
    return Claim(
        id=stable_env_read_edge_claim_id(edge.reader_id, edge.env_name),
        claim=f"{edge.reader_id} reads environment variable {edge.env_name}.",
        kind="structure",
        scope="cross-repo",
        bindings=[Binding(path=edge.reader_path, file_blob=reader_blob, fn_hash=edge.reader_fn_hash, commit=head, qualname=edge.reader_qualname)],
        provenance="git",
        evidence="observed",
        confidence=0.55,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={"edge_kind": "reads_env", "reader_id": edge.reader_id, "env_id": stable_env_claim_id(edge.env_name), "env_name": edge.env_name, "reader_path": edge.reader_path, "reader_qualname": edge.reader_qualname, "resolution": edge.resolution, "coverage": "partial", "reader_anchor": _function_anchor_for(repo, edge.reader_path, edge.reader_qualname), "anchors": []},
    )


def derive_config_key_read_edge_claim(repo: GitRepo, edge) -> Claim | None:
    if not edge.reader_path or not edge.config_path or not edge.reader_fn_hash or not edge.config_hash:
        return None
    reader_blob = repo.blob_sha(edge.reader_path)
    config_blob = repo.blob_sha(edge.config_path)
    head = repo.head()
    return Claim(
        id=stable_config_read_edge_claim_id(edge.reader_id, edge.config_id),
        claim=f"{edge.reader_id} reads config key {edge.config_key}.",
        kind="structure",
        scope="cross-repo",
        bindings=[Binding(path=edge.reader_path, file_blob=reader_blob, fn_hash=edge.reader_fn_hash, commit=head, qualname=edge.reader_qualname), Binding(path=edge.config_path, file_blob=config_blob, fn_hash=edge.config_hash, commit=head, qualname=edge.config_key)],
        provenance="git",
        evidence="observed",
        confidence=0.55,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={"edge_kind": "reads_config_key", "reader_id": edge.reader_id, "config_id": edge.config_id, "config_key": edge.config_key, "reader_path": edge.reader_path, "config_path": edge.config_path, "reader_qualname": edge.reader_qualname, "resolution": edge.resolution, "coverage": "partial", "reader_anchor": _function_anchor_for(repo, edge.reader_path, edge.reader_qualname), "config_anchor": _anchor(edge.config_path, 1, 1, edge.config_key), "anchors": []},
    )


def derive_read_edge_claim(repo: GitRepo, edge, function_anchor_by_id: dict[str, dict] | None = None, declaration_anchor_by_id: dict[str, dict] | None = None) -> Claim | None:
    if not edge.reader_path or not edge.declaration_path or not edge.reader_fn_hash or not edge.declaration_hash:
        return None
    reader_blob = repo.blob_sha(edge.reader_path)
    declaration_blob = repo.blob_sha(edge.declaration_path)
    head = repo.head()
    function_anchor_by_id = function_anchor_by_id or {}
    declaration_anchor_by_id = declaration_anchor_by_id or {}
    language = getattr(edge, "language", "python")
    reader_anchor = function_anchor_by_id.get(edge.reader_id)
    if reader_anchor is None:
        reader_anchor = _java_node_anchor_for(repo, edge.reader_path, getattr(edge, "reader_qualname", None), "method") if language == "java" else _function_anchor_for(repo, edge.reader_path, edge.reader_qualname)
    declaration_anchor = declaration_anchor_by_id.get(edge.declaration_id)
    if declaration_anchor is None:
        declaration_anchor = _java_node_anchor_for(repo, edge.declaration_path, edge.declaration_qualname, getattr(edge, "declaration_kind", "field")) if language == "java" else _declaration_anchor_for(repo, edge.declaration_path, edge.declaration_qualname)
    return Claim(
        id=stable_read_edge_claim_id(edge.reader_id, edge.declaration_id),
        claim=f"{edge.reader_id} reads declaration {edge.declaration_qualname}.",
        kind="structure",
        scope="cross-repo",
        bindings=[
            Binding(path=edge.reader_path, file_blob=reader_blob, fn_hash=edge.reader_fn_hash, commit=head, qualname=edge.reader_qualname),
            Binding(path=edge.declaration_path, file_blob=declaration_blob, fn_hash=edge.declaration_hash, commit=head, qualname=edge.declaration_qualname),
        ],
        provenance="git",
        evidence="observed",
        confidence=0.55,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "edge_kind": "reads",
            "reader_id": edge.reader_id,
            "declaration_id": edge.declaration_id,
            "reader_path": edge.reader_path,
            "declaration_path": edge.declaration_path,
            "declaration_qualname": edge.declaration_qualname,
            "resolution": edge.resolution,
            "language": language,
            "coverage": "partial",
            "reader_anchor": reader_anchor,
            "declaration_anchor": declaration_anchor,
            "anchors": [],
            "notes": ["Read edge is observed only for unambiguous Python Name loads of tracked module-level declarations; source remains authority.", "Coverage is partial: only already-derived files and conservative static reads are included."],
        },
    )



def derive_write_edge_claim(repo: GitRepo, edge) -> Claim | None:
    if not edge.writer_path or not edge.declaration_path or not edge.writer_fn_hash or not edge.declaration_hash:
        return None
    writer_blob = repo.blob_sha(edge.writer_path)
    declaration_blob = repo.blob_sha(edge.declaration_path)
    head = repo.head()
    return Claim(
        id=stable_write_edge_claim_id(edge.writer_id, edge.declaration_id),
        claim=f"{edge.writer_id} writes declaration {edge.declaration_qualname}.",
        kind="structure",
        scope="cross-repo",
        bindings=[
            Binding(path=edge.writer_path, file_blob=writer_blob, fn_hash=edge.writer_fn_hash, commit=head, qualname=edge.writer_qualname),
            Binding(path=edge.declaration_path, file_blob=declaration_blob, fn_hash=edge.declaration_hash, commit=head, qualname=edge.declaration_qualname),
        ],
        provenance="git",
        evidence="observed",
        confidence=0.55,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "edge_kind": "writes",
            "writer_id": edge.writer_id,
            "declaration_id": edge.declaration_id,
            "writer_path": edge.writer_path,
            "declaration_path": edge.declaration_path,
            "declaration_qualname": edge.declaration_qualname,
            "resolution": edge.resolution,
            "language": getattr(edge, "language", "python"),
            "coverage": "partial",
            "writer_anchor": _java_node_anchor_for(repo, edge.writer_path, getattr(edge, "writer_qualname", None), "method") if getattr(edge, "language", "python") == "java" else _function_anchor_for(repo, edge.writer_path, edge.writer_qualname),
            "declaration_anchor": _java_node_anchor_for(repo, edge.declaration_path, edge.declaration_qualname, getattr(edge, "declaration_kind", "field")) if getattr(edge, "language", "python") == "java" else _declaration_anchor_for(repo, edge.declaration_path, edge.declaration_qualname),
            "anchors": [],
            "notes": ["Write edge is observed only for Python global declarations or other unambiguous writes to tracked module-level declarations; source remains authority.", "Coverage is partial: only already-derived files and conservative static writes are included."],
        },
    )


def _java_node_anchor_for(repo: GitRepo, path: str | None, qualname: str | None, node_kind: str | None) -> dict:
    if not path or not qualname or not node_kind:
        return _anchor(path, None, None, qualname)
    try:
        source = repo.read_file(path)
        for node in [*extract_java_classes(path, source), *extract_java_methods(path, source), *extract_java_fields(path, source)]:
            kind = node.declaration_kind if hasattr(node, "declaration_kind") else node.node_kind
            if node.qualname == qualname and kind == node_kind:
                return _anchor(path, node.line_start, node.line_end, qualname)
    except Exception:
        pass
    return _anchor(path, None, None, qualname)


def derive_inherit_edge_claim(repo: GitRepo, edge) -> Claim | None:
    if not edge.child_path or not edge.parent_path or not edge.child_hash or not edge.parent_hash:
        return None
    child_blob = repo.blob_sha(edge.child_path)
    parent_blob = repo.blob_sha(edge.parent_path)
    head = repo.head()
    return Claim(
        id=stable_inherit_edge_claim_id(edge.child_id, edge.parent_id, edge.relation),
        claim=f"{edge.child_id} {edge.relation} {edge.parent_qualname}.",
        kind="structure",
        scope="cross-repo",
        bindings=[
            Binding(path=edge.child_path, file_blob=child_blob, fn_hash=edge.child_hash, commit=head, qualname=edge.child_qualname),
            Binding(path=edge.parent_path, file_blob=parent_blob, fn_hash=edge.parent_hash, commit=head, qualname=edge.parent_qualname),
        ],
        provenance="git",
        evidence="observed",
        confidence=0.55,
        endorsed_by=None,
        last_verified=now_utc(),
        model=MODEL,
        body={
            "edge_kind": "inherits",
            "relation": edge.relation,
            "child_id": edge.child_id,
            "parent_id": edge.parent_id,
            "child_path": edge.child_path,
            "parent_path": edge.parent_path,
            "child_qualname": edge.child_qualname,
            "parent_qualname": edge.parent_qualname,
            "child_node_kind": edge.child_node_kind,
            "parent_node_kind": edge.parent_node_kind,
            "resolution": edge.resolution,
            "coverage": "partial",
            "child_anchor": _java_node_anchor_for(repo, edge.child_path, edge.child_qualname, edge.child_node_kind),
            "parent_anchor": _java_node_anchor_for(repo, edge.parent_path, edge.parent_qualname, edge.parent_node_kind),
            "anchors": [],
            "notes": ["Java inheritance edge is observed only for syntactic extends/implements targets resolved by same-file uniqueness or explicit import; unresolved supertypes are not linked.", "Coverage is partial and syntactic; semantic resolution is deferred to SCIP/LSP step."],
        },
    )


SEMANTIC_CLAIM_EDGE_KINDS = {"semantic_depends_on", "semantic_calls", "semantic_uses_type"}


def _sanitize_semantic_claim(claim: Claim, existing_ids: set[str]) -> Claim | None:
    """Conservatively accept a semantic overlay claim.

    Semantic claims are never allowed to replace deterministic syntactic/observed
    claims. Accepted overlays are always attributed and capped at confidence 0.6.
    """
    if claim.id in existing_ids:
        return None
    body = dict(claim.body or {})
    if body.get("extraction_tier") != "semantic-resolved" and body.get("tier") != "semantic-resolved":
        return None
    edge_kind = body.get("edge_kind")
    if edge_kind is not None and edge_kind not in SEMANTIC_CLAIM_EDGE_KINDS:
        return None
    body["extraction_tier"] = "semantic-resolved"
    body["tier"] = "semantic-resolved"
    claim.evidence = "attributed"
    claim.confidence = min(float(claim.confidence), 0.6)
    claim.body = body
    return claim

def derive_claims_for_path(repo: GitRepo, path: str, *, use_model: bool = False, model: DeriverModel | None = None, semantic_backend: SemanticExtractorBackend | None = None) -> list[Claim]:
    text = repo.read_file(path)
    functions = extract_functions(path, text)
    classes = extract_classes(path, text)
    declarations = [*extract_declarations(path, text), *extract_sql_declarations(path, text)]
    configs = extract_configs(path, text)
    apis = extract_apis(path, text)
    java_classes: list[ClassNode] = []
    java_methods: list[ClassNode] = []
    java_fields: list[DeclarationNode] = []
    java_apis: list[ApiNode] = []
    java_degrade_hint: str | None = None
    if path.endswith(".java"):
        status = java_status()
        if status.available:
            java_classes = extract_java_classes(path, text)
            java_methods = extract_java_methods(path, text)
            java_fields = extract_java_fields(path, text)
            java_apis = [*extract_java_apis(path, text), *extract_java_functional_apis(repo, path, text), *extract_java_feign_apis(path, text)]
        else:
            java_degrade_hint = status.degrade_hint or JAVA_DEGRADE_HINT
    claims = [derive_file_claim(repo, path)]
    semantic_overlay_candidates: list[Claim] = []
    if semantic_backend is not None:
        if semantic_backend.available():
            semantic_backend.enqueue_background_refresh(str(repo.root), path)
            semantic_overlay_candidates = list(semantic_backend.semantic_claims_for_path(repo, path, text) or [])
            claims[0].body["semantic_extraction"] = {"available": True, "degraded": True, "queued_background_refresh": True, "extraction_tier": "semantic-resolved", "accepted_claims": 0, "rejected_claims": 0}
            status = getattr(semantic_backend, "last_status", None)
            if isinstance(status, dict):
                claims[0].body["semantic_extraction"]["provider_status"] = dict(status)
        else:
            claims[0].body["semantic_extraction"] = {"available": False, "degraded": True, "queued_background_refresh": False, "extraction_tier": "semantic-resolved", "accepted_claims": 0, "rejected_claims": 0}
            status = getattr(semantic_backend, "last_status", None)
            if isinstance(status, dict):
                claims[0].body["semantic_extraction"]["provider_status"] = dict(status)
    if java_degrade_hint:
        claims[0].body["java_extraction"] = {"available": False, "degraded": True, "degrade_hint": java_degrade_hint}
    claims.extend(derive_class_claim(repo, cls) for cls in classes)
    claims.extend(derive_declaration_claim(repo, decl) for decl in declarations)
    claims.extend(derive_config_claim(repo, config) for config in configs)
    claims.extend(derive_api_claim(repo, api) for api in [*apis, *java_apis])
    claims.extend(derive_java_node_claim(repo, node) for node in [*java_classes, *java_methods, *java_fields])
    edges, unresolved = resolve_call_edges(path, text, functions, repo=repo)
    read_edges, unresolved_reads = resolve_read_edges(path, text, functions, declarations, repo=repo)
    write_edges, unresolved_writes = resolve_write_edges(path, text, functions, declarations, repo=repo)
    env_read_edges, unresolved_env_reads = resolve_env_read_edges(path, text, functions)
    for _env in sorted({edge.env_name for edge in env_read_edges}):
        claims.append(derive_env_claim(repo, _env))
    config_key_read_edges, unresolved_config_key_reads = resolve_config_key_read_edges(path, text, functions, repo=repo)
    inherit_edges, unresolved_inherits = resolve_java_inherit_edges(path, text, java_classes, repo=repo) if java_classes else ([], {})
    java_call_edges, unresolved_java_calls = resolve_java_call_edges(path, text, java_methods, repo=repo, inherit_edges=inherit_edges) if java_methods else ([], {})
    java_field_edges, unresolved_java_fields = resolve_java_field_edges(path, text, java_methods, java_fields, repo=repo, inherit_edges=inherit_edges) if java_methods else ([], {})
    java_override_edges, unresolved_java_overrides = resolve_java_override_edges(path, text, java_classes, java_methods, inherit_edges, unresolved_inherits, repo=repo) if java_methods else ([], {})
    java_type_edges, unresolved_java_types = resolve_java_type_use_edges(path, text, java_classes, java_methods, java_fields, repo=repo) if (java_classes or java_fields or java_methods) else ([], {})
    java_inject_edges, unresolved_java_injects = resolve_java_inject_edges(path, text, java_classes, java_fields, inherit_edges, repo=repo, java_methods=java_methods) if java_classes else ([], {})
    java_topic_edges, unresolved_java_topics = resolve_java_topic_edges(path, text, java_methods, repo=repo) if java_methods else ([], {})
    java_cache_declarations, unresolved_java_cache = resolve_java_cache_declarations(path, text, java_methods) if java_methods else ([], {})
    java_scheduling_declarations, unresolved_java_scheduling = resolve_java_scheduling_declarations(path, text, java_methods) if java_methods else ([], {})
    java_transaction_declarations, unresolved_java_transactions = resolve_java_transaction_declarations(path, text, java_classes, java_methods) if (java_classes or java_methods) else ([], {})
    java_async_declarations, unresolved_java_async = resolve_java_async_declarations(path, text, java_classes, java_methods) if (java_classes or java_methods) else ([], {})
    java_retry_declarations, unresolved_java_retry = resolve_java_retry_declarations(path, text, java_classes, java_methods) if (java_classes or java_methods) else ([], {})
    java_circuit_breaker_declarations, unresolved_java_circuit_breaker = resolve_java_circuit_breaker_declarations(path, text, java_classes, java_methods) if (java_classes or java_methods) else ([], {})
    java_rate_limiter_declarations, unresolved_java_rate_limiter = resolve_java_rate_limiter_declarations(path, text, java_classes, java_methods) if (java_classes or java_methods) else ([], {})
    java_bulkhead_declarations, unresolved_java_bulkhead = resolve_java_bulkhead_declarations(path, text, java_classes, java_methods) if (java_classes or java_methods) else ([], {})
    java_time_limiter_declarations, unresolved_java_time_limiter = resolve_java_time_limiter_declarations(path, text, java_classes, java_methods) if (java_classes or java_methods) else ([], {})
    java_pre_authorize_declarations, unresolved_java_pre_authorize = resolve_java_pre_authorize_declarations(path, text, java_classes, java_methods) if (java_classes or java_methods) else ([], {})
    java_roles_allowed_declarations, unresolved_java_roles_allowed = resolve_java_roles_allowed_declarations(path, text, java_classes, java_methods) if (java_classes or java_methods) else ([], {})
    java_secured_declarations, unresolved_java_secured = resolve_java_secured_declarations(path, text, java_classes, java_methods) if (java_classes or java_methods) else ([], {})
    java_post_authorize_declarations, unresolved_java_post_authorize = resolve_java_post_authorize_declarations(path, text, java_classes, java_methods) if (java_classes or java_methods) else ([], {})
    java_exception_handler_declarations, unresolved_java_exception_handler = resolve_java_exception_handler_declarations(path, text, java_classes, java_methods) if java_methods else ([], {})
    java_controller_advice_declarations, unresolved_java_controller_advice = resolve_java_controller_advice_declarations(path, text, java_classes) if java_classes else ([], {})
    java_pre_filter_declarations, unresolved_java_pre_filter = resolve_java_pre_filter_declarations(path, text, java_classes, java_methods) if (java_classes or java_methods) else ([], {})
    java_post_filter_declarations, unresolved_java_post_filter = resolve_java_post_filter_declarations(path, text, java_classes, java_methods) if (java_classes or java_methods) else ([], {})
    java_resilience4j_retry_declarations, unresolved_java_resilience4j_retry = resolve_java_resilience4j_retry_declarations(path, text, java_classes, java_methods) if (java_classes or java_methods) else ([], {})
    java_sagas, unresolved_java_sagas = resolve_java_saga_definitions(path, text, java_classes, repo=repo) if java_classes else ({}, {})
    java_config_properties, unresolved_java_config_properties = resolve_java_configuration_properties(path, text, java_classes, java_methods) if (java_classes or java_methods) else ([], {})
    java_spring_declarations, unresolved_java_spring_declarations = resolve_java_spring_declarations(path, text, java_classes, java_methods) if (java_classes or java_methods) else ({}, {})
    java_persistence_declarations, unresolved_java_persistence_declarations = resolve_java_persistence_declarations(path, text, java_classes, java_methods, java_fields) if (java_classes or java_methods or java_fields) else ({}, {})
    java_repository_declarations, unresolved_java_repository_declarations = resolve_java_repository_declarations(path, text, java_classes, java_methods, repo=repo) if (java_classes or java_methods) else ({}, {})
    java_mybatis_declarations, unresolved_java_mybatis_declarations = resolve_java_mybatis_declarations(path, text, java_classes, java_methods) if (java_classes or java_methods) else ({}, {})
    for _topic in sorted({edge.topic_name for edge in java_topic_edges}):
        claims.append(derive_topic_claim(repo, _topic))
    edges = [*edges, *java_call_edges]
    # adapt Java field edges to existing read/write edge derivation surfaces
    for fed in java_field_edges:
        if fed.edge_kind == "reads":
            read_edges.append(type("JavaReadEdge", (), {
                "reader_id": fed.accessor_id, "declaration_id": fed.field_id,
                "declaration_qualname": fed.field_qualname, "resolution": fed.resolution,
                "reader_path": fed.accessor_path, "declaration_path": fed.field_path,
                "reader_fn_hash": fed.accessor_hash, "declaration_hash": fed.field_hash,
                "reader_qualname": fed.accessor_qualname, "evidence": fed.evidence,
                "language": "java", "declaration_kind": "field",
            })())
        elif fed.edge_kind == "writes":
            write_edges.append(type("JavaWriteEdge", (), {
                "writer_id": fed.accessor_id, "declaration_id": fed.field_id,
                "declaration_qualname": fed.field_qualname, "resolution": fed.resolution,
                "writer_path": fed.accessor_path, "declaration_path": fed.field_path,
                "writer_fn_hash": fed.accessor_hash, "declaration_hash": fed.field_hash,
                "writer_qualname": fed.accessor_qualname, "evidence": fed.evidence,
                "language": "java", "declaration_kind": "field",
            })())
    callees_by_caller: dict[str, list[dict]] = {}
    callers_by_callee: dict[str, list[dict]] = {}
    fn_anchor_by_id = {stable_function_claim_id(fn.path, fn.qualname): _anchor(fn.path, fn.line_start, fn.line_end, fn.qualname) for fn in functions}
    fn_anchor_by_id.update({java_node_id(m): _anchor(m.path, m.line_start, m.line_end, m.qualname) for m in java_methods})
    decl_anchor_by_id = {stable_declaration_claim_id(decl.path, decl.qualname): _anchor(decl.path, decl.line_start, decl.line_end, decl.qualname) for decl in declarations}
    decl_anchor_by_id.update({stable_java_node_claim_id(decl.path, decl.qualname, decl.declaration_kind): _anchor(decl.path, decl.line_start, decl.line_end, decl.qualname) for decl in java_fields})
    for edge in edges:
        edge_dict = {"target_id": edge.callee_id, "target_qualname": edge.callee_qualname, "target_path": edge.callee_path, "anchor": fn_anchor_by_id.get(edge.callee_id, _anchor(edge.callee_path, None, None, edge.callee_qualname)), "evidence": edge.evidence, "resolution": edge.resolution}
        callees_by_caller.setdefault(edge.caller_id, []).append(edge_dict)
        callers_by_callee.setdefault(edge.callee_id, []).append({"source_id": edge.caller_id, "source_path": edge.caller_path, "anchor": fn_anchor_by_id.get(edge.caller_id, _anchor(edge.caller_path, None, None, edge.caller_qualname)), "evidence": edge.evidence, "resolution": edge.resolution})
    unresolved_by_caller = {caller: [{"expr": item.expr, "reason": item.reason} for item in items] for caller, items in unresolved.items()}
    for caller, items in unresolved_java_calls.items():
        unresolved_by_caller.setdefault(caller, []).extend({"expr": item.expr, "reason": item.reason} for item in items)
    reads_by_reader: dict[str, list[dict]] = {}
    readers_by_decl: dict[str, list[dict]] = {}
    writes_by_writer: dict[str, list[dict]] = {}
    writers_by_decl: dict[str, list[dict]] = {}
    for edge in read_edges:
        reads_by_reader.setdefault(edge.reader_id, []).append({"target_id": edge.declaration_id, "target_qualname": edge.declaration_qualname, "target_path": edge.declaration_path, "anchor": decl_anchor_by_id.get(edge.declaration_id, _anchor(edge.declaration_path, None, None, edge.declaration_qualname)), "evidence": edge.evidence, "resolution": edge.resolution})
        readers_by_decl.setdefault(edge.declaration_id, []).append({"source_id": edge.reader_id, "source_path": edge.reader_path, "anchor": fn_anchor_by_id.get(edge.reader_id, _anchor(edge.reader_path, None, None, edge.reader_qualname)), "evidence": edge.evidence, "resolution": edge.resolution})
    unresolved_reads_by_reader = {reader: [{"expr": item.expr, "reason": item.reason} for item in items] for reader, items in unresolved_reads.items()}
    for reader, items in unresolved_java_fields.items():
        unresolved_reads_by_reader.setdefault(reader, []).extend({"expr": item.expr, "reason": item.reason} for item in items if item.edge_kind == "reads")
    for edge in write_edges:
        anchor = decl_anchor_by_id.get(edge.declaration_id, _anchor(edge.declaration_path, None, None, edge.declaration_qualname))
        writes_by_writer.setdefault(edge.writer_id, []).append({"target_id": edge.declaration_id, "target_qualname": edge.declaration_qualname, "target_path": edge.declaration_path, "anchor": anchor, "evidence": edge.evidence, "resolution": edge.resolution})
        writers_by_decl.setdefault(edge.declaration_id, []).append({"source_id": edge.writer_id, "source_path": edge.writer_path, "anchor": fn_anchor_by_id.get(edge.writer_id, _anchor(edge.writer_path, None, None, edge.writer_qualname)), "evidence": edge.evidence, "resolution": edge.resolution})
    unresolved_writes_by_writer = {writer: [{"expr": item.expr, "reason": item.reason} for item in items] for writer, items in unresolved_writes.items()}
    for writer, items in unresolved_java_fields.items():
        unresolved_writes_by_writer.setdefault(writer, []).extend({"expr": item.expr, "reason": item.reason} for item in items if item.edge_kind == "writes")
    env_reads_by_reader: dict[str, list[dict]] = {}
    env_readers_by_env: dict[str, list[dict]] = {}
    for edge in env_read_edges:
        env_reads_by_reader.setdefault(edge.reader_id, []).append({"env_id": stable_env_claim_id(edge.env_name), "env_name": edge.env_name, "evidence": edge.evidence, "resolution": edge.resolution})
        env_readers_by_env.setdefault(stable_env_claim_id(edge.env_name), []).append({"source_id": edge.reader_id, "reader_id": edge.reader_id, "source_path": edge.reader_path, "evidence": edge.evidence, "resolution": edge.resolution})
    unresolved_env_reads_by_reader = {reader: [{"expr": item.expr, "reason": item.reason} for item in items] for reader, items in unresolved_env_reads.items()}
    config_reads_by_reader: dict[str, list[dict]] = {}
    config_readers_by_key: dict[str, list[dict]] = {}
    for edge in config_key_read_edges:
        config_reads_by_reader.setdefault(edge.reader_id, []).append({"config_id": edge.config_id, "config_key": edge.config_key, "config_path": edge.config_path, "evidence": edge.evidence, "resolution": edge.resolution})
        config_readers_by_key.setdefault(edge.config_id, []).append({"source_id": edge.reader_id, "reader_id": edge.reader_id, "source_path": edge.reader_path, "evidence": edge.evidence, "resolution": edge.resolution})
    unresolved_config_key_reads_by_reader = {reader: [{"expr": item.expr, "reason": item.reason} for item in items] for reader, items in unresolved_config_key_reads.items()}
    injects_by_source: dict[str, list[dict]] = {}
    injected_by_target: dict[str, list[dict]] = {}
    for edge in java_inject_edges:
        injects_by_source.setdefault(edge.injector_id, []).append({"target_id": edge.bean_id, "target_qualname": edge.bean_qualname, "inject_kind": edge.inject_kind, "evidence": edge.evidence, "confidence": edge.confidence, "resolution": edge.resolution, "tier": "attributed"})
        injected_by_target.setdefault(edge.bean_id, []).append({"source_id": edge.injector_id, "source_path": edge.injector_path, "inject_kind": edge.inject_kind, "evidence": edge.evidence, "confidence": edge.confidence, "resolution": edge.resolution, "tier": "attributed"})
    unresolved_injects_by_source = {src: [{"type": item.type_expr, "reason": item.reason, "inject_kind": item.inject_kind, "candidates": item.candidates or []} for item in items] for src, items in unresolved_java_injects.items()}
    config_properties_by_source = {edge.source_id: {"prefix": edge.prefix, "target_kind": edge.target_kind, "evidence": edge.evidence, "confidence": edge.confidence, "resolution": edge.resolution, "tier": "attributed"} for edge in java_config_properties}
    unresolved_config_properties_by_source = {src: [{"expr": item.expr, "reason": item.reason} for item in items] for src, items in unresolved_java_config_properties.items()}
    topic_pubs_by_source: dict[str, list[dict]] = {}
    topic_subs_by_source: dict[str, list[dict]] = {}
    topic_publishers: dict[str, list[dict]] = {}
    topic_subscribers: dict[str, list[dict]] = {}
    for edge in java_topic_edges:
        entry = {"topic_id": stable_topic_claim_id(edge.topic_name), "topic_name": edge.topic_name, "evidence": edge.evidence, "confidence": edge.confidence, "resolution": edge.resolution, "tier": "attributed"}
        rev = {"source_id": edge.source_id, "source_path": edge.source_path, "evidence": edge.evidence, "confidence": edge.confidence, "resolution": edge.resolution, "tier": "attributed"}
        if edge.edge_kind == "publishes_to":
            topic_pubs_by_source.setdefault(edge.source_id, []).append(entry)
            topic_publishers.setdefault(stable_topic_claim_id(edge.topic_name), []).append(rev)
        elif edge.edge_kind == "subscribes_to":
            topic_subs_by_source.setdefault(edge.source_id, []).append(entry)
            topic_subscribers.setdefault(stable_topic_claim_id(edge.topic_name), []).append(rev)
    unresolved_topics_by_source = {src: [{"expr": item.expr, "reason": item.reason, "edge_kind": item.edge_kind} for item in items] for src, items in unresolved_java_topics.items()}
    unresolved_overrides_by_method = {method: [{"expr": item.expr, "reason": item.reason} for item in items] for method, items in unresolved_java_overrides.items()}
    java_anchor_by_id = {stable_java_node_claim_id(node.path, node.qualname, node.node_kind): _anchor(node.path, node.line_start, node.line_end, node.qualname) for node in java_classes if node.node_kind in {"class", "interface"}}
    inherits_by_child: dict[str, list[dict]] = {}
    subtypes_by_parent: dict[str, list[dict]] = {}
    implementors_by_parent: dict[str, list[dict]] = {}
    overrides_by_method: dict[str, list[dict]] = {}
    overridden_by_target: dict[str, list[dict]] = {}
    uses_type_by_user: dict[str, list[dict]] = {}
    used_by_type: dict[str, list[dict]] = {}
    unresolved_types_by_user = {user: [{"type": item.type_expr, "reason": item.reason, "use_kind": item.use_kind} for item in items] for user, items in unresolved_java_types.items()}
    for edge in java_type_edges:
        entry = {"target_id": edge.type_id, "target_qualname": edge.type_qualname, "target_path": edge.type_path, "use_kind": edge.use_kind, "evidence": edge.evidence, "resolution": edge.resolution}
        uses_type_by_user.setdefault(edge.user_id, []).append(entry)
        used_by_type.setdefault(edge.type_id, []).append({"source_id": edge.user_id, "source_path": edge.user_path, "use_kind": edge.use_kind, "evidence": edge.evidence, "resolution": edge.resolution})
    for edge in java_override_edges:
        target_item = {
            "edge_id": stable_override_edge_claim_id(edge.method_id, edge.overridden_id),
            "target_id": edge.overridden_id,
            "overridden_qualname": edge.overridden_qualname,
            "resolution": edge.resolution,
            "evidence": edge.evidence,
            "anchor": fn_anchor_by_id.get(edge.overridden_id, _anchor(edge.overridden_path, None, None, edge.overridden_qualname)),
        }
        overrides_by_method.setdefault(edge.method_id, []).append(target_item)
        reverse_item = {
            "edge_id": stable_override_edge_claim_id(edge.method_id, edge.overridden_id),
            "source_id": edge.method_id,
            "method_id": edge.method_id,
            "resolution": edge.resolution,
            "evidence": edge.evidence,
            "anchor": fn_anchor_by_id.get(edge.method_id, _anchor(edge.method_path, None, None, edge.method_qualname)),
        }
        overridden_by_target.setdefault(edge.overridden_id, []).append(reverse_item)
    for edge in inherit_edges:
        target_item = {"target_id": edge.parent_id, "target_qualname": edge.parent_qualname, "target_path": edge.parent_path, "relation": edge.relation, "anchor": java_anchor_by_id.get(edge.parent_id, _anchor(edge.parent_path, None, None, edge.parent_qualname)), "evidence": edge.evidence, "resolution": edge.resolution}
        inherits_by_child.setdefault(edge.child_id, []).append(target_item)
        reverse_item = {"source_id": edge.child_id, "source_path": edge.child_path, "relation": edge.relation, "anchor": java_anchor_by_id.get(edge.child_id, _anchor(edge.child_path, None, None, edge.child_qualname)), "evidence": edge.evidence, "resolution": edge.resolution}
        if edge.relation == "implements":
            implementors_by_parent.setdefault(edge.parent_id, []).append(reverse_item)
        else:
            subtypes_by_parent.setdefault(edge.parent_id, []).append(reverse_item)
    unresolved_inherits_by_child = {child: [{"expr": item.expr, "reason": item.reason, "relation": item.relation} for item in items] for child, items in unresolved_inherits.items()}
    for claim in claims:
        if claim.body.get("node_kind") == "topic":
            graph = claim.body.setdefault("graph", {})
            graph["publishers"] = topic_publishers.get(claim.id, [])
            graph["subscribers"] = topic_subscribers.get(claim.id, [])
            graph["topic_coverage"] = "partial"
        if claim.body.get("node_kind") == "env":
            graph = claim.body.setdefault("graph", {})
            graph["read_by"] = env_readers_by_env.get(claim.id, [])
            graph["read_by_coverage"] = "partial"
        if claim.scope == "config":
            graph = claim.body.setdefault("graph", {})
            graph["read_by"] = config_readers_by_key.get(claim.id, [])
            graph["read_by_coverage"] = "partial"
        if claim.scope == "declaration":
            graph = claim.body.setdefault("graph", {})
            graph["read_by"] = readers_by_decl.get(claim.id, [])
            graph["read_by_coverage"] = "partial"
            graph["written_by"] = writers_by_decl.get(claim.id, [])
            graph["written_by_coverage"] = "partial"
        if claim.body.get("language") == "java" and claim.body.get("node_kind") in {"class", "interface", "enum", "field", "constant"}:
            graph = claim.body.setdefault("graph", {})
            graph["inherits"] = inherits_by_child.get(claim.id, [])
            graph["inherits_unresolved"] = unresolved_inherits_by_child.get(claim.id, [])
            graph["inherits_coverage"] = "partial"
            graph["subtypes"] = subtypes_by_parent.get(claim.id, [])
            graph["subtypes_coverage"] = "partial"
            graph["implementors"] = implementors_by_parent.get(claim.id, [])
            graph["implementors_coverage"] = "partial"
            graph["uses_type"] = uses_type_by_user.get(claim.id, [])
            graph["used_by_types"] = used_by_type.get(claim.id, [])
            graph["uses_type_unresolved"] = unresolved_types_by_user.get(claim.id, [])
            graph["uses_type_coverage"] = "partial"
            graph["injects"] = injects_by_source.get(claim.id, [])
            graph["injected_by"] = injected_by_target.get(claim.id, [])
            graph["injects_unresolved"] = unresolved_injects_by_source.get(claim.id, [])
            graph["injects_coverage"] = "partial"
            if claim.id in java_spring_declarations:
                graph["spring_declaration"] = java_spring_declarations[claim.id]
            if claim.id in unresolved_java_spring_declarations:
                graph["spring_declaration_unresolved"] = unresolved_java_spring_declarations[claim.id]
            if claim.id in java_persistence_declarations:
                graph["persistence_declaration"] = java_persistence_declarations[claim.id]
            if claim.id in unresolved_java_persistence_declarations:
                graph["persistence_declaration_unresolved"] = unresolved_java_persistence_declarations[claim.id]
            if claim.id in java_repository_declarations:
                graph["repository_declaration"] = java_repository_declarations[claim.id]
            if claim.id in unresolved_java_repository_declarations:
                graph["repository_declaration_unresolved"] = unresolved_java_repository_declarations[claim.id]
            if claim.id in java_mybatis_declarations:
                graph["mybatis_declaration"] = java_mybatis_declarations[claim.id]
            if claim.id in unresolved_java_mybatis_declarations:
                graph["mybatis_declaration_unresolved"] = unresolved_java_mybatis_declarations[claim.id]
            if claim.id in config_properties_by_source:
                graph["configuration_properties"] = config_properties_by_source[claim.id]
            if claim.id in unresolved_config_properties_by_source:
                graph["configuration_properties_unresolved"] = unresolved_config_properties_by_source[claim.id]
            if claim.id in java_sagas:
                graph["saga_definition"] = java_sagas[claim.id]
                graph["saga_definition_unresolved"] = unresolved_java_sagas.get(claim.id, [])
                graph["saga_coverage"] = "partial"
            elif claim.id in unresolved_java_sagas:
                graph["saga_definition_unresolved"] = unresolved_java_sagas[claim.id]
                graph["saga_coverage"] = "partial"
        if claim.body.get("language") == "java" and claim.body.get("node_kind") in {"method", "constructor"}:
            graph = claim.body.setdefault("graph", {})
            graph["callees"] = callees_by_caller.get(claim.id, [])
            graph["callers"] = callers_by_callee.get(claim.id, [])
            graph["unresolved_calls"] = unresolved_by_caller.get(claim.id, [])
            graph["calls_coverage"] = "partial"
            graph["reads"] = reads_by_reader.get(claim.id, [])
            graph["reads_unresolved"] = unresolved_reads_by_reader.get(claim.id, [])
            graph["writes"] = writes_by_writer.get(claim.id, [])
            graph["writes_unresolved"] = unresolved_writes_by_writer.get(claim.id, [])
            graph["field_access_coverage"] = "partial"
            graph["overrides"] = overrides_by_method.get(claim.id, [])
            graph["overridden_by"] = overridden_by_target.get(claim.id, [])
            graph["overrides_unresolved"] = unresolved_overrides_by_method.get(claim.id, [])
            graph["overrides_coverage"] = "partial"
            graph["uses_type"] = uses_type_by_user.get(claim.id, [])
            graph["used_by_types"] = used_by_type.get(claim.id, [])
            graph["uses_type_unresolved"] = unresolved_types_by_user.get(claim.id, [])
            graph["uses_type_coverage"] = "partial"
            if claim.id in java_spring_declarations:
                graph["spring_declaration"] = java_spring_declarations[claim.id]
            if claim.id in unresolved_java_spring_declarations:
                graph["spring_declaration_unresolved"] = unresolved_java_spring_declarations[claim.id]
            if claim.id in java_persistence_declarations:
                graph["persistence_declaration"] = java_persistence_declarations[claim.id]
            if claim.id in unresolved_java_persistence_declarations:
                graph["persistence_declaration_unresolved"] = unresolved_java_persistence_declarations[claim.id]
            if claim.id in java_repository_declarations:
                graph["repository_declaration"] = java_repository_declarations[claim.id]
            if claim.id in unresolved_java_repository_declarations:
                graph["repository_declaration_unresolved"] = unresolved_java_repository_declarations[claim.id]
            if claim.id in java_mybatis_declarations:
                graph["mybatis_declaration"] = java_mybatis_declarations[claim.id]
            if claim.id in unresolved_java_mybatis_declarations:
                graph["mybatis_declaration_unresolved"] = unresolved_java_mybatis_declarations[claim.id]
            if claim.id in config_properties_by_source:
                graph["configuration_properties"] = config_properties_by_source[claim.id]
            if claim.id in unresolved_config_properties_by_source:
                graph["configuration_properties_unresolved"] = unresolved_config_properties_by_source[claim.id]
            graph["publishes_to"] = topic_pubs_by_source.get(claim.id, [])
            graph["publishes_to_unresolved"] = [x for x in unresolved_topics_by_source.get(claim.id, []) if x.get("edge_kind") == "publishes_to"]
            graph["subscribes_to"] = topic_subs_by_source.get(claim.id, [])
            graph["subscribes_to_unresolved"] = [x for x in unresolved_topics_by_source.get(claim.id, []) if x.get("edge_kind") == "subscribes_to"]
            graph["topic_coverage"] = "partial"

    if use_model:
        model_claims = derive_model_function_claims(repo, functions, model=model)
        model_ids = {claim.id for claim in model_claims}
        for claim in model_claims:
            graph = claim.body.setdefault("graph", {})
            graph["callees"] = callees_by_caller.get(claim.id, [])
            graph["callers"] = callers_by_callee.get(claim.id, [])
            graph["unresolved_calls"] = unresolved_by_caller.get(claim.id, [])
            graph["reads"] = reads_by_reader.get(claim.id, [])
            graph["reads_unresolved"] = unresolved_reads_by_reader.get(claim.id, [])
            graph["writes"] = writes_by_writer.get(claim.id, [])
            graph["writes_unresolved"] = unresolved_writes_by_writer.get(claim.id, [])
            graph["reads_env"] = env_reads_by_reader.get(claim.id, [])
            graph["reads_env_unresolved"] = unresolved_env_reads_by_reader.get(claim.id, [])
            graph["reads_env_coverage"] = "partial"
            graph["reads_config_key"] = config_reads_by_reader.get(claim.id, [])
            graph["reads_config_key_unresolved"] = unresolved_config_key_reads_by_reader.get(claim.id, [])
            graph["reads_config_key_coverage"] = "partial"
            claims.append(claim)
        # Fallback to heuristic for functions the model did not cover.
        for fn in functions:
            graph = {
                "callees": callees_by_caller.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "callers": callers_by_callee.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "unresolved_calls": unresolved_by_caller.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "reads": reads_by_reader.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "reads_unresolved": unresolved_reads_by_reader.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "writes": writes_by_writer.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "writes_unresolved": unresolved_writes_by_writer.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "reads_env": env_reads_by_reader.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "reads_env_unresolved": unresolved_env_reads_by_reader.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "reads_env_coverage": "partial",
                "reads_config_key": config_reads_by_reader.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "reads_config_key_unresolved": unresolved_config_key_reads_by_reader.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "reads_config_key_coverage": "partial",
            }
            claim = derive_function_claim(repo, fn, graph=graph)
            if claim.id not in model_ids:
                claims.append(claim)
            contract = derive_contract_claim(repo, fn, graph=graph)
            if contract is not None:
                claims.append(contract)
    else:
        for fn in functions:
            graph = {
                "callees": callees_by_caller.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "callers": callers_by_callee.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "unresolved_calls": unresolved_by_caller.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "reads": reads_by_reader.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "reads_unresolved": unresolved_reads_by_reader.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "writes": writes_by_writer.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "writes_unresolved": unresolved_writes_by_writer.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "reads_env": env_reads_by_reader.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "reads_env_unresolved": unresolved_env_reads_by_reader.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "reads_env_coverage": "partial",
                "reads_config_key": config_reads_by_reader.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "reads_config_key_unresolved": unresolved_config_key_reads_by_reader.get(stable_function_claim_id(fn.path, fn.qualname), []),
                "reads_config_key_coverage": "partial",
            }
            fn_claim = derive_function_claim(repo, fn, graph=graph)
            claims.append(fn_claim)
            contract = derive_contract_claim(repo, fn, graph=graph)
            if contract is not None:
                claims.append(contract)
    edge_claims = [claim for edge in edges if (claim := derive_call_edge_claim(repo, edge, fn_anchor_by_id)) is not None]
    read_edge_claims = [claim for edge in read_edges if (claim := derive_read_edge_claim(repo, edge, fn_anchor_by_id, decl_anchor_by_id)) is not None]
    write_edge_claims = [claim for edge in write_edges if (claim := derive_write_edge_claim(repo, edge)) is not None]
    inherit_edge_claims = [claim for edge in inherit_edges if (claim := derive_inherit_edge_claim(repo, edge)) is not None]
    java_contract_claims = []
    for node in java_methods:
        node_id = java_node_id(node)
        graph = {
            "writes": writes_by_writer.get(node_id, []),
            "reads": reads_by_reader.get(node_id, []),
            "callees": callees_by_caller.get(node_id, []),
        }
        claim = derive_java_contract_claim(repo, node, graph=graph)
        if claim is not None:
            java_contract_claims.append(claim)
    override_edge_claims = [claim for edge in java_override_edges if (claim := derive_override_edge_claim(repo, edge)) is not None]
    type_use_edge_claims = [claim for edge in java_type_edges if (claim := derive_type_use_edge_claim(repo, edge)) is not None]
    env_read_edge_claims = [claim for edge in env_read_edges if (claim := derive_env_read_edge_claim(repo, edge)) is not None]
    config_key_read_edge_claims = [claim for edge in config_key_read_edges if (claim := derive_config_key_read_edge_claim(repo, edge)) is not None]
    inject_edge_claims = [claim for edge in java_inject_edges if (claim := derive_inject_edge_claim(repo, edge)) is not None]
    configuration_properties_claims = [derive_configuration_properties_claim(repo, edge) for edge in java_config_properties]
    topic_edge_claims = [claim for edge in java_topic_edges if (claim := derive_topic_edge_claim(repo, edge)) is not None]
    cache_declaration_claims = [derive_cache_declaration_claim(repo, item) for item in java_cache_declarations]
    scheduling_declaration_claims = [derive_scheduling_declaration_claim(repo, item) for item in java_scheduling_declarations]
    transaction_declaration_claims = [derive_transaction_declaration_claim(repo, item) for item in java_transaction_declarations]
    async_declaration_claims = [derive_async_declaration_claim(repo, item) for item in java_async_declarations]
    retry_declaration_claims = [derive_retry_declaration_claim(repo, item) for item in java_retry_declarations]
    circuit_breaker_declaration_claims = [derive_circuit_breaker_declaration_claim(repo, item) for item in java_circuit_breaker_declarations]
    rate_limiter_declaration_claims = [derive_rate_limiter_declaration_claim(repo, item) for item in java_rate_limiter_declarations]
    bulkhead_declaration_claims = [derive_bulkhead_declaration_claim(repo, item) for item in java_bulkhead_declarations]
    time_limiter_declaration_claims = [derive_time_limiter_declaration_claim(repo, item) for item in java_time_limiter_declarations]
    pre_authorize_declaration_claims = [derive_pre_authorize_declaration_claim(repo,x) for x in java_pre_authorize_declarations]
    roles_allowed_declaration_claims = [derive_roles_allowed_declaration_claim(repo,x) for x in java_roles_allowed_declarations]
    secured_declaration_claims = [derive_secured_declaration_claim(repo,x) for x in java_secured_declarations]
    post_authorize_declaration_claims = [derive_post_authorize_declaration_claim(repo,x) for x in java_post_authorize_declarations]
    exception_handler_declaration_claims = [derive_exception_handler_declaration_claim(repo,x) for x in java_exception_handler_declarations]
    controller_advice_declaration_claims = [derive_controller_advice_declaration_claim(repo,x) for x in java_controller_advice_declarations]
    pre_filter_declaration_claims = [derive_pre_filter_declaration_claim(repo,x) for x in java_pre_filter_declarations]
    post_filter_declaration_claims = [derive_post_filter_declaration_claim(repo,x) for x in java_post_filter_declarations]
    resilience4j_retry_declaration_claims = [derive_resilience4j_retry_declaration_claim(repo, item) for item in java_resilience4j_retry_declarations]
    for claim in claims:
        saga = claim.body.get("graph", {}).get("saga_definition") if isinstance(claim.body.get("graph"), dict) else None
        if not saga:
            continue
        dependencies = []
        for step in saga.get("steps", []):
            contract = step.get("participant_contract")
            if not contract:
                continue
            dependencies.append(contract["path"])
            dependencies.extend(handler["path"] for handler in contract.get("handlers", []))
        for dependency in sorted(set(dependencies)):
            if dependency == claim.bindings[0].path:
                continue
            claim.bindings.append(Binding(path=dependency, file_blob=repo.blob_sha(dependency), fn_hash=None, commit=repo.head(), qualname=None))
        claim.body["saga_dependency_paths"] = sorted(set(dependencies))
    claims.extend(java_contract_claims)
    claims.extend(edge_claims)
    claims.extend(read_edge_claims)
    claims.extend(write_edge_claims)
    claims.extend(inherit_edge_claims)
    claims.extend(override_edge_claims)
    claims.extend(type_use_edge_claims)
    claims.extend(env_read_edge_claims)
    claims.extend(config_key_read_edge_claims)
    claims.extend(inject_edge_claims)
    claims.extend(configuration_properties_claims)
    claims.extend(topic_edge_claims)
    claims.extend(cache_declaration_claims)
    claims.extend(scheduling_declaration_claims)
    claims.extend(transaction_declaration_claims)
    claims.extend(async_declaration_claims)
    claims.extend(retry_declaration_claims)
    claims.extend(circuit_breaker_declaration_claims)
    claims.extend(rate_limiter_declaration_claims)
    claims.extend(bulkhead_declaration_claims)
    claims.extend(time_limiter_declaration_claims)
    claims.extend(resilience4j_retry_declaration_claims)
    claims.extend(pre_authorize_declaration_claims)
    claims.extend(roles_allowed_declaration_claims)
    claims.extend(secured_declaration_claims)
    claims.extend(post_authorize_declaration_claims)
    claims.extend(exception_handler_declaration_claims)
    claims.extend(controller_advice_declaration_claims)
    claims.extend(pre_filter_declaration_claims)
    claims.extend(post_filter_declaration_claims)
    if unresolved_java_cache:
        claims[0].body["java_cache_unresolved"] = {key: [{"expr": x.expr, "reason": x.reason} for x in value] for key, value in sorted(unresolved_java_cache.items())}
    if unresolved_java_scheduling:
        claims[0].body["java_scheduling_unresolved"] = {key: [{"expr": x.expr, "reason": x.reason} for x in value] for key, value in sorted(unresolved_java_scheduling.items())}
    if unresolved_java_transactions:
        claims[0].body["java_transaction_unresolved"] = {key: [{"expr": x.expr, "reason": x.reason} for x in value] for key, value in sorted(unresolved_java_transactions.items())}
    if unresolved_java_async:
        claims[0].body["java_async_unresolved"] = {key: [{"expr": x.expr, "reason": x.reason} for x in value] for key, value in sorted(unresolved_java_async.items())}
    if unresolved_java_retry:
        claims[0].body["java_retry_unresolved"] = {key: [{"expr": x.expr, "reason": x.reason} for x in value] for key, value in sorted(unresolved_java_retry.items())}
    if unresolved_java_circuit_breaker:
        claims[0].body["java_circuit_breaker_unresolved"] = {key: [{"expr": x.expr, "reason": x.reason} for x in value] for key, value in sorted(unresolved_java_circuit_breaker.items())}
    if unresolved_java_rate_limiter:
        claims[0].body["java_rate_limiter_unresolved"] = {key: [{"expr": x.expr, "reason": x.reason} for x in value] for key, value in sorted(unresolved_java_rate_limiter.items())}
    if unresolved_java_bulkhead:
        claims[0].body["java_bulkhead_unresolved"] = {key: [{"expr": x.expr, "reason": x.reason} for x in value] for key, value in sorted(unresolved_java_bulkhead.items())}
    if unresolved_java_time_limiter:
        claims[0].body["java_time_limiter_unresolved"] = {key: [{"expr": x.expr, "reason": x.reason} for x in value] for key, value in sorted(unresolved_java_time_limiter.items())}
    if unresolved_java_pre_authorize:
        claims[0].body["java_pre_authorize_unresolved"]={k:[{"expr":x.expr,"reason":x.reason} for x in v] for k,v in sorted(unresolved_java_pre_authorize.items())}
    if unresolved_java_roles_allowed:
        claims[0].body["java_roles_allowed_unresolved"]={k:[{"expr":x.expr,"reason":x.reason} for x in v] for k,v in sorted(unresolved_java_roles_allowed.items())}
    if unresolved_java_secured:
        claims[0].body["java_secured_unresolved"]={k:[{"expr":x.expr,"reason":x.reason} for x in v] for k,v in sorted(unresolved_java_secured.items())}
    if unresolved_java_post_authorize:
        claims[0].body["java_post_authorize_unresolved"]={k:[{"expr":x.expr,"reason":x.reason} for x in v] for k,v in sorted(unresolved_java_post_authorize.items())}
    if unresolved_java_exception_handler:
        claims[0].body["java_exception_handler_unresolved"]={k:[{"expr":x.expr,"reason":x.reason} for x in v] for k,v in sorted(unresolved_java_exception_handler.items())}
    if unresolved_java_controller_advice:
        claims[0].body["java_controller_advice_unresolved"]={k:[{"expr":x.expr,"reason":x.reason} for x in v] for k,v in sorted(unresolved_java_controller_advice.items())}
    if unresolved_java_pre_filter:
        claims[0].body["java_pre_filter_unresolved"]={k:[{"expr":x.expr,"reason":x.reason} for x in v] for k,v in sorted(unresolved_java_pre_filter.items())}
    if unresolved_java_post_filter:
        claims[0].body["java_post_filter_unresolved"]={k:[{"expr":x.expr,"reason":x.reason} for x in v] for k,v in sorted(unresolved_java_post_filter.items())}
    if unresolved_java_resilience4j_retry:
        claims[0].body["java_resilience4j_retry_unresolved"] = {key: [{"expr": x.expr, "reason": x.reason} for x in value] for key, value in sorted(unresolved_java_resilience4j_retry.items())}
    if semantic_backend is not None and semantic_overlay_candidates:
        accepted = 0
        rejected = 0
        existing_ids = {claim.id for claim in claims}
        for candidate in semantic_overlay_candidates:
            sanitized = _sanitize_semantic_claim(candidate, existing_ids)
            if sanitized is None:
                rejected += 1
                continue
            claims.append(sanitized)
            existing_ids.add(sanitized.id)
            accepted += 1
        semantic = claims[0].body.setdefault("semantic_extraction", {})
        semantic["accepted_claims"] = accepted
        semantic["rejected_claims"] = rejected
    return claims
