from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from dataclasses import dataclass
from typing import Any

from .extract import ApiNode, ClassNode, DeclarationNode, _identifier_keywords

JAVA_DEGRADE_HINT = (
    "Java extraction requires optional dependencies: tree_sitter and "
    "tree_sitter_java. Install in a venv with `python -m pip install "
    "tree_sitter tree_sitter_java`, then rerun TMF."
)


def _java_exact_simple_annotation_import(source: str, simple_name: str, expected_fqn: str | frozenset[str]) -> bool:
    """Accept one exact non-static import and reject local/simple-name shadowing."""
    imports = re.findall(r"(?m)^\s*import\s+(?!static\b)([A-Za-z_][\w.]*)\s*;", source)
    raw = re.findall(rf"\bimport\s+(?:static\s+)?([^;]*{re.escape(simple_name)}[^;]*)\s*;", source)
    declarations = rf"(?:@interface|class|interface|record|enum)\s+{re.escape(simple_name)}\b"
    expected = frozenset({expected_fqn}) if isinstance(expected_fqn, str) else expected_fqn
    matching = [value for value in imports if value in expected]
    return (
        len(matching) == 1
        and [value for value in imports if value.rsplit('.', 1)[-1] == simple_name] == matching
        and raw == matching
        and re.search(declarations, source) is None
    )


@dataclass(frozen=True)
class JavaExtractionStatus:
    available: bool
    degrade_hint: str | None = None


@dataclass(frozen=True)
class JavaCacheDeclaration:
    method_id: str
    method_qualname: str
    path: str
    operation: str
    cache_names: tuple[str, ...]
    key: str | None
    condition: str | None
    unless: str | None
    line_start: int
    line_end: int
    annotation_hash: str
    method_hash: str
    resolution: str = "spring-cache-exact-import-literal"


@dataclass(frozen=True)
class JavaUnresolvedCacheDeclaration:
    method_id: str
    expr: str
    reason: str


@dataclass(frozen=True)
class JavaSchedulingDeclaration:
    method_id: str
    method_qualname: str
    path: str
    fixed_rate: str | None
    fixed_delay: str | None
    initial_delay: str | None
    cron: str | None
    zone: str | None
    time_unit: str | None
    line_start: int
    line_end: int
    annotation_hash: str
    method_hash: str
    resolution: str = "spring-scheduling-exact-import-literal"


@dataclass(frozen=True)
class JavaUnresolvedSchedulingDeclaration:
    method_id: str
    expr: str
    reason: str


@dataclass(frozen=True)
class JavaTransactionDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    propagation: str | None
    isolation: str | None
    read_only: bool | None
    timeout: str | None
    transaction_manager: str | None
    rollback_for: tuple[str, ...]
    no_rollback_for: tuple[str, ...]
    rollback_for_class_name: tuple[str, ...]
    no_rollback_for_class_name: tuple[str, ...]
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-transactional-exact-import-literal"


@dataclass(frozen=True)
class JavaUnresolvedTransactionDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaAsyncDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    executor_qualifier: str | None
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-async-exact-import-literal"

@dataclass(frozen=True)
class JavaUnresolvedAsyncDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaRetryDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    annotation_kind: str
    path: str
    metadata: dict[str, Any]
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-retry-exact-import-literal"

@dataclass(frozen=True)
class JavaUnresolvedRetryDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaCircuitBreakerDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    name: str
    fallback_method: str | None
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "resilience4j-circuitbreaker-exact-import-literal"

@dataclass(frozen=True)
class JavaUnresolvedCircuitBreakerDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaRateLimiterDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    name: str
    fallback_method: str | None
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "resilience4j-ratelimiter-exact-import-literal"

@dataclass(frozen=True)
class JavaUnresolvedRateLimiterDeclaration:
    owner_id: str
    expr: str
    reason: str


@dataclass(frozen=True)
class JavaBulkheadDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    name: str
    fallback_method: str | None
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "resilience4j-bulkhead-exact-import-literal"

@dataclass(frozen=True)
class JavaUnresolvedBulkheadDeclaration:
    owner_id: str
    expr: str
    reason: str


@dataclass(frozen=True)
class JavaTimeLimiterDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    name: str
    fallback_method: str | None
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "resilience4j-timelimiter-exact-import-literal"

@dataclass(frozen=True)
class JavaUnresolvedTimeLimiterDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaPreAuthorizeDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    expression: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-security-preauthorize-exact-import-literal"

@dataclass(frozen=True)
class JavaUnresolvedPreAuthorizeDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaRolesAllowedDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    roles: tuple[str, ...]
    source_namespace: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "roles-allowed-exact-import-literal"

@dataclass(frozen=True)
class JavaUnresolvedRolesAllowedDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaSecuredDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    roles: tuple[str, ...]
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-security-secured-exact-import-literal"

@dataclass(frozen=True)
class JavaUnresolvedSecuredDeclaration:
    owner_id: str
    expr: str
    reason: str
@dataclass(frozen=True)
class JavaPostAuthorizeDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    expression: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-security-postauthorize-exact-import-literal"

@dataclass(frozen=True)
class JavaUnresolvedPostAuthorizeDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaExceptionHandlerDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    exception_types: tuple[str, ...]
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-web-exceptionhandler-exact-import-class-literal"

@dataclass(frozen=True)
class JavaUnresolvedExceptionHandlerDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaControllerAdviceDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-web-controlleradvice-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedControllerAdviceDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaRestControllerAdviceDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-web-restcontrolleradvice-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedRestControllerAdviceDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaInitBinderDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-web-initbinder-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedInitBinderDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaModelAttributeDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-web-modelattribute-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedModelAttributeDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaResponseStatusDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-web-responsestatus-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedResponseStatusDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaSessionAttributesDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-web-sessionattributes-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedSessionAttributesDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaCrossOriginDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-web-crossorigin-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedCrossOriginDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaRestControllerDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-web-restcontroller-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedRestControllerDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaControllerDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-stereotype-controller-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedControllerDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaServiceDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-stereotype-service-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedServiceDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaComponentDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-stereotype-component-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedComponentDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaRepositoryDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-stereotype-repository-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedRepositoryDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaConfigurationDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-context-configuration-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedConfigurationDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaBeanDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-context-bean-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedBeanDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaPrimaryDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-context-primary-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedPrimaryDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaLazyDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-context-lazy-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedLazyDeclaration:
    owner_id: str
    expr: str
    reason: str


@dataclass(frozen=True)
class JavaPostConstructDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "jakarta-annotation-postconstruct-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedPostConstructDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaAutowiredDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-autowired-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedAutowiredDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaResourceDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "jakarta-annotation-resource-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedResourceDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaSingletonDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "jakarta-inject-singleton-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedSingletonDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaInjectDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "jakarta-inject-inject-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedInjectDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaNamedDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "jakarta-inject-named-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedNamedDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaPreDestroyDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "jakarta-annotation-predestroy-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedPreDestroyDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaScopeDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-context-scope-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedScopeDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaResponseBodyDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-web-responsebody-exact-import-presence"

@dataclass(frozen=True)
class JavaUnresolvedResponseBodyDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaPreFilterDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    expression: str
    filter_target: str | None
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-security-prefilter-exact-import-literal"

@dataclass(frozen=True)
class JavaPostFilterDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    expression: str
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "spring-security-postfilter-exact-import-literal"

@dataclass(frozen=True)
class JavaUnresolvedPostFilterDeclaration:
    owner_id: str
    expr: str
    reason: str

@dataclass(frozen=True)
class JavaUnresolvedPreFilterDeclaration:
    owner_id: str
    expr: str
    reason: str








_SKIP_LEAF_TYPES = {"line_comment", "block_comment"}






























_CLASS_TYPES = {"class_declaration", "interface_declaration", "enum_declaration", "record_declaration", "annotation_type_declaration"}
_METHOD_TYPES = {"method_declaration", "constructor_declaration", "compact_constructor_declaration"}




























_WEBFLUX_FQNS = {
    "RouterFunctions": "org.springframework.web.reactive.function.server.RouterFunctions",
    "RequestPredicates": "org.springframework.web.reactive.function.server.RequestPredicates",
}
_WEBFLUX_VERBS = "GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS"
















































_JAVA_KNOWN_EXTERNAL_TYPES = {"String", "List", "Map", "Set", "Collection", "Optional", "Integer", "Long", "Boolean", "Double", "Float", "Object", "Void"}
















_EXTERNAL_OR_JDK_SIMPLE_TYPES = {
    "Object", "String", "Exception", "RuntimeException", "Throwable", "Error",
    "List", "ArrayList", "LinkedList", "Map", "HashMap", "Set", "HashSet",
    "Comparable", "Comparator", "Iterable", "Collection", "Optional", "Number",
    "Integer", "Long", "Boolean", "Double", "Float", "Short", "Byte", "Character",
}








































































def resolve_java_pre_authorize_declarations(path: str, source: str, classes: list[ClassNode], methods: list[ClassNode]) -> tuple[list[JavaPreAuthorizeDeclaration], dict[str, list[JavaUnresolvedPreAuthorizeDeclaration]]]:
    """Retain direct Spring Security PreAuthorize literals; infer no runtime behavior."""
    if "@PreAuthorize" not in source: return [], {}
    expected = "org.springframework.security.access.prepost.PreAuthorize"
    exact = _java_exact_simple_annotation_import(source, "PreAuthorize", expected)
    _,parser=_language_and_parser();data=source.encode();tree=parser.parse(data);candidates={}
    for item in [*classes,*methods]: candidates.setdefault((item.qualname,item.node_kind),[]).append(item)
    found=[];unresolved={}
    def reject(owner,ann,reason): unresolved.setdefault(owner,[]).append(JavaUnresolvedPreAuthorizeDeclaration(owner,_node_text(data,ann),reason))
    def parse(ann):
        values={};seen=set()
        for arg in _java_annotation_args(ann):
            if arg.type!='element_value_pair':
                if len(_java_annotation_args(ann)) != 1: return None,'pre_authorize_attribute_count'
                value=_java_string_literal_value(data,arg)
                if value is None or not value or '${' in value or '#{' in value:return None,'pre_authorize_value_not_literal_string'
                values['value']=value;continue
            ch=_named_children(arg);kn=_child_by_field(arg,'key') or (ch[0] if ch else None);val=_child_by_field(arg,'value')
            if kn is None or val is None:return None,'pre_authorize_malformed_attribute'
            key=_node_text(data,kn)
            if key not in {'value'}:return None,f'pre_authorize_unsupported_attribute:{key}'
            if key in seen:return None,f'pre_authorize_duplicate_attribute:{key}'
            seen.add(key);value=_java_string_literal_value(data,val)
            if value is None or '${' in value or '#{' in value:return None,f'pre_authorize_{key}_not_literal_string'
            values[key]=value
        if not values.get('value'):return None,'pre_authorize_value_missing_or_empty'
        return values,None
    def walk(node,stack):
        ns=stack;q=None;kind=None
        if node.type in _CLASS_TYPES:
            n=_identifier_from_node(data,node);ns=[*stack,n] if n else stack;q='.'.join(ns);kind='interface' if node.type=='interface_declaration' else ('record' if node.type=='record_declaration' else 'class')
        elif node.type=='method_declaration':q=_method_qualname(data,node,stack);kind='method'
        if q and kind:
            anns=[a for a in _java_annotations(node) if _java_annotation_name(data,a)=='PreAuthorize']
            if anns:
                pool=candidates.get((q,kind),[])
                if len(pool)>1:pool=[x for x in pool if x.class_hash==java_hash_for_node(source,node)]
                owner=java_node_id(pool[0]) if len(pool)==1 else f'unresolved:{path}:{q}:{kind}'
                if not exact:
                    for a in anns:reject(owner,a,'pre_authorize_annotation_not_exact_explicit_import')
                elif len(anns)!=1:
                    for a in anns:reject(owner,a,'pre_authorize_duplicate_annotation')
                elif len(pool)!=1:reject(owner,anns[0],'pre_authorize_owner_ambiguous')
                else:
                    values,reason=parse(anns[0])
                    if reason:reject(owner,anns[0],reason)
                    else:found.append(JavaPreAuthorizeDeclaration(owner,q,kind,path,values['value'],_line_start(anns[0]),_line_end(anns[0]),java_hash_for_node(source,anns[0]),pool[0].class_hash))
        for child in _named_children(node):walk(child,ns)
    walk(tree.root_node,[]);return sorted(found,key=lambda x:x.owner_id),unresolved

def resolve_java_roles_allowed_declarations(path: str, source: str, classes: list[ClassNode], methods: list[ClassNode]) -> tuple[list[JavaRolesAllowedDeclaration], dict[str, list[JavaUnresolvedRolesAllowedDeclaration]]]:
    """Retain direct Jakarta/Javax RolesAllowed literals; infer no authorization semantics."""
    if "@RolesAllowed" not in source: return [], {}
    expected={"jakarta.annotation.security.RolesAllowed":"jakarta","javax.annotation.security.RolesAllowed":"javax"}
    imports=re.findall(r"(?m)^\s*import\s+(?!static\b)([A-Za-z_][\w.]*)\s*;",source)
    raw=re.findall(r"\bimport\s+(?:static\s+)?([^;]*RolesAllowed[^;]*)\s*;",source)
    matches=[x for x in imports if x in expected]
    simple=[x for x in imports if x.rsplit('.',1)[-1]=='RolesAllowed']
    exact=len(matches)==1 and simple==matches and raw==matches and re.search(r"@interface\s+RolesAllowed\b",source) is None
    namespace=expected[matches[0]] if exact else None
    _,parser=_language_and_parser();data=source.encode();tree=parser.parse(data);candidates={}
    for item in [*classes,*methods]:candidates.setdefault((item.qualname,item.node_kind),[]).append(item)
    found=[];unresolved={}
    def reject(owner,ann,reason):unresolved.setdefault(owner,[]).append(JavaUnresolvedRolesAllowedDeclaration(owner,_node_text(data,ann),reason))
    def walk(node,stack):
        ns=stack;q=None;kind=None
        if node.type in _CLASS_TYPES:
            n=_identifier_from_node(data,node);ns=[*stack,n] if n else stack;q='.'.join(ns);kind='interface' if node.type=='interface_declaration' else ('record' if node.type=='record_declaration' else 'class')
        elif node.type=='method_declaration':q=_method_qualname(data,node,stack);kind='method'
        if q and kind:
            anns=[a for a in _java_annotations(node) if _java_annotation_name(data,a)=='RolesAllowed']
            if anns:
                pool=candidates.get((q,kind),[])
                if len(pool)>1:pool=[x for x in pool if x.class_hash==java_hash_for_node(source,node)]
                owner=java_node_id(pool[0]) if len(pool)==1 else f'unresolved:{path}:{q}:{kind}'
                if not exact:
                    for ann in anns:reject(owner,ann,'roles_allowed_annotation_not_exact_explicit_import')
                elif len(anns)!=1:
                    for ann in anns:reject(owner,ann,'roles_allowed_duplicate_annotation')
                elif len(pool)!=1:reject(owner,anns[0],'roles_allowed_owner_ambiguous')
                else:
                    args=_java_annotation_args(anns[0]);roles=_java_literal_string_array(data,args[0]) if len(args)==1 else None
                    if not roles or any(not role or '${' in role or '#{' in role for role in roles):reject(owner,anns[0],'roles_allowed_value_not_literal_string_array')
                    else:found.append(JavaRolesAllowedDeclaration(owner,q,kind,path,tuple(roles),namespace,_line_start(anns[0]),_line_end(anns[0]),java_hash_for_node(source,anns[0]),pool[0].class_hash))
        for child in _named_children(node):walk(child,ns)
    walk(tree.root_node,[]);return sorted(found,key=lambda x:x.owner_id),unresolved

def resolve_java_secured_declarations(path: str, source: str, classes: list[ClassNode], methods: list[ClassNode]) -> tuple[list[JavaSecuredDeclaration], dict[str, list[JavaUnresolvedSecuredDeclaration]]]:
    """Retain direct Spring Security Secured role literals; infer no authorization semantics."""
    if "@Secured" not in source: return [], {}
    expected="org.springframework.security.access.annotation.Secured"
    exact = _java_exact_simple_annotation_import(source, "Secured", expected)
    _,parser=_language_and_parser();data=source.encode();tree=parser.parse(data);candidates={}
    for item in [*classes,*methods]:candidates.setdefault((item.qualname,item.node_kind),[]).append(item)
    found=[];unresolved={}
    def reject(owner,ann,reason):unresolved.setdefault(owner,[]).append(JavaUnresolvedSecuredDeclaration(owner,_node_text(data,ann),reason))
    def walk(node,stack):
        ns=stack;q=None;kind=None
        if node.type in _CLASS_TYPES:
            n=_identifier_from_node(data,node);ns=[*stack,n] if n else stack;q='.'.join(ns);kind='interface' if node.type=='interface_declaration' else ('record' if node.type=='record_declaration' else 'class')
        elif node.type=='method_declaration':q=_method_qualname(data,node,stack);kind='method'
        if q and kind:
            anns=[a for a in _java_annotations(node) if _java_annotation_name(data,a)=='Secured']
            if anns:
                pool=candidates.get((q,kind),[])
                if len(pool)>1:pool=[x for x in pool if x.class_hash==java_hash_for_node(source,node)]
                owner=java_node_id(pool[0]) if len(pool)==1 else f'unresolved:{path}:{q}:{kind}'
                if not exact:
                    for ann in anns:reject(owner,ann,'secured_annotation_not_exact_explicit_import')
                elif len(anns)!=1:
                    for ann in anns:reject(owner,ann,'secured_duplicate_annotation')
                elif len(pool)!=1:reject(owner,anns[0],'secured_owner_ambiguous')
                else:
                    args=_java_annotation_args(anns[0]);roles=_java_literal_string_array(data,args[0]) if len(args)==1 else None
                    if not roles or any(not role or '${' in role or '#{' in role for role in roles):reject(owner,anns[0],'secured_value_not_literal_string_array')
                    else:found.append(JavaSecuredDeclaration(owner,q,kind,path,tuple(roles),_line_start(anns[0]),_line_end(anns[0]),java_hash_for_node(source,anns[0]),pool[0].class_hash))
        for child in _named_children(node):walk(child,ns)
    walk(tree.root_node,[]);return sorted(found,key=lambda x:x.owner_id),unresolved
def resolve_java_post_authorize_declarations(path: str, source: str, classes: list[ClassNode], methods: list[ClassNode]) -> tuple[list[JavaPostAuthorizeDeclaration], dict[str, list[JavaUnresolvedPostAuthorizeDeclaration]]]:
    """Retain direct Spring Security PostAuthorize literals; infer no runtime behavior."""
    if "@PostAuthorize" not in source: return [], {}
    expected = "org.springframework.security.access.prepost.PostAuthorize"
    exact = _java_exact_simple_annotation_import(source, "PostAuthorize", expected)
    _,parser=_language_and_parser();data=source.encode();tree=parser.parse(data);candidates={}
    for item in [*classes,*methods]: candidates.setdefault((item.qualname,item.node_kind),[]).append(item)
    found=[];unresolved={}
    def reject(owner,ann,reason): unresolved.setdefault(owner,[]).append(JavaUnresolvedPostAuthorizeDeclaration(owner,_node_text(data,ann),reason))
    def parse(ann):
        values={};seen=set()
        for arg in _java_annotation_args(ann):
            if arg.type!='element_value_pair':
                if len(_java_annotation_args(ann)) != 1: return None,'post_authorize_attribute_count'
                value=_java_string_literal_value(data,arg)
                if value is None or not value or '${' in value or '#{' in value:return None,'post_authorize_value_not_literal_string'
                values['value']=value;continue
            ch=_named_children(arg);kn=_child_by_field(arg,'key') or (ch[0] if ch else None);val=_child_by_field(arg,'value')
            if kn is None or val is None:return None,'post_authorize_malformed_attribute'
            key=_node_text(data,kn)
            if key not in {'value'}:return None,f'post_authorize_unsupported_attribute:{key}'
            if key in seen:return None,f'post_authorize_duplicate_attribute:{key}'
            seen.add(key);value=_java_string_literal_value(data,val)
            if value is None or '${' in value or '#{' in value:return None,f'post_authorize_{key}_not_literal_string'
            values[key]=value
        if not values.get('value'):return None,'post_authorize_value_missing_or_empty'
        return values,None
    def walk(node,stack):
        ns=stack;q=None;kind=None
        if node.type in _CLASS_TYPES:
            n=_identifier_from_node(data,node);ns=[*stack,n] if n else stack;q='.'.join(ns);kind='interface' if node.type=='interface_declaration' else ('record' if node.type=='record_declaration' else 'class')
        elif node.type=='method_declaration':q=_method_qualname(data,node,stack);kind='method'
        if q and kind:
            anns=[a for a in _java_annotations(node) if _java_annotation_name(data,a)=='PostAuthorize']
            if anns:
                pool=candidates.get((q,kind),[])
                if len(pool)>1:pool=[x for x in pool if x.class_hash==java_hash_for_node(source,node)]
                owner=java_node_id(pool[0]) if len(pool)==1 else f'unresolved:{path}:{q}:{kind}'
                if not exact:
                    for a in anns:reject(owner,a,'post_authorize_annotation_not_exact_explicit_import')
                elif len(anns)!=1:
                    for a in anns:reject(owner,a,'post_authorize_duplicate_annotation')
                elif len(pool)!=1:reject(owner,anns[0],'post_authorize_owner_ambiguous')
                else:
                    values,reason=parse(anns[0])
                    if reason:reject(owner,anns[0],reason)
                    else:found.append(JavaPostAuthorizeDeclaration(owner,q,kind,path,values['value'],_line_start(anns[0]),_line_end(anns[0]),java_hash_for_node(source,anns[0]),pool[0].class_hash))
        for child in _named_children(node):walk(child,ns)
    walk(tree.root_node,[]);return sorted(found,key=lambda x:x.owner_id),unresolved

def resolve_java_exception_handler_declarations(path: str, source: str, classes: list[ClassNode], methods: list[ClassNode]) -> tuple[list[JavaExceptionHandlerDeclaration], dict[str, list[JavaUnresolvedExceptionHandlerDeclaration]]]:
    """Retain direct Spring Web ExceptionHandler class literals; infer no dispatch/runtime behavior."""
    if "@ExceptionHandler" not in source: return [], {}
    expected="org.springframework.web.bind.annotation.ExceptionHandler"
    exact = _java_exact_simple_annotation_import(source, "ExceptionHandler", expected)
    _,parser=_language_and_parser();data=source.encode();tree=parser.parse(data);candidates={}
    for item in methods:candidates.setdefault((item.qualname,item.node_kind),[]).append(item)
    found=[];unresolved={}
    def reject(owner,ann,reason):unresolved.setdefault(owner,[]).append(JavaUnresolvedExceptionHandlerDeclaration(owner,_node_text(data,ann),reason))
    def parse_classes(node):
        nodes=_named_children(node) if node.type=='element_value_array_initializer' else [node]
        vals=tuple(_node_text(data,x).strip()[:-6] for x in nodes if _node_text(data,x).strip().endswith('.class'))
        return vals if len(vals)==len(nodes) and all(re.fullmatch(r'(?:[A-Za-z_$][\w$]*\.)*[A-Za-z_$][\w$]*',x) for x in vals) else None
    def walk(node,stack):
        ns=stack;q=None
        if node.type in _CLASS_TYPES:
            n=_identifier_from_node(data,node);ns=[*stack,n] if n else stack
        elif node.type=='method_declaration':q=_method_qualname(data,node,stack)
        if q:
            anns=[a for a in _java_annotations(node) if _java_annotation_name(data,a)=='ExceptionHandler']
            if anns:
                pool=candidates.get((q,'method'),[])
                if len(pool)>1:pool=[x for x in pool if x.class_hash==java_hash_for_node(source,node)]
                owner=java_node_id(pool[0]) if len(pool)==1 else f'unresolved:{path}:{q}:method'
                if not exact:
                    for a in anns:reject(owner,a,'exception_handler_annotation_not_exact_explicit_import')
                elif len(anns)!=1:
                    for a in anns:reject(owner,a,'exception_handler_duplicate_annotation')
                elif len(pool)!=1:reject(owner,anns[0],'exception_handler_owner_ambiguous')
                else:
                    args=_java_annotation_args(anns[0]);vals=()
                    if len(args)>1:reject(owner,anns[0],'exception_handler_attribute_count')
                    elif args:
                        arg=args[0]
                        if arg.type=='element_value_pair':
                            key=_child_by_field(arg,'key');arg=_child_by_field(arg,'value')
                            if key is None or _node_text(data,key) not in {'value','exception'}:arg=None
                        vals=parse_classes(arg) if arg is not None else None
                        if vals is None:reject(owner,anns[0],'exception_handler_value_not_class_literals')
                    if vals is not None:found.append(JavaExceptionHandlerDeclaration(owner,q,'method',path,tuple(vals),_line_start(anns[0]),_line_end(anns[0]),java_hash_for_node(source,anns[0]),pool[0].class_hash))
        for child in _named_children(node):walk(child,ns)
    walk(tree.root_node,[]);return sorted(found,key=lambda x:x.owner_id),unresolved

def resolve_java_controller_advice_declarations(path: str, source: str, classes: list[ClassNode]) -> tuple[list[JavaControllerAdviceDeclaration], dict[str, list[JavaUnresolvedControllerAdviceDeclaration]]]:
    """Retain direct ControllerAdvice presence; infer no discovery, scope, or runtime behavior."""
    if "@ControllerAdvice" not in source: return [], {}
    expected = "org.springframework.web.bind.annotation.ControllerAdvice"
    exact = _java_exact_simple_annotation_import(source, "ControllerAdvice", expected)
    _, parser = _language_and_parser(); data = source.encode(); tree = parser.parse(data); candidates = {}
    for item in classes: candidates.setdefault((item.qualname, item.node_kind), []).append(item)
    found=[]; unresolved={}
    def reject(owner,ann,reason): unresolved.setdefault(owner,[]).append(JavaUnresolvedControllerAdviceDeclaration(owner,_node_text(data,ann),reason))
    def walk(node,stack,in_method=False):
        ns=stack; q=None; kind=None
        if node.type in _CLASS_TYPES:
            n=_identifier_from_node(data,node); ns=[*stack,n] if n else stack; q='.'.join(ns)
            kind='interface' if node.type=='interface_declaration' else ('record' if node.type=='record_declaration' else 'class')
        if q and kind in {'class','interface'} and not in_method:
            anns=[a for a in _java_annotations(node) if _java_annotation_name(data,a)=='ControllerAdvice']
            if anns:
                pool=candidates.get((q,kind),[])
                if len(pool)>1: pool=[x for x in pool if x.class_hash==java_hash_for_node(source,node)]
                owner=java_node_id(pool[0]) if len(pool)==1 else f'unresolved:{path}:{q}:{kind}'
                if not exact:
                    for a in anns: reject(owner,a,'controller_advice_annotation_not_exact_explicit_import')
                elif len(anns)!=1:
                    for a in anns: reject(owner,a,'controller_advice_duplicate_annotation')
                elif len(pool)!=1: reject(owner,anns[0],'controller_advice_owner_ambiguous')
                elif _java_annotation_args(anns[0]): reject(owner,anns[0],'controller_advice_metadata_unsupported')
                else: found.append(JavaControllerAdviceDeclaration(owner,q,kind,path,_line_start(anns[0]),_line_end(anns[0]),java_hash_for_node(source,anns[0]),pool[0].class_hash))
        for child in _named_children(node): walk(child,ns,in_method or node.type in {'method_declaration','constructor_declaration'})
    walk(tree.root_node,[],False); return sorted(found,key=lambda x:x.owner_id),unresolved
def _resolve_java_presence_declarations(
    path: str,
    source: str,
    classes: list[ClassNode],
    methods: list[ClassNode],
    fields: list[DeclarationNode] | None = None,
    *,
    annotation: str,
    expected_fqn: str | frozenset[str],
    owner_kinds: frozenset[str],
    declaration_type: type,
    unresolved_type: type,
    reason_prefix: str,
    allow_nested_method_owner: bool = False,
    reject_static_owner: bool = False,
    reject_anonymous_owner: bool = False,
    resolution_by_fqn: dict[str, str] | None = None,
) -> tuple[list[Any], dict[str, list[Any]]]:
    """Shared fail-closed resolver for direct, metadata-free annotation presence."""
    if f"@{annotation}" not in source:
        return [], {}
    exact = _java_exact_simple_annotation_import(source, annotation, expected_fqn)
    _, parser = _language_and_parser()
    data = source.encode()
    tree = parser.parse(data)
    candidates: dict[tuple[str, str], list[ClassNode]] = {}
    for item in [*classes, *methods, *(fields or [])]:
        kind = item.declaration_kind if isinstance(item, DeclarationNode) else item.node_kind
        candidates.setdefault((item.qualname, kind), []).append(item)
    found: list[Any] = []
    unresolved: dict[str, list[Any]] = {}

    def reject(owner: str, ann: Any, reason: str) -> None:
        unresolved.setdefault(owner, []).append(unresolved_type(owner, _node_text(data, ann), reason))

    def walk(node: Any, stack: list[str], in_method: bool = False, in_anonymous_class: bool = False) -> None:
        next_stack = stack
        qualname = None
        kind = None
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(data, node)
            next_stack = [*stack, name] if name else stack
            qualname = ".".join(next_stack)
            kind = "interface" if node.type == "interface_declaration" else ("record" if node.type == "record_declaration" else "class")
        elif node.type in {"method_declaration", "constructor_declaration"}:
            qualname = _method_qualname(data, node, stack)
            kind = "method" if node.type == "method_declaration" else "constructor"
        elif node.type in {"field_declaration", "constant_declaration"}:
            field_qualnames = _field_qualnames(data, node, stack)
            if len(field_qualnames) == 1:
                qualname = field_qualnames[0]
                simple = qualname.rsplit(".", 1)[-1]
                kind = "constant" if node.type == "constant_declaration" or simple in set(_constants_from_field_declaration(data, node)) else "field"
            elif any(_java_annotation_name(data, ann) == annotation for ann in _java_annotations(node)):
                for ann in _java_annotations(node):
                    if _java_annotation_name(data, ann) == annotation:
                        reject(f"unresolved:{path}:{'.'.join(stack)}:field", ann, f"{reason_prefix}_multi_declarator_owner_unsupported")
        anonymous_owner_unsupported = reject_anonymous_owner and in_anonymous_class
        if qualname and kind in owner_kinds and not in_method and not anonymous_owner_unsupported or (qualname and kind == "method" and kind in owner_kinds and allow_nested_method_owner and not anonymous_owner_unsupported):
            annotations = [ann for ann in _java_annotations(node) if _java_annotation_name(data, ann) == annotation]
            pool = candidates.get((qualname, kind), [])
            if len(pool) > 1:
                node_hash = java_hash_for_node(source, node)
                pool = [
                    item for item in pool
                    if (item.declaration_hash if isinstance(item, DeclarationNode) else item.class_hash) == node_hash
                ]
            owner = java_node_id(pool[0]) if len(pool) == 1 else f"unresolved:{path}:{qualname}:{kind}"
            for ann in annotations:
                if not exact:
                    reject(owner, ann, f"{reason_prefix}_annotation_not_exact_explicit_import")
                elif len(annotations) != 1:
                    reject(owner, ann, f"{reason_prefix}_duplicate_annotation")
                elif len(pool) != 1:
                    reject(owner, ann, f"{reason_prefix}_owner_ambiguous")
                elif reject_static_owner and any(
                    child.type == "static"
                    for modifiers in _named_children(node)
                    if modifiers.type == "modifiers"
                    for child in modifiers.children
                ):
                    reject(owner, ann, f"{reason_prefix}_static_owner_unsupported")
                elif _java_annotation_args(ann):
                    reject(owner, ann, f"{reason_prefix}_metadata_unsupported")
                else:
                    owner_hash = pool[0].declaration_hash if isinstance(pool[0], DeclarationNode) else pool[0].class_hash
                    args = (owner, qualname, kind, path, _line_start(ann), _line_end(ann), java_hash_for_node(source, ann), owner_hash)
                    if resolution_by_fqn is None:
                        found.append(declaration_type(*args))
                    else:
                        imported = _java_explicit_imports(source).get(annotation)
                        found.append(declaration_type(*args, resolution_by_fqn[imported]))
        nested_method = in_method or node.type in {"method_declaration", "constructor_declaration"}
        nested_anonymous_class = in_anonymous_class or node.type == "object_creation_expression"
        for child in _named_children(node):
            walk(child, next_stack, nested_method, nested_anonymous_class)

    walk(tree.root_node, [])
    return sorted(found, key=lambda item: item.owner_id), unresolved


def resolve_java_rest_controller_advice_declarations(path: str, source: str, classes: list[ClassNode]) -> tuple[list[JavaRestControllerAdviceDeclaration], dict[str, list[JavaUnresolvedRestControllerAdviceDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, classes, [], annotation="RestControllerAdvice", expected_fqn="org.springframework.web.bind.annotation.RestControllerAdvice", owner_kinds=frozenset({"class", "interface"}), declaration_type=JavaRestControllerAdviceDeclaration, unresolved_type=JavaUnresolvedRestControllerAdviceDeclaration, reason_prefix="rest_controller_advice")


def resolve_java_init_binder_declarations(path: str, source: str, methods: list[ClassNode]) -> tuple[list[JavaInitBinderDeclaration], dict[str, list[JavaUnresolvedInitBinderDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, [], methods, annotation="InitBinder", expected_fqn="org.springframework.web.bind.annotation.InitBinder", owner_kinds=frozenset({"method"}), declaration_type=JavaInitBinderDeclaration, unresolved_type=JavaUnresolvedInitBinderDeclaration, reason_prefix="init_binder", allow_nested_method_owner=True)


def resolve_java_model_attribute_declarations(path: str, source: str, methods: list[ClassNode]) -> tuple[list[JavaModelAttributeDeclaration], dict[str, list[JavaUnresolvedModelAttributeDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, [], methods, annotation="ModelAttribute", expected_fqn="org.springframework.web.bind.annotation.ModelAttribute", owner_kinds=frozenset({"method"}), declaration_type=JavaModelAttributeDeclaration, unresolved_type=JavaUnresolvedModelAttributeDeclaration, reason_prefix="model_attribute", allow_nested_method_owner=True)


def resolve_java_response_status_declarations(path: str, source: str, classes: list[ClassNode], methods: list[ClassNode]) -> tuple[list[JavaResponseStatusDeclaration], dict[str, list[JavaUnresolvedResponseStatusDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, classes, methods, annotation="ResponseStatus", expected_fqn="org.springframework.web.bind.annotation.ResponseStatus", owner_kinds=frozenset({"class", "interface", "method"}), declaration_type=JavaResponseStatusDeclaration, unresolved_type=JavaUnresolvedResponseStatusDeclaration, reason_prefix="response_status", allow_nested_method_owner=True)


def resolve_java_session_attributes_declarations(path: str, source: str, classes: list[ClassNode]) -> tuple[list[JavaSessionAttributesDeclaration], dict[str, list[JavaUnresolvedSessionAttributesDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, classes, [], annotation="SessionAttributes", expected_fqn="org.springframework.web.bind.annotation.SessionAttributes", owner_kinds=frozenset({"class", "interface"}), declaration_type=JavaSessionAttributesDeclaration, unresolved_type=JavaUnresolvedSessionAttributesDeclaration, reason_prefix="session_attributes")


def resolve_java_cross_origin_declarations(path: str, source: str, classes: list[ClassNode], methods: list[ClassNode]) -> tuple[list[JavaCrossOriginDeclaration], dict[str, list[JavaUnresolvedCrossOriginDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, classes, methods, annotation="CrossOrigin", expected_fqn="org.springframework.web.bind.annotation.CrossOrigin", owner_kinds=frozenset({"class", "interface", "method"}), declaration_type=JavaCrossOriginDeclaration, unresolved_type=JavaUnresolvedCrossOriginDeclaration, reason_prefix="cross_origin", allow_nested_method_owner=True)


def resolve_java_rest_controller_declarations(path: str, source: str, classes: list[ClassNode]) -> tuple[list[JavaRestControllerDeclaration], dict[str, list[JavaUnresolvedRestControllerDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, classes, [], annotation="RestController", expected_fqn="org.springframework.web.bind.annotation.RestController", owner_kinds=frozenset({"class", "interface"}), declaration_type=JavaRestControllerDeclaration, unresolved_type=JavaUnresolvedRestControllerDeclaration, reason_prefix="rest_controller")


def resolve_java_controller_declarations(path: str, source: str, classes: list[ClassNode]) -> tuple[list[JavaControllerDeclaration], dict[str, list[JavaUnresolvedControllerDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, classes, [], annotation="Controller", expected_fqn="org.springframework.stereotype.Controller", owner_kinds=frozenset({"class", "interface"}), declaration_type=JavaControllerDeclaration, unresolved_type=JavaUnresolvedControllerDeclaration, reason_prefix="controller")


def resolve_java_service_declarations(path: str, source: str, classes: list[ClassNode]) -> tuple[list[JavaServiceDeclaration], dict[str, list[JavaUnresolvedServiceDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, classes, [], annotation="Service", expected_fqn="org.springframework.stereotype.Service", owner_kinds=frozenset({"class", "interface"}), declaration_type=JavaServiceDeclaration, unresolved_type=JavaUnresolvedServiceDeclaration, reason_prefix="service")


def resolve_java_component_declarations(path: str, source: str, classes: list[ClassNode]) -> tuple[list[JavaComponentDeclaration], dict[str, list[JavaUnresolvedComponentDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, classes, [], annotation="Component", expected_fqn="org.springframework.stereotype.Component", owner_kinds=frozenset({"class", "interface"}), declaration_type=JavaComponentDeclaration, unresolved_type=JavaUnresolvedComponentDeclaration, reason_prefix="component")


def resolve_java_repository_stereotype_declarations(path: str, source: str, classes: list[ClassNode]) -> tuple[list[JavaRepositoryDeclaration], dict[str, list[JavaUnresolvedRepositoryDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, classes, [], annotation="Repository", expected_fqn="org.springframework.stereotype.Repository", owner_kinds=frozenset({"class", "interface"}), declaration_type=JavaRepositoryDeclaration, unresolved_type=JavaUnresolvedRepositoryDeclaration, reason_prefix="repository")


def resolve_java_configuration_declarations(path: str, source: str, classes: list[ClassNode]) -> tuple[list[JavaConfigurationDeclaration], dict[str, list[JavaUnresolvedConfigurationDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, classes, [], annotation="Configuration", expected_fqn="org.springframework.context.annotation.Configuration", owner_kinds=frozenset({"class", "interface"}), declaration_type=JavaConfigurationDeclaration, unresolved_type=JavaUnresolvedConfigurationDeclaration, reason_prefix="configuration")


def resolve_java_bean_declarations(path: str, source: str, methods: list[ClassNode]) -> tuple[list[JavaBeanDeclaration], dict[str, list[JavaUnresolvedBeanDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, [], methods, annotation="Bean", expected_fqn="org.springframework.context.annotation.Bean", owner_kinds=frozenset({"method"}), declaration_type=JavaBeanDeclaration, unresolved_type=JavaUnresolvedBeanDeclaration, reason_prefix="bean")


def resolve_java_primary_declarations(path: str, source: str, classes: list[ClassNode], methods: list[ClassNode]) -> tuple[list[JavaPrimaryDeclaration], dict[str, list[JavaUnresolvedPrimaryDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, classes, methods, annotation="Primary", expected_fqn="org.springframework.context.annotation.Primary", owner_kinds=frozenset({"class", "interface", "method"}), declaration_type=JavaPrimaryDeclaration, unresolved_type=JavaUnresolvedPrimaryDeclaration, reason_prefix="primary")


def resolve_java_lazy_declarations(path: str, source: str, classes: list[ClassNode], methods: list[ClassNode]) -> tuple[list[JavaLazyDeclaration], dict[str, list[JavaUnresolvedLazyDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, classes, methods, annotation="Lazy", expected_fqn="org.springframework.context.annotation.Lazy", owner_kinds=frozenset({"class", "interface", "method"}), declaration_type=JavaLazyDeclaration, unresolved_type=JavaUnresolvedLazyDeclaration, reason_prefix="lazy")


def resolve_java_post_construct_declarations(path: str, source: str, methods: list[ClassNode]) -> tuple[list[JavaPostConstructDeclaration], dict[str, list[JavaUnresolvedPostConstructDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, [], methods, annotation="PostConstruct", expected_fqn="jakarta.annotation.PostConstruct", owner_kinds=frozenset({"method"}), declaration_type=JavaPostConstructDeclaration, unresolved_type=JavaUnresolvedPostConstructDeclaration, reason_prefix="post_construct")

def resolve_java_autowired_declarations(path: str, source: str, methods: list[ClassNode], fields: list[DeclarationNode]) -> tuple[list[JavaAutowiredDeclaration], dict[str, list[JavaUnresolvedAutowiredDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, [], methods, fields, annotation="Autowired", expected_fqn="org.springframework.beans.factory.annotation.Autowired", owner_kinds=frozenset({"constructor", "method", "field"}), declaration_type=JavaAutowiredDeclaration, unresolved_type=JavaUnresolvedAutowiredDeclaration, reason_prefix="autowired", reject_static_owner=True, reject_anonymous_owner=True)

def resolve_java_resource_declarations(path: str, source: str, classes: list[ClassNode], methods: list[ClassNode], fields: list[DeclarationNode]) -> tuple[list[JavaResourceDeclaration], dict[str, list[JavaUnresolvedResourceDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, classes, methods, fields, annotation="Resource", expected_fqn=frozenset({"jakarta.annotation.Resource", "javax.annotation.Resource"}), owner_kinds=frozenset({"class", "method", "field"}), declaration_type=JavaResourceDeclaration, unresolved_type=JavaUnresolvedResourceDeclaration, reason_prefix="resource", reject_static_owner=True, reject_anonymous_owner=True, resolution_by_fqn={"jakarta.annotation.Resource":"jakarta-annotation-resource-exact-import-presence","javax.annotation.Resource":"javax-annotation-resource-exact-import-presence"})

def resolve_java_singleton_declarations(path: str, source: str, classes: list[ClassNode]) -> tuple[list[JavaSingletonDeclaration], dict[str, list[JavaUnresolvedSingletonDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, classes, [], annotation="Singleton", expected_fqn=frozenset({"jakarta.inject.Singleton", "javax.inject.Singleton"}), owner_kinds=frozenset({"class"}), declaration_type=JavaSingletonDeclaration, unresolved_type=JavaUnresolvedSingletonDeclaration, reason_prefix="singleton", resolution_by_fqn={"jakarta.inject.Singleton":"jakarta-inject-singleton-exact-import-presence","javax.inject.Singleton":"javax-inject-singleton-exact-import-presence"})

def resolve_java_inject_declarations(path: str, source: str, methods: list[ClassNode], fields: list[DeclarationNode]) -> tuple[list[JavaInjectDeclaration], dict[str, list[JavaUnresolvedInjectDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, [], methods, fields, annotation="Inject", expected_fqn=frozenset({"jakarta.inject.Inject", "javax.inject.Inject"}), owner_kinds=frozenset({"constructor", "method", "field"}), declaration_type=JavaInjectDeclaration, unresolved_type=JavaUnresolvedInjectDeclaration, reason_prefix="inject", reject_static_owner=True, reject_anonymous_owner=True, resolution_by_fqn={"jakarta.inject.Inject":"jakarta-inject-inject-exact-import-presence","javax.inject.Inject":"javax-inject-inject-exact-import-presence"})

def resolve_java_named_declarations(path: str, source: str, classes: list[ClassNode], methods: list[ClassNode], fields: list[DeclarationNode]) -> tuple[list[JavaNamedDeclaration], dict[str, list[JavaUnresolvedNamedDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, classes, methods, fields, annotation="Named", expected_fqn=frozenset({"jakarta.inject.Named", "javax.inject.Named"}), owner_kinds=frozenset({"class", "method", "field"}), declaration_type=JavaNamedDeclaration, unresolved_type=JavaUnresolvedNamedDeclaration, reason_prefix="named", reject_anonymous_owner=True, resolution_by_fqn={"jakarta.inject.Named":"jakarta-inject-named-exact-import-presence","javax.inject.Named":"javax-inject-named-exact-import-presence"})

def resolve_java_pre_destroy_declarations(path: str, source: str, methods: list[ClassNode]) -> tuple[list[JavaPreDestroyDeclaration], dict[str, list[JavaUnresolvedPreDestroyDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, [], methods, annotation="PreDestroy", expected_fqn="jakarta.annotation.PreDestroy", owner_kinds=frozenset({"method"}), declaration_type=JavaPreDestroyDeclaration, unresolved_type=JavaUnresolvedPreDestroyDeclaration, reason_prefix="pre_destroy")


def resolve_java_scope_declarations(path: str, source: str, classes: list[ClassNode], methods: list[ClassNode]) -> tuple[list[JavaScopeDeclaration], dict[str, list[JavaUnresolvedScopeDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, classes, methods, annotation="Scope", expected_fqn="org.springframework.context.annotation.Scope", owner_kinds=frozenset({"class", "interface", "method"}), declaration_type=JavaScopeDeclaration, unresolved_type=JavaUnresolvedScopeDeclaration, reason_prefix="scope")


def resolve_java_response_body_declarations(path: str, source: str, classes: list[ClassNode], methods: list[ClassNode]) -> tuple[list[JavaResponseBodyDeclaration], dict[str, list[JavaUnresolvedResponseBodyDeclaration]]]:
    return _resolve_java_presence_declarations(path, source, classes, methods, annotation="ResponseBody", expected_fqn="org.springframework.web.bind.annotation.ResponseBody", owner_kinds=frozenset({"class", "interface", "method"}), declaration_type=JavaResponseBodyDeclaration, unresolved_type=JavaUnresolvedResponseBodyDeclaration, reason_prefix="response_body", allow_nested_method_owner=True)


def resolve_java_pre_filter_declarations(path: str, source: str, classes: list[ClassNode], methods: list[ClassNode]) -> tuple[list[JavaPreFilterDeclaration], dict[str, list[JavaUnresolvedPreFilterDeclaration]]]:
    """Retain direct Spring Security PreFilter literals; infer no runtime behavior."""
    if "@PreFilter" not in source: return [], {}
    expected = "org.springframework.security.access.prepost.PreFilter"
    exact = _java_exact_simple_annotation_import(source, "PreFilter", expected)
    _,parser=_language_and_parser();data=source.encode();tree=parser.parse(data);candidates={}
    for item in [*classes,*methods]: candidates.setdefault((item.qualname,item.node_kind),[]).append(item)
    found=[];unresolved={}
    def reject(owner,ann,reason): unresolved.setdefault(owner,[]).append(JavaUnresolvedPreFilterDeclaration(owner,_node_text(data,ann),reason))
    def parse(ann):
        values={};seen=set()
        for arg in _java_annotation_args(ann):
            if arg.type!='element_value_pair':
                if len(_java_annotation_args(ann)) != 1: return None,'pre_filter_attribute_count'
                value=_java_string_literal_value(data,arg)
                if value is None or not value or '${' in value or '#{' in value:return None,'pre_filter_value_not_literal_string'
                values['value']=value;continue
            ch=_named_children(arg);kn=_child_by_field(arg,'key') or (ch[0] if ch else None);val=_child_by_field(arg,'value')
            if kn is None or val is None:return None,'pre_filter_malformed_attribute'
            key=_node_text(data,kn)
            if key not in {'value','filterTarget'}:return None,f'pre_filter_unsupported_attribute:{key}'
            if key in seen:return None,f'pre_filter_duplicate_attribute:{key}'
            seen.add(key);value=_java_string_literal_value(data,val)
            if value is None or '${' in value or '#{' in value:return None,f'pre_filter_{key}_not_literal_string'
            values[key]=value
        if not values.get('value'):return None,'pre_filter_value_missing_or_empty'
        return values,None
    def walk(node,stack):
        ns=stack;q=None;kind=None
        if node.type in _CLASS_TYPES:
            n=_identifier_from_node(data,node);ns=[*stack,n] if n else stack;q='.'.join(ns);kind='interface' if node.type=='interface_declaration' else ('record' if node.type=='record_declaration' else 'class')
        elif node.type=='method_declaration':q=_method_qualname(data,node,stack);kind='method'
        if q and kind:
            anns=[a for a in _java_annotations(node) if _java_annotation_name(data,a)=='PreFilter']
            if anns:
                pool=candidates.get((q,kind),[])
                if len(pool)>1:pool=[x for x in pool if x.class_hash==java_hash_for_node(source,node)]
                owner=java_node_id(pool[0]) if len(pool)==1 else f'unresolved:{path}:{q}:{kind}'
                if not exact:
                    for a in anns:reject(owner,a,'pre_filter_annotation_not_exact_explicit_import')
                elif len(anns)!=1:
                    for a in anns:reject(owner,a,'pre_filter_duplicate_annotation')
                elif len(pool)!=1:reject(owner,anns[0],'pre_filter_owner_ambiguous')
                else:
                    values,reason=parse(anns[0])
                    if reason:reject(owner,anns[0],reason)
                    elif kind!='method':reject(owner,anns[0],'pre_filter_target_not_method')
                    else:found.append(JavaPreFilterDeclaration(owner,q,kind,path,values['value'],values.get('filterTarget'),_line_start(anns[0]),_line_end(anns[0]),java_hash_for_node(source,anns[0]),pool[0].class_hash))
        for child in _named_children(node):walk(child,ns)
    walk(tree.root_node,[]);return sorted(found,key=lambda x:x.owner_id),unresolved
def resolve_java_post_filter_declarations(path: str, source: str, classes: list[ClassNode], methods: list[ClassNode]) -> tuple[list[JavaPostFilterDeclaration], dict[str, list[JavaUnresolvedPostFilterDeclaration]]]:
    """Retain direct Spring Security PostFilter literals; infer no runtime behavior."""
    if "@PostFilter" not in source: return [], {}
    expected = "org.springframework.security.access.prepost.PostFilter"
    exact = _java_exact_simple_annotation_import(source, "PostFilter", expected)
    _,parser=_language_and_parser();data=source.encode();tree=parser.parse(data);candidates={}
    for item in [*classes,*methods]: candidates.setdefault((item.qualname,item.node_kind),[]).append(item)
    found=[];unresolved={}
    def reject(owner,ann,reason): unresolved.setdefault(owner,[]).append(JavaUnresolvedPostFilterDeclaration(owner,_node_text(data,ann),reason))
    def parse(ann):
        values={};seen=set()
        for arg in _java_annotation_args(ann):
            if arg.type!='element_value_pair':
                if len(_java_annotation_args(ann)) != 1: return None,'post_filter_attribute_count'
                value=_java_string_literal_value(data,arg)
                if value is None or not value or '${' in value or '#{' in value:return None,'post_filter_value_not_literal_string'
                values['value']=value;continue
            ch=_named_children(arg);kn=_child_by_field(arg,'key') or (ch[0] if ch else None);val=_child_by_field(arg,'value')
            if kn is None or val is None:return None,'post_filter_malformed_attribute'
            key=_node_text(data,kn)
            if key not in {'value'}:return None,f'post_filter_unsupported_attribute:{key}'
            if key in seen:return None,f'post_filter_duplicate_attribute:{key}'
            seen.add(key);value=_java_string_literal_value(data,val)
            if value is None or '${' in value or '#{' in value:return None,f'post_filter_{key}_not_literal_string'
            values[key]=value
        if not values.get('value'):return None,'post_filter_value_missing_or_empty'
        return values,None
    def walk(node,stack):
        ns=stack;q=None;kind=None
        if node.type in _CLASS_TYPES:
            n=_identifier_from_node(data,node);ns=[*stack,n] if n else stack;q='.'.join(ns);kind='interface' if node.type=='interface_declaration' else ('record' if node.type=='record_declaration' else 'class')
        elif node.type=='method_declaration':q=_method_qualname(data,node,stack);kind='method'
        if q and kind:
            anns=[a for a in _java_annotations(node) if _java_annotation_name(data,a)=='PostFilter']
            if anns:
                pool=candidates.get((q,kind),[])
                if len(pool)>1:pool=[x for x in pool if x.class_hash==java_hash_for_node(source,node)]
                owner=java_node_id(pool[0]) if len(pool)==1 else f'unresolved:{path}:{q}:{kind}'
                if not exact:
                    for a in anns:reject(owner,a,'post_filter_annotation_not_exact_explicit_import')
                elif len(anns)!=1:
                    for a in anns:reject(owner,a,'post_filter_duplicate_annotation')
                elif len(pool)!=1:reject(owner,anns[0],'post_filter_owner_ambiguous')
                else:
                    values,reason=parse(anns[0])
                    if reason:reject(owner,anns[0],reason)
                    elif kind!='method':reject(owner,anns[0],'post_filter_target_not_method')
                    else:found.append(JavaPostFilterDeclaration(owner,q,kind,path,values['value'],_line_start(anns[0]),_line_end(anns[0]),java_hash_for_node(source,anns[0]),pool[0].class_hash))
        for child in _named_children(node):walk(child,ns)
    walk(tree.root_node,[]);return sorted(found,key=lambda x:x.owner_id),unresolved

@dataclass(frozen=True)
class JavaResilience4jRetryDeclaration:
    owner_id: str
    owner_qualname: str
    owner_kind: str
    path: str
    name: str
    fallback_method: str | None
    line_start: int
    line_end: int
    annotation_hash: str
    owner_hash: str
    resolution: str = "resilience4j-retry-exact-import-literal"

@dataclass(frozen=True)
class JavaUnresolvedResilience4jRetryDeclaration:
    owner_id: str
    expr: str
    reason: str


@lru_cache(maxsize=1)
def _java_available() -> bool:
    try:
        _language_and_parser()
        return True
    except Exception:
        return False


def java_status() -> JavaExtractionStatus:
    available = _java_available()
    return JavaExtractionStatus(available=available, degrade_hint=None if available else JAVA_DEGRADE_HINT)


def _language_and_parser():
    # Lazy imports keep Python core at zero hard dependency.
    from tree_sitter import Language, Parser  # type: ignore
    import tree_sitter_java  # type: ignore

    language_obj = tree_sitter_java.language()
    try:
        language = Language(language_obj)
    except TypeError:  # older bindings may already return a Language
        language = language_obj
    parser = Parser()
    if hasattr(parser, "set_language"):
        parser.set_language(language)
    else:
        parser.language = language
    return language, parser


_SKIP_LEAF_TYPES = {"line_comment", "block_comment"}


def _is_named_type(node: Any, type_name: str) -> bool:
    return getattr(node, "type", None) == type_name


def _children(node: Any) -> list[Any]:
    return list(getattr(node, "children", []) or [])


def _named_children(node: Any) -> list[Any]:
    return list(getattr(node, "named_children", []) or [])


def _child_by_field(node: Any, field: str) -> Any | None:
    getter = getattr(node, "child_by_field_name", None)
    if getter is None:
        return None
    return getter(field)


def _node_text(source_bytes: bytes, node: Any) -> str:
    return source_bytes[int(node.start_byte): int(node.end_byte)].decode("utf-8", errors="replace")


def _line_start(node: Any) -> int:
    return int(node.start_point[0]) + 1


def _line_end(node: Any) -> int:
    return int(node.end_point[0]) + 1


def _leaf_token_items(source_bytes: bytes, node: Any) -> list[str]:
    items: list[str] = []

    def walk(cur: Any) -> None:
        if cur.type in _SKIP_LEAF_TYPES:
            return
        children = _children(cur)
        if not children:
            text = _node_text(source_bytes, cur)
            if text.strip():
                items.append(f"{cur.type}:{text}")
            return
        for child in children:
            walk(child)

    walk(node)
    return items


def java_hash_for_node(source: str, node: Any) -> str:
    source_bytes = source.encode("utf-8")
    token_stream = "\0".join(_leaf_token_items(source_bytes, node))
    return hashlib.sha256(token_stream.encode("utf-8")).hexdigest()


def _find_descendant(node: Any, type_name: str) -> Any | None:
    if node.type == type_name:
        return node
    for child in _named_children(node):
        found = _find_descendant(child, type_name)
        if found is not None:
            return found
    return None


def _identifier_from_node(source_bytes: bytes, node: Any) -> str | None:
    name = _child_by_field(node, "name")
    if name is not None:
        return _node_text(source_bytes, name)
    for child in _named_children(node):
        if child.type == "identifier":
            return _node_text(source_bytes, child)
    return None


def _constants_from_field_declaration(source_bytes: bytes, field_node: Any) -> list[str]:
    names: list[str] = []

    def walk(cur: Any) -> None:
        if cur.type == "variable_declarator":
            name_node = _child_by_field(cur, "name")
            if name_node is not None:
                name = _node_text(source_bytes, name_node)
                if name.isupper():
                    names.append(name)
            return
        for child in _named_children(cur):
            walk(child)

    walk(field_node)
    return names


def _field_qualnames(source_bytes: bytes, field_node: Any, container_stack: list[str]) -> list[str]:
    names: list[str] = []

    def walk(cur: Any) -> None:
        if cur.type == "variable_declarator":
            name_node = _child_by_field(cur, "name")
            if name_node is not None:
                names.append(".".join([*container_stack, _node_text(source_bytes, name_node)]))
            return
        for child in _named_children(cur):
            walk(child)

    walk(field_node)
    return names


def _method_qualname(source_bytes: bytes, method_node: Any, container_stack: list[str]) -> str | None:
    name = _identifier_from_node(source_bytes, method_node)
    if name is None:
        return None
    return ".".join([*container_stack, name])


_CLASS_TYPES = {"class_declaration", "interface_declaration", "enum_declaration", "record_declaration", "annotation_type_declaration"}
_METHOD_TYPES = {"method_declaration", "constructor_declaration", "compact_constructor_declaration"}




def _java_string_literal_value(source_bytes: bytes, node: Any | None) -> str | None:
    if node is None or node.type != "string_literal":
        return None
    text = _node_text(source_bytes, node).strip()
    if len(text) >= 2 and text[0] == '"' and text[-1] == '"':
        return text[1:-1]
    return None


def _java_annotation_name(source_bytes: bytes, node: Any) -> str | None:
    for child in _named_children(node):
        if child.type in {"identifier", "scoped_identifier"}:
            return _node_text(source_bytes, child).split(".")[-1]
    return None


def _java_annotation_args(node: Any) -> list[Any]:
    args = _find_descendant(node, "annotation_argument_list")
    if args is None:
        return []
    return _named_children(args)


def _java_literal_string_array(source_bytes: bytes, node: Any) -> list[str] | None:
    if node.type == "string_literal":
        value = _java_string_literal_value(source_bytes, node)
        return [value] if value is not None else None
    if node.type != "element_value_array_initializer":
        return None
    values = [_java_string_literal_value(source_bytes, child) for child in _named_children(node)]
    return None if any(value is None for value in values) else [value for value in values if value is not None]


def _java_annotation_literal_paths(source_bytes: bytes, node: Any) -> tuple[list[str] | None, str | None]:
    args = _java_annotation_args(node)
    if not args:
        return [""], None
    if len(args) == 1 and args[0].type in {"string_literal", "element_value_array_initializer"}:
        values = _java_literal_string_array(source_bytes, args[0])
        return (values, None) if values else (None, "java_route_path_not_literal")
    if any(arg.type != "element_value_pair" for arg in args):
        return None, "java_route_path_not_literal"
    aliases: dict[str, list[str]] = {}
    for arg in args:
        if arg.type != "element_value_pair":
            continue
        name = _child_by_field(arg, "key") or (_named_children(arg)[0] if _named_children(arg) else None)
        value = _child_by_field(arg, "value")
        key = _node_text(source_bytes, name) if name is not None else ""
        if key in {"path", "value"}:
            literals = _java_literal_string_array(source_bytes, value) if value is not None else None
            if not literals:
                return None, "java_route_path_not_literal"
            aliases[key] = literals
    if len(aliases) > 1:
        return None, "java_route_path_alias_ambiguous"
    return (next(iter(aliases.values())), None) if aliases else ([""], None)


def _join_java_paths(prefix: str, route: str) -> str:
    if not prefix:
        return route or ""
    if not route:
        return prefix
    return "/" + prefix.strip("/") + "/" + route.strip("/")


def _java_request_methods(source_bytes: bytes, annotation: Any) -> list[str] | None:
    for arg in _java_annotation_args(annotation):
        if arg.type != "element_value_pair":
            continue
        children = _named_children(arg)
        key_node = _child_by_field(arg, "key") or (children[0] if children else None)
        if key_node is None or _node_text(source_bytes, key_node) != "method":
            continue
        value = _child_by_field(arg, "value")
        values = _named_children(value) if value is not None and value.type == "element_value_array_initializer" else ([value] if value is not None else [])
        methods: list[str] = []
        for item in values:
            text = _node_text(source_bytes, item)
            if item.type != "field_access" or not text.startswith("RequestMethod.") or text.count(".") != 1:
                return None
            method = text.split(".")[1]
            if method not in {"GET", "POST", "PUT", "DELETE", "PATCH"}:
                return None
            methods.append(method)
        return methods or None
    return None


def _java_route_contract(source_bytes: bytes, annotation: Any) -> tuple[list[str], list[str] | None, str | None] | None:
    name = _java_annotation_name(source_bytes, annotation)
    if name is None:
        return None
    shortcut = {
        "GetMapping": "GET",
        "PostMapping": "POST",
        "PutMapping": "PUT",
        "DeleteMapping": "DELETE",
        "PatchMapping": "PATCH",
    }
    if name in shortcut:
        paths, reason = _java_annotation_literal_paths(source_bytes, annotation)
        return [shortcut[name]], paths, reason
    if name == "RequestMapping":
        paths, reason = _java_annotation_literal_paths(source_bytes, annotation)
        methods = _java_request_methods(source_bytes, annotation)
        return (methods or [], paths, reason or (None if methods else "java_route_method_not_literal"))
    return None


def _java_annotations(node: Any) -> list[Any]:
    mods = None
    for child in _named_children(node):
        if child.type == "modifiers":
            mods = child
            break
    if mods is None:
        return []
    return [c for c in _named_children(mods) if c.type in {"annotation", "marker_annotation"}]


def extract_java_apis(path: str, source: str) -> list[ApiNode]:
    if not path.endswith(".java"):
        return []
    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    imports = _java_explicit_imports(source)
    mapping_fqn = "org.springframework.web.bind.annotation."
    # A Spring web wildcard import is still an exact package-level binding for
    # these framework annotations (and is what generated JHipster resources
    # use).  Do not generalise this to arbitrary wildcard imports.
    spring_web_wildcard = bool(re.search(
        r"(?m)^\s*import\s+org\.springframework\.web\.bind\.annotation\.\*\s*;",
        source,
    ))
    allowed_mappings = {"RequestMapping", "GetMapping", "PostMapping", "PutMapping", "DeleteMapping", "PatchMapping"}
    exact_mappings = {
        name for name in allowed_mappings
        if imports.get(name) == mapping_fqn + name or spring_web_wildcard
    }
    exact_controllers = {
        name for name, fqn in {
            "Controller": "org.springframework.stereotype.Controller",
            "RestController": mapping_fqn + "RestController",
        }.items() if imports.get(name) == fqn or (name == "RestController" and spring_web_wildcard)
    }
    methods_by_qualname: dict[str, list[ClassNode]] = {}
    for method_node in extract_java_methods(path, source):
        if method_node.node_kind == "method":
            methods_by_qualname.setdefault(method_node.qualname, []).append(method_node)
    out: list[ApiNode] = []

    def walk(node: Any, stack: list[str], class_prefixes: list[str] | None, controller: bool) -> None:
        next_stack = stack
        next_prefixes = class_prefixes
        next_controller = controller
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(source_bytes, node)
            if name:
                next_stack = [*stack, name]
            annotations = _java_annotations(node)
            next_controller = any(_java_annotation_name(source_bytes, ann) in exact_controllers for ann in annotations)
            for ann in annotations:
                if _java_annotation_name(source_bytes, ann) not in exact_mappings:
                    continue
                prefixes, reason = _java_annotation_literal_paths(source_bytes, ann)
                next_prefixes = prefixes if reason is None else None
        elif node.type == "method_declaration" and controller and class_prefixes is not None:
            qualname = _method_qualname(source_bytes, node, stack)
            if qualname:
                handler_candidates = methods_by_qualname.get(qualname, [])
                # A method reference cannot be represented honestly when overload
                # resolution would be required, so omit the route conservatively.
                if len(handler_candidates) != 1:
                    return
                handler_node_id = java_node_id(handler_candidates[0])
                for ann in _java_annotations(node):
                    if _java_annotation_name(source_bytes, ann) not in exact_mappings:
                        continue
                    contract = _java_route_contract(source_bytes, ann)
                    if contract is None:
                        continue
                    methods, routes, reason = contract
                    if reason is not None or routes is None or not methods:
                        continue
                    line_start = _line_start(ann)
                    line_end = _line_end(node)
                    api_hash = java_hash_for_node(source, node)
                    for prefix in class_prefixes:
                        for route in routes:
                            full_path = _join_java_paths(prefix, route)
                            for method in methods:
                                out.append(ApiNode(
                            path=path,
                            method=method,
                            route_path=full_path,
                            handler_qualname=qualname,
                            line_start=line_start,
                            line_end=line_end,
                            api_hash=api_hash,
                            keywords=_identifier_keywords(f"{full_path}_{qualname}"),
                            handler_node_id=handler_node_id,
                                ))
        for child in _named_children(node):
            walk(child, next_stack, next_prefixes, next_controller)

    walk(tree.root_node, [], [""], False)
    return out




def extract_java_feign_apis(path: str, source: str) -> list[ApiNode]:
    """Exact-import, literal-only Spring Cloud OpenFeign declaration slice.

    A Feign interface method is represented as a dual-bound API relationship:
    the client annotation is the independently mutable route declaration and
    the interface method is the handler/declaration endpoint. Runtime client
    behavior is deliberately not inferred.
    """
    if not path.endswith(".java"):
        return []
    imports = _java_explicit_imports(source)
    if imports.get("FeignClient") != "org.springframework.cloud.openfeign.FeignClient":
        return []
    mapping_fqn = "org.springframework.web.bind.annotation."
    allowed = {"RequestMapping", "GetMapping", "PostMapping", "PutMapping", "DeleteMapping", "PatchMapping"}
    exact = {name for name in allowed if imports.get(name) == mapping_fqn + name}
    if not exact:
        return []
    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    methods = [m for m in extract_java_methods(path, source) if m.node_kind == "method"]
    by_q: dict[str, list[ClassNode]] = {}
    for method in methods:
        by_q.setdefault(method.qualname, []).append(method)
    out: list[ApiNode] = []

    def literal_arg(ann: Any, names: set[str], positional: bool = False) -> str | None:
        args = _java_annotation_args(ann)
        if positional and len(args) == 1 and args[0].type == "string_literal":
            text = _node_text(source_bytes, args[0]); return text[1:-1] if len(text) >= 2 else None
        for arg in args:
            if arg.type != "element_value_pair": continue
            children = _named_children(arg)
            key = _child_by_field(arg, "key") or (children[0] if children else None)
            value = _child_by_field(arg, "value")
            if key is not None and value is not None and _node_text(source_bytes, key) in names and value.type == "string_literal":
                text = _node_text(source_bytes, value); return text[1:-1]
        return None

    def walk(node: Any, stack: list[str], client: tuple[str, str | None, str, Any] | None) -> None:
        next_stack, next_client = stack, client
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(source_bytes, node)
            if name: next_stack = [*stack, name]
            next_client = None
            if node.type == "interface_declaration":
                for ann in _java_annotations(node):
                    if _java_annotation_name(source_bytes, ann) != "FeignClient": continue
                    service = literal_arg(ann, {"name", "value"}, positional=True)
                    url = literal_arg(ann, {"url"})
                    prefix = literal_arg(ann, {"path"}) or ""
                    # Any present but non-literal supported field fails closed.
                    text = _node_text(source_bytes, ann)
                    if service and not any(token in text for token in ("${", "#{")):
                        next_client = (service, url, prefix, ann)
        elif node.type == "method_declaration" and client is not None:
            q = _method_qualname(source_bytes, node, stack)
            candidates = by_q.get(q or "", [])
            if q and len(candidates) == 1:
                for ann in _java_annotations(node):
                    if _java_annotation_name(source_bytes, ann) not in exact: continue
                    contract = _java_route_contract(source_bytes, ann)
                    if contract is None: continue
                    verbs, paths, reason = contract
                    if reason is not None or paths is None or len(verbs) != 1: continue
                    service, url, prefix, client_ann = client
                    handler = candidates[0]
                    route_hash = java_hash_for_node(source, client_ann)
                    for route in paths:
                        full = _join_java_paths(prefix, route)
                        out.append(ApiNode(path=path, method=verbs[0], route_path=full,
                            handler_qualname=q, line_start=_line_start(client_ann), line_end=_line_end(client_ann),
                            api_hash=route_hash, keywords=_identifier_keywords(f"{service}_{full}_{q}"),
                            handler_node_id=java_node_id(handler), route_path_source=path,
                            route_qualname=f"FeignClient {service}", route_line_start=_line_start(client_ann),
                            route_line_end=_line_end(client_ann), route_hash=route_hash,
                            handler_path=path, handler_hash=handler.class_hash, service_name=service,
                            service_url=url, adapter="spring-cloud-openfeign-literal"))
        for child in _named_children(node): walk(child, next_stack, next_client)
    walk(tree.root_node, [], None)
    return out


_WEBFLUX_FQNS = {
    "RouterFunctions": "org.springframework.web.reactive.function.server.RouterFunctions",
    "RequestPredicates": "org.springframework.web.reactive.function.server.RequestPredicates",
}
_WEBFLUX_VERBS = "GET|POST|PUT|DELETE|PATCH|HEAD|OPTIONS"


def extract_java_functional_apis(repo: Any, path: str, source: str) -> list[ApiNode]:
    """Resolve the deliberately small, exact-import WebFlux functional subset.

    Accepted route expressions are direct ``RouterFunctions.route`` and flat
    ``RouterFunctions.route().VERB(...).VERB(...).build()`` chains.  Anything
    requiring Java typing, predicate composition, nesting, lambdas, filters,
    resources, or overload selection is omitted rather than guessed.
    """
    if not path.endswith(".java"):
        return []
    imports = _java_explicit_imports(source)
    if any(imports.get(k) != v for k, v in _WEBFLUX_FQNS.items()):
        return []
    java_paths = [p for p in repo.ls_files() if p.endswith(".java")]
    class_candidates: dict[str, list[tuple[str, ClassNode]]] = {}
    method_candidates: dict[tuple[str, str], list[ClassNode]] = {}
    for candidate_path in java_paths:
        try:
            candidate_source = repo.read_file(candidate_path)
            classes = [c for c in extract_java_classes(candidate_path, candidate_source) if c.node_kind in {"class", "record"}]
            methods = [m for m in extract_java_methods(candidate_path, candidate_source) if m.node_kind == "method"]
        except Exception:
            continue
        for cls in classes:
            simple = cls.qualname.rsplit(".", 1)[-1]
            class_candidates.setdefault(simple, []).append((candidate_path, cls))
        for method in methods:
            owner, _, name = method.qualname.rpartition(".")
            method_candidates.setdefault((owner.rsplit(".", 1)[-1], name), []).append(method)

    # Only declared field/parameter/local identifiers with an exactly imported
    # or uniquely repository-local handler type are eligible.
    variable_types: dict[str, str] = {}
    decl_re = re.compile(r"\b([A-Z][A-Za-z0-9_]*)\s+([a-zA-Z_$][\w$]*)\s*(?=[,;)=])")
    for type_name, variable in decl_re.findall(source):
        if imports.get(type_name) or len(class_candidates.get(type_name, [])) == 1:
            variable_types[variable] = type_name

    def resolved_handler(variable: str, method_name: str) -> tuple[str, ClassNode] | None:
        type_name = variable_types.get(variable)
        if not type_name:
            return None
        classes = class_candidates.get(type_name, [])
        imported = imports.get(type_name)
        if imported:
            classes = [(p, c) for p, c in classes if _java_package(repo.read_file(p)) + "." + type_name == imported]
        if len(classes) != 1:
            return None
        handler_path, handler_class = classes[0]
        methods = method_candidates.get((handler_class.qualname.rsplit(".", 1)[-1], method_name), [])
        if len(methods) != 1 or methods[0].path != handler_path:
            return None
        return handler_path, methods[0]

    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    out: list[ApiNode] = []
    direct = re.compile(
        rf"^RouterFunctions\.route\(\s*RequestPredicates\.({_WEBFLUX_VERBS})\(\s*\"([^\"\\]*)\"\s*\)\s*,\s*([A-Za-z_$][\w$]*)::([A-Za-z_$][\w$]*)\s*\)$",
        re.S,
    )
    builder_item = re.compile(
        rf"\.({_WEBFLUX_VERBS})\(\s*\"([^\"\\]*)\"\s*,\s*([A-Za-z_$][\w$]*)::([A-Za-z_$][\w$]*)\s*\)", re.S
    )

    def add(node: Any, verb: str, uri: str, variable: str, method_name: str) -> None:
        resolved = resolved_handler(variable, method_name)
        if resolved is None:
            return
        handler_path, handler = resolved
        route_hash = java_hash_for_node(source, node)
        out.append(ApiNode(
            path=path, method=verb, route_path=uri, handler_qualname=handler.qualname,
            line_start=_line_start(node), line_end=_line_end(node), api_hash=route_hash,
            keywords=_identifier_keywords(f"{uri}_{handler.qualname}"), handler_node_id=java_node_id(handler),
            route_path_source=path, route_qualname=f"{verb} {uri}",
            route_line_start=_line_start(node), route_line_end=_line_end(node), route_hash=route_hash,
            handler_path=handler_path, handler_hash=handler.class_hash,
        ))

    def walk(node: Any) -> None:
        if node.type == "method_invocation":
            text = source_bytes[node.start_byte:node.end_byte].decode("utf-8")
            match = direct.fullmatch(text.strip())
            ancestor = node.parent
            nested_or_filtered = False
            while ancestor is not None and ancestor.type not in {"return_statement", "expression_statement", "local_variable_declaration"}:
                if ancestor.type == "method_invocation":
                    outer = source_bytes[ancestor.start_byte:ancestor.end_byte].decode("utf-8")
                    if "RouterFunctions.nest(" in outer or ".filter(" in outer or ".resources(" in outer:
                        nested_or_filtered = True
                        break
                ancestor = ancestor.parent
            if match and not nested_or_filtered:
                add(node, *match.groups())
            elif text.strip().startswith("RouterFunctions.route()") and text.strip().endswith(".build()"):
                # Ensure the complete middle consists solely of accepted items.
                middle = text.strip()[len("RouterFunctions.route()"):-len(".build()")]
                matches = list(builder_item.finditer(middle))
                if matches and "".join(m.group(0) for m in matches) == middle:
                    for item in matches:
                        add(node, *item.groups())
        for child in _named_children(node):
            walk(child)

    walk(tree.root_node)
    # Nested method-invocation AST nodes can expose the same builder prefix.
    unique = {(a.method, a.route_path, a.handler_node_id): a for a in out}
    return list(unique.values())




def extract_java_classes(path: str, source: str) -> list[ClassNode]:
    if not path.endswith(".java"):
        return []
    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    root = tree.root_node
    out: list[ClassNode] = []

    def walk(node: Any, stack: list[str]) -> None:
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(source_bytes, node)
            if name:
                qualname = ".".join([*stack, name])
                # Records use the established class/type identity semantics.  Do
                # not synthesize their implicit fields, accessors, or methods.
                kind = (
                    "class" if node.type == "record_declaration"
                    else "interface" if node.type == "annotation_type_declaration"
                    else node.type.replace("_declaration", "")
                )
                out.append(ClassNode(
                    path=path,
                    qualname=qualname,
                    line_start=_line_start(node),
                    line_end=_line_end(node),
                    class_hash=java_hash_for_node(source, node),
                    keywords=_identifier_keywords(qualname),
                    docstring=None,
                    language="java",
                    node_kind=kind,
                    extraction_tier="java-treesitter-syntactic",
                ))
                stack = [*stack, name]
        for child in _named_children(node):
            walk(child, stack)

    walk(root, [])
    return out


def extract_java_methods(path: str, source: str) -> list[ClassNode]:
    if not path.endswith(".java"):
        return []
    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    root = tree.root_node
    raw: list[tuple[Any, str, str, tuple[str, ...]]] = []

    def walk(node: Any, stack: list[str]) -> None:
        next_stack = stack
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(source_bytes, node)
            if name:
                next_stack = [*stack, name]
        elif node.type in _METHOD_TYPES:
            qualname = _method_qualname(source_bytes, node, stack)
            if qualname:
                _name, _argc, parameter_types = _method_signature_parts(source_bytes, node)
                raw.append((node, qualname, "method" if node.type == "method_declaration" else "constructor", parameter_types))
        for child in _named_children(node):
            walk(child, next_stack)

    walk(root, [])
    counts: dict[tuple[str, str], int] = {}
    for _node, qualname, kind, _types in raw:
        counts[(qualname, kind)] = counts.get((qualname, kind), 0) + 1
    out: list[ClassNode] = []
    for node, qualname, kind, parameter_types in raw:
        identity_key = qualname
        if counts[(qualname, kind)] > 1:
            identity_key = f"{qualname}({','.join(parameter_types)})"
        out.append(ClassNode(
                    path=path,
                    qualname=qualname,
                    line_start=_line_start(node),
                    line_end=_line_end(node),
                    class_hash=java_hash_for_node(source, node),
                    keywords=_identifier_keywords(qualname),
                    docstring=None,
                    language="java",
                    node_kind=kind,
                    extraction_tier="java-treesitter-syntactic",
                    identity_key=identity_key,
                ))
    return out


def java_node_id(node: ClassNode | DeclarationNode) -> str:
    ids = __import__("tmf.ids", fromlist=["stable_java_node_claim_id"])
    kind = node.declaration_kind if isinstance(node, DeclarationNode) else node.node_kind
    identity_key = None if isinstance(node, DeclarationNode) else node.identity_key
    return ids.stable_java_node_claim_id(node.path, node.qualname, kind, identity_key)


def extract_java_fields(path: str, source: str) -> list[DeclarationNode]:
    if not path.endswith(".java"):
        return []
    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    root = tree.root_node
    out: list[DeclarationNode] = []

    def walk(node: Any, stack: list[str]) -> None:
        next_stack = stack
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(source_bytes, node)
            if name:
                next_stack = [*stack, name]
        elif node.type in {"field_declaration", "constant_declaration"}:
            constants = set(_constants_from_field_declaration(source_bytes, node))
            for qualname in _field_qualnames(source_bytes, node, stack):
                simple = qualname.rsplit(".", 1)[-1]
                kind = "constant" if node.type == "constant_declaration" or simple in constants else "field"
                out.append(DeclarationNode(
                    path=path,
                    qualname=qualname,
                    line_start=_line_start(node),
                    line_end=_line_end(node),
                    declaration_hash=java_hash_for_node(source, node),
                    keywords=_identifier_keywords(qualname),
                    declaration_kind=kind,
                    language="java",
                    extraction_tier="java-treesitter-syntactic",
                ))
        for child in _named_children(node):
            walk(child, next_stack)

    walk(root, [])
    return out


@dataclass(frozen=True)
class JavaCallEdge:
    caller_id: str
    callee_id: str
    callee_qualname: str
    evidence: str = "observed"
    resolution: str = "java_syntax"
    caller_path: str | None = None
    callee_path: str | None = None
    caller_fn_hash: str | None = None
    callee_fn_hash: str | None = None
    caller_qualname: str | None = None
    caller_node_kind: str | None = "method"
    callee_node_kind: str | None = "method"
    language: str = "java"


@dataclass(frozen=True)
class JavaUnresolvedCall:
    caller_id: str
    expr: str
    reason: str


def _method_signature_parts(source_bytes: bytes, node: Any) -> tuple[str | None, int, tuple[str, ...]]:
    from .java_types import parse_java_type
    name = _identifier_from_node(source_bytes, node)
    params = _child_by_field(node, "parameters")
    types: list[str] = []
    if params is not None:
        for child in _named_children(params):
            if child.type in {"formal_parameter", "spread_parameter"}:
                typ = _child_by_field(child, "type")
                if typ is None:
                    types.append("")
                else:
                    parsed = parse_java_type(_node_text(source_bytes, typ).strip() + ("..." if child.type == "spread_parameter" else ""))
                    types.append(parsed.canonical + ("..." if parsed.varargs else ""))
    return name, len(types), tuple(types)


def _method_type_parameters(source_bytes: bytes, node: Any) -> dict[str, str | None] | None:
    """Read the deliberately small method-generic inference surface.

    Constructors and multi-variable, intersection, recursive, or parameterized
    bounds are excluded. ``None`` also marks an unsupported declaration.
    """
    if node.type != "method_declaration":
        return {}
    params = _child_by_field(node, "type_parameters")
    if params is None:
        params = next((c for c in _named_children(node) if c.type == "type_parameters"), None)
    if params is None:
        return {}
    declarations = [c for c in _named_children(params) if c.type == "type_parameter"]
    if len(declarations) != 1:
        return None
    declaration = declarations[0]
    name_node = next((c for c in _named_children(declaration) if c.type == "type_identifier"), None)
    if name_node is None:
        return None
    name = _node_text(source_bytes, name_node).strip()
    bound_node = next((c for c in _named_children(declaration) if c.type == "type_bound"), None)
    if bound_node is None:
        return {name: None}
    bound = _node_text(source_bytes, bound_node).strip()
    bound = bound[len("extends"):].strip() if bound.startswith("extends") else bound
    if not bound or "&" in bound or "<" in bound or name in bound:
        return None
    return {name: bound}


def _method_signature_index(path: str, source: str) -> dict[str, tuple[int, tuple[str, ...]]]:
    if not path.endswith(".java"):
        return {}
    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    out: dict[str, tuple[int, tuple[str, ...]]] = {}
    stack: list[str] = []

    def walk(node: Any, stack: list[str]) -> None:
        next_stack = stack
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(source_bytes, node)
            if name:
                next_stack = [*stack, name]
        elif node.type in _METHOD_TYPES:
            name, argc, types = _method_signature_parts(source_bytes, node)
            if name:
                out[".".join([*stack, name])] = (argc, types)
        for child in _named_children(node):
            walk(child, next_stack)

    walk(tree.root_node, [])
    return out


def _call_expr_name(source_bytes: bytes, node: Any) -> tuple[str, str | None] | None:
    name_node = _child_by_field(node, "name")
    if name_node is None:
        return None
    name = _node_text(source_bytes, name_node)
    obj = _child_by_field(node, "object")
    if obj is None:
        return name, None
    return name, _node_text(source_bytes, obj).strip()


def _call_arg_count(node: Any) -> int:
    args = _child_by_field(node, "arguments")
    if args is None:
        return 0
    return len([c for c in _named_children(args) if c.type not in {",", "(" , ")"}])


def _call_argument_types(source_bytes: bytes, node: Any, declared: dict[str, str]) -> tuple[str | None, ...]:
    from .java_types import parse_java_type
    args = _child_by_field(node, "arguments")
    if args is None:
        return ()
    out: list[str | None] = []
    literal_types = {
        "decimal_integer_literal": "int", "hex_integer_literal": "int", "octal_integer_literal": "int", "binary_integer_literal": "int",
        "decimal_floating_point_literal": "double", "hex_floating_point_literal": "double",
        "true": "boolean", "false": "boolean", "character_literal": "char", "string_literal": "String", "null_literal": None,
    }
    for arg in _named_children(args):
        typ: str | None = literal_types.get(arg.type)
        text = _node_text(source_bytes, arg).strip()
        if arg.type == "identifier":
            declared_type = declared.get(text)
            typ = parse_java_type(declared_type).canonical if declared_type else None
        elif arg.type == "object_creation_expression":
            type_node = _child_by_field(arg, "type")
            typ = parse_java_type(_node_text(source_bytes, type_node)).canonical if type_node is not None else None
        elif arg.type == "array_creation_expression":
            type_node = _child_by_field(arg, "type")
            if type_node is not None:
                base = parse_java_type(_node_text(source_bytes, type_node))
                dimensions = sum(1 for child in _named_children(arg)
                                 if child.type in {"dimensions_expr", "dimensions"})
                typ = base.canonical + "[]" * dimensions if dimensions else None
        elif arg.type not in literal_types:
            typ = None
        out.append(typ)
    return tuple(out)


def resolve_java_call_edges(path: str, source: str, java_methods: list[ClassNode], repo: Any | None = None, inherit_edges: list[JavaInheritEdge] | None = None) -> tuple[list[JavaCallEdge], dict[str, list[JavaUnresolvedCall]]]:
    if not path.endswith(".java"):
        return [], {}
    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    root = tree.root_node
    java_classes = extract_java_classes(path, source)
    explicit_imports, _wildcards, static_imports = _java_imports(source_bytes, root)
    project_index = None
    package = ""
    if repo is not None:
        from .java_index import java_package, java_project_index
        project_index = java_project_index(repo)
        package = java_package(source)
    snapshot = getattr(repo, "_tmf_java_repository_snapshot", None) if repo is not None else None

    def methods_for(file_path: str, file_source: str | None = None) -> list[ClassNode]:
        if snapshot is not None and file_path in snapshot.methods:
            return list(snapshot.methods[file_path])
        if file_source is None:
            file_source = repo.read_file(file_path)
        return extract_java_methods(file_path, file_source)

    def classes_for(file_path: str, file_source: str | None = None) -> list[ClassNode]:
        if snapshot is not None and file_path in snapshot.classes:
            return list(snapshot.classes[file_path])
        if file_source is None:
            file_source = repo.read_file(file_path)
        return extract_java_classes(file_path, file_source)
    by_qual = {m.qualname: m for m in java_methods if m.node_kind == "method"}
    by_class: dict[str, list[ClassNode]] = {}
    for m in java_methods:
        if m.node_kind == "method" and "." in m.qualname:
            cls = m.qualname.rsplit(".", 1)[0]
            by_class.setdefault(cls, []).append(m)
    constructors_by_class: dict[str, list[ClassNode]] = {}
    for m in java_methods:
        if m.node_kind == "constructor" and "." in m.qualname:
            constructors_by_class.setdefault(m.qualname.rsplit(".", 1)[0], []).append(m)
    sigs_current = _method_signature_index(path, source)
    edges: list[JavaCallEdge] = []
    unresolved: dict[str, list[JavaUnresolvedCall]] = {}

    def add_unresolved(caller: ClassNode, expr: str, reason: str) -> None:
        caller_id = java_node_id(caller)
        unresolved.setdefault(caller_id, []).append(JavaUnresolvedCall(caller_id=caller_id, expr=expr, reason=reason))

    def add_edge(caller: ClassNode, callee: ClassNode, resolution: str) -> None:
        ids = __import__("tmf.ids", fromlist=["stable_java_node_claim_id"])
        edges.append(JavaCallEdge(
            caller_id=java_node_id(caller),
            callee_id=java_node_id(callee),
            callee_qualname=callee.qualname,
            resolution=resolution,
            caller_path=caller.path,
            callee_path=callee.path,
            caller_fn_hash=caller.class_hash,
            callee_fn_hash=callee.class_hash,
            caller_qualname=caller.qualname,
            callee_node_kind=callee.node_kind,
        ))

    signature_cache: dict[tuple[str, int, int, str], tuple[str, ...] | None] = {}
    type_parameter_cache: dict[tuple[str, int, int, str], dict[str, str | None] | None] = {}

    def method_signature(method: ClassNode) -> tuple[str, ...] | None:
        key = (method.path, method.line_start, method.line_end, method.identity_key or method.qualname)
        if key in signature_cache:
            return signature_cache[key]
        try:
            method_source = source if method.path == path else repo.read_file(method.path)
            source_data = method_source.encode("utf-8")
            _language, method_parser = _language_and_parser()
            method_tree = method_parser.parse(source_data)
            found = None
            def walk(cur: Any) -> None:
                nonlocal found
                if found is not None:
                    return
                if cur.type in _METHOD_TYPES and _line_start(cur) == method.line_start and _line_end(cur) == method.line_end:
                    signature = _method_signature_parts(source_data, cur)[2]
                    identity = f"{method.qualname}({','.join(signature)})"
                    if method.identity_key in {None, method.qualname, identity}:
                        found = signature
                        return
                for child in _named_children(cur):
                    walk(child)
            walk(method_tree.root_node)
        except Exception:
            found = None
        signature_cache[key] = found
        return found

    def method_type_parameters(method: ClassNode) -> dict[str, str | None] | None:
        key = (method.path, method.line_start, method.line_end, method.identity_key or method.qualname)
        if key in type_parameter_cache:
            return type_parameter_cache[key]
        found = None
        try:
            method_source = source if method.path == path else repo.read_file(method.path)
            data = method_source.encode("utf-8")
            _language, parser = _language_and_parser()
            tree = parser.parse(data)
            def walk(cur: Any) -> None:
                nonlocal found
                if found is not None:
                    return
                if cur.type in _METHOD_TYPES and _line_start(cur) == method.line_start and _line_end(cur) == method.line_end:
                    found = _method_type_parameters(data, cur)
                    return
                for child in _named_children(cur):
                    walk(child)
            walk(tree.root_node)
        except Exception:
            found = None
        type_parameter_cache[key] = found
        return found

    def reference_distance(source_type: str, target_type: str) -> int | None:
        """Return the shortest wholly source-defined reference upcast."""
        from .java_types import parse_java_type
        source_ref, target_ref = parse_java_type(source_type), parse_java_type(target_type)
        if (source_ref.primitive or target_ref.primitive or source_ref.array_dims or target_ref.array_dims
                or source_ref.type_arguments or target_ref.type_arguments
                or source_ref.wildcard or target_ref.wildcard):
            return None

        # Built-in JDK type hierarchy: every reference type extends Object
        if target_ref.simple_name == "Object" and target_ref.erased in ("Object", "java.lang.Object"):
            if source_ref.simple_name == "Object" and source_ref.erased in ("Object", "java.lang.Object"):
                return None  # Same type, not an upcast
            # Any non-Object reference type is 1 step from Object
            return 1

        def resolve_ref(ref: Any) -> tuple[str, str] | None:
            local = [c for c in java_classes if c.qualname == ref.simple_name]
            if len(local) == 1:
                return path, local[0].qualname
            if project_index is None:
                return None
            symbol, _ = project_index.resolve(ref.erased, package=package, imports=explicit_imports)
            return (symbol.path, symbol.simple_name) if symbol is not None else None

        start, goal = resolve_ref(source_ref), resolve_ref(target_ref)
        if start is None or goal is None or start == goal:
            return None
        frontier: list[tuple[str, str | None, str, int]] = [(start[0], source if start[0] == path else None, start[1], 0)]
        seen = {start}
        while frontier:
            file_path, file_source, qualname, distance = frontier.pop(0)
            if file_source is None:
                try:
                    file_source = repo.read_file(file_path) if repo is not None else None
                except Exception:
                    file_source = None
            if file_source is None:
                continue
            for parent_path, parent_qualname, _relation in parent_specs_for(file_path, file_source, qualname):
                parent = (parent_path, parent_qualname)
                if parent == goal:
                    return distance + 1
                if parent not in seen:
                    seen.add(parent)
                    frontier.append((parent_path, file_source if parent_path == file_path else None, parent_qualname, distance + 1))
        return None

    def unique_method(methods: list[ClassNode], name: str, argc: int, argument_types: tuple[str | None, ...]) -> tuple[ClassNode | None, str | None]:
        from .java_types import unique_applicable_signature
        cands = [m for m in methods if m.qualname.rsplit(".", 1)[-1] == name]
        if not cands:
            return None, "java_method_not_found"
        argc_matches = []
        for m in cands:
            sig = method_signature(m)
            if sig is None or len(sig) == argc or (sig and sig[-1].endswith("...") and argc >= len(sig) - 1):
                argc_matches.append(m)
        lone_sig = method_signature(argc_matches[0]) if len(argc_matches) == 1 else None
        lone_type_parameters = method_type_parameters(argc_matches[0]) if len(argc_matches) == 1 else None
        if (len(argc_matches) == 1 and not (lone_sig and lone_sig[-1].endswith("..."))
                and lone_type_parameters == {}):
            return argc_matches[0], None
        if argc_matches and all(item is not None for item in argument_types):
            selected = unique_applicable_signature(argument_types, [method_signature(m) for m in argc_matches], reference_distance,
                                                   [method_type_parameters(m) for m in argc_matches])
            if selected is not None:
                return argc_matches[selected], None
        return None, "java_overloaded_or_ambiguous_method"

    def unique_constructor(constructors: list[ClassNode], argc: int, argument_types: tuple[str | None, ...]) -> tuple[ClassNode | None, str | None]:
        from .java_types import unique_applicable_signature
        if not constructors:
            return None, "java_constructor_not_found"
        argc_matches = [c for c in constructors if (
            method_signature(c) is None
            or len(method_signature(c) or ()) == argc
            or (method_signature(c) and method_signature(c)[-1].endswith("...") and argc >= len(method_signature(c)) - 1)
        )]
        lone_sig = method_signature(argc_matches[0]) if len(argc_matches) == 1 else None
        if len(argc_matches) == 1 and not (lone_sig and lone_sig[-1].endswith("...")):
            return argc_matches[0], None
        if argc_matches and all(item is not None for item in argument_types):
            selected = unique_applicable_signature(argument_types, [method_signature(c) for c in argc_matches], reference_distance,
                                                   [method_type_parameters(c) for c in argc_matches])
            if selected is not None:
                return argc_matches[selected], None
        return None, "java_overloaded_or_ambiguous_constructor"

    def constructors_for_type(type_expr: str) -> tuple[list[ClassNode], str]:
        simple = type_expr.rsplit(".", 1)[-1]
        local = constructors_by_class.get(simple, [])
        if local:
            return local, "java_same_file_constructor"
        if repo is None or project_index is None:
            return [], "java_constructor_type_not_resolved"
        symbol, resolution = project_index.resolve(type_expr, package=package, imports=explicit_imports)
        if symbol is None:
            return [], "java_constructor_type_not_resolved"
        try:
            target_source = repo.read_file(symbol.path)
        except Exception:
            return [], "java_constructor_type_not_resolved"
        constructors = [m for m in methods_for(symbol.path, target_source)
                        if m.node_kind == "constructor" and m.qualname.rsplit(".", 1)[0] == symbol.simple_name]
        return constructors, f"java_project_constructor_{resolution}"

    def imported_methods(type_name: str) -> tuple[list[ClassNode], str | None]:
        if repo is None:
            return [], "java_variable_or_unknown_receiver"
        target_path = explicit_imports.get(type_name)
        if project_index is not None:
            symbol, resolution = project_index.resolve(type_name, package=package, imports=explicit_imports)
            if symbol is not None:
                target_path = symbol.path
        if target_path is None:
            return [], "java_variable_or_unknown_receiver"
        try:
            target_source = repo.read_file(target_path)
        except Exception:
            return [], "java_external_or_jdk_receiver"
        methods = methods_for(target_path, target_source)
        methods = [m for m in methods if m.qualname.startswith(type_name + ".")]
        return methods, None

    def receiver_types(method_node: Any) -> dict[str, str]:
        types: dict[str, str] = {}
        params = _child_by_field(method_node, "parameters")
        if params is not None:
            for child in _named_children(params):
                if child.type in {"formal_parameter", "spread_parameter"}:
                    name = _child_by_field(child, "name")
                    typ = _child_by_field(child, "type")
                    if name is not None and typ is not None:
                        types[_node_text(source_bytes, name)] = _node_text(source_bytes, typ).strip()
        def walk(cur: Any) -> None:
            if cur.type == "local_variable_declaration":
                typ = _child_by_field(cur, "type")
                if typ is not None:
                    for child in _named_children(cur):
                        if child.type == "variable_declarator":
                            name = _child_by_field(child, "name")
                            if name is not None:
                                types[_node_text(source_bytes, name)] = _node_text(source_bytes, typ).strip()
            # The loop variable is a statically typed local just like a method
            # parameter.  Missing it made ordinary domain traversals such as
            # `for (Pet pet : pets) pet.getName()` look like unknown receivers.
            elif cur.type == "enhanced_for_statement":
                name = _child_by_field(cur, "name")
                typ = _child_by_field(cur, "type")
                if name is not None and typ is not None:
                    types[_node_text(source_bytes, name)] = _node_text(source_bytes, typ).strip()
            for child in _named_children(cur):
                walk(child)
        body = _child_by_field(method_node, "body")
        if body is not None:
            walk(body)
        return types

    def field_receiver_types() -> dict[str, dict[str, str]]:
        found: dict[str, dict[str, str]] = {}
        def walk(cur: Any, stack: list[str]) -> None:
            next_stack = stack
            if cur.type in _CLASS_TYPES:
                name = _identifier_from_node(source_bytes, cur)
                if name:
                    next_stack = [*stack, name]
            if cur.type in {"field_declaration", "constant_declaration"}:
                typ = _child_by_field(cur, "type")
                if typ is not None and next_stack:
                    bucket = found.setdefault(".".join(next_stack), {})
                    for child in _named_children(cur):
                        if child.type == "variable_declarator":
                            name = _child_by_field(child, "name")
                            if name is not None:
                                bucket[_node_text(source_bytes, name)] = _node_text(source_bytes, typ).strip()
            for child in _named_children(cur):
                walk(child, next_stack)
        walk(root, [])
        return found

    fields_by_class = field_receiver_types()

    parent_specs: dict[str, list[tuple[str, str, str]]] = {}
    for edge in inherit_edges or []:
        if edge.child_path == path and edge.child_qualname:
            parent_specs.setdefault(edge.child_qualname, []).append(
                (edge.parent_path or path, edge.parent_qualname, edge.relation)
            )

    parent_cache: dict[tuple[str, str], list[tuple[str, str, str]]] = {}

    def parent_specs_for(file_path: str, file_source: str, class_qual: str) -> list[tuple[str, str, str]]:
        key = (file_path, class_qual)
        if key in parent_cache:
            return parent_cache[key]
        if file_path == path:
            specs = parent_specs.get(class_qual, [])
        elif repo is not None:
            classes = classes_for(file_path, file_source)
            edges_for_file, _ = resolve_java_inherit_edges(file_path, file_source, classes, repo=repo)
            specs = [
                (edge.parent_path or file_path, edge.parent_qualname, edge.relation)
                for edge in edges_for_file
                if edge.child_qualname == class_qual
            ]
        else:
            specs = []
        parent_cache[key] = specs
        return specs

    def inherited_parent_methods(class_qual: str, *, extends_only: bool = False) -> list[ClassNode]:
        found: list[ClassNode] = []
        seen: set[tuple[str, str]] = set()

        def walk(file_path: str, file_source: str, current_qual: str) -> None:
            marker = (file_path, current_qual)
            if marker in seen:
                return
            seen.add(marker)
            for parent_path, parent_qual, relation in parent_specs_for(file_path, file_source, current_qual):
                if extends_only and relation != "extends":
                    continue
                try:
                    parent_source = file_source if parent_path == file_path else repo.read_file(parent_path)
                except Exception:
                    continue
                methods = java_methods if parent_path == path else methods_for(parent_path, parent_source)
                found.extend(m for m in methods if m.qualname.rsplit(".", 1)[0] == parent_qual)
                walk(parent_path, parent_source, parent_qual)

        walk(path, source, class_qual)
        return found

    def typed_receiver_methods(type_expr: str, name: str) -> tuple[list[ClassNode], str]:
        if repo is None or project_index is None:
            return [], "java_variable_or_unknown_receiver"
        symbol, resolution = project_index.resolve(type_expr, package=package, imports=explicit_imports)
        if symbol is None:
            return [], "java_ambiguous_or_unknown_receiver"
        try:
            target_source = repo.read_file(symbol.path)
        except Exception:
            return [], "java_external_or_jdk_receiver"
        methods = [m for m in methods_for(symbol.path, target_source) if m.qualname.startswith(symbol.simple_name + ".")]
        return methods, f"java_project_typed_receiver_{resolution}"

    def declared_return_type(method: ClassNode) -> str | None:
        """Read only an explicit source return type; constructors/var/inference stay unknown."""
        if method.node_kind != "method" or repo is None:
            return None
        try:
            target_source = source if method.path == path else repo.read_file(method.path)
        except Exception:
            return None
        _lang, target_parser = _language_and_parser()
        data = target_source.encode("utf-8")
        target_tree = target_parser.parse(data)
        matches: list[str] = []
        def scan(cur: Any, stack: list[str]) -> None:
            next_stack = stack
            if cur.type in _CLASS_TYPES:
                n = _identifier_from_node(data, cur)
                if n:
                    next_stack = [*stack, n]
            elif cur.type == "method_declaration" and _method_qualname(data, cur, stack) == method.qualname:
                typ = _child_by_field(cur, "type")
                if typ is not None and _line_start(cur) == method.line_start:
                    matches.append(_node_text(data, typ).strip())
            for child in _named_children(cur):
                scan(child, next_stack)
        scan(target_tree.root_node, [])
        if len(matches) != 1 or matches[0] in {"void", "var"}:
            return None
        declared = matches[0]
        # Preserve the declaring source's exact import context before resolving
        # the return type from the caller's file.
        imported = _java_explicit_imports(target_source).get(declared)
        return imported or declared

    def visit(node: Any, stack: list[str]) -> None:
        next_stack = stack
        current_method: ClassNode | None = None
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(source_bytes, node)
            if name:
                next_stack = [*stack, name]
        elif node.type in _METHOD_TYPES:
            q = _method_qualname(source_bytes, node, stack)
            signature = _method_signature_parts(source_bytes, node)[2]
            identity = f"{q}({','.join(signature)})"
            candidates = [m for m in java_methods if m.node_kind == ("constructor" if node.type == "constructor_declaration" else "method") and m.qualname == q]
            current_method = next((m for m in candidates if m.identity_key == identity), candidates[0] if len(candidates) == 1 else None)
        if current_method is not None:
            class_qual = current_method.qualname.rsplit(".", 1)[0]
            local_methods = by_class.get(class_qual, [])
            local_names = {m.qualname.rsplit(".", 1)[-1] for m in local_methods}
            types_by_name = receiver_types(node)
            types_by_name.update(fields_by_class.get(class_qual, {}))
            def walk_calls(cur: Any) -> None:
                if cur is not node and cur.type in _METHOD_TYPES:
                    return
                # Annotation element values are metadata expressions, never
                # runtime invocations of the annotated callable. Class
                # literals, enum constants, nested annotations, and arrays are
                # deliberately left to annotation/type evidence.
                if cur.type in {"annotation", "marker_annotation"}:
                    return
                # Lambda bodies are deferred code, not calls made by the enclosing
                # method. The graph has no callable/context node for them yet.
                if cur.type == "lambda_expression":
                    add_unresolved(current_method, _node_text(source_bytes, cur).strip(), "java_lambda_deferred_context_not_modeled")
                    return
                # A method reference creates a function value; it is not an
                # invocation. Preserve evidence until a reference edge exists.
                if cur.type == "method_reference":
                    add_unresolved(current_method, _node_text(source_bytes, cur).strip(), "java_method_reference_relationship_not_modeled")
                    return
                if cur.type == "method_invocation":
                    parsed = _call_expr_name(source_bytes, cur)
                    if parsed is not None:
                        name, receiver = parsed
                        argc = _call_arg_count(cur)
                        argument_types = _call_argument_types(source_bytes, cur, types_by_name)
                        if receiver is None:
                            callee, reason = unique_method(local_methods, name, argc, argument_types)
                            if callee is not None:
                                add_edge(current_method, callee, "java_same_class_method")
                            elif name not in local_names:
                                callee, parent_reason = unique_method(inherited_parent_methods(class_qual), name, argc, argument_types)
                                if callee is not None:
                                    add_edge(current_method, callee, "java_direct_parent_method")
                                elif name in static_imports:
                                    # Static import fallback: checkNotNull(...) -> Preconditions.checkNotNull
                                    declaring_class_simple, declaring_class_path = static_imports[name]
                                    if repo is not None:
                                        try:
                                            declaring_source = repo.read_file(declaring_class_path)
                                            methods = methods_for(declaring_class_path, declaring_source)
                                            methods = [m for m in methods if m.qualname.endswith("." + name)]
                                            callee, match_reason = unique_method(methods, name, argc, argument_types)
                                            if callee is not None:
                                                add_edge(current_method, callee, "java_static_import_method")
                                            else:
                                                add_unresolved(current_method, name, match_reason or "java_static_import_method_overload_mismatch")
                                        except Exception:
                                            add_unresolved(current_method, name, "java_static_import_declaring_class_not_found")
                                    else:
                                        add_unresolved(current_method, name, "java_static_import_no_repo")
                                else:
                                    add_unresolved(current_method, name, parent_reason or "java_parent_method_not_found")
                            else:
                                add_unresolved(current_method, name, reason or "java_overloaded_or_ambiguous_method")
                        elif receiver == "this":
                            callee, reason = unique_method(local_methods, name, argc, argument_types)
                            if callee is not None:
                                add_edge(current_method, callee, "java_this_method")
                            else:
                                add_unresolved(current_method, f"this.{name}", reason or "java_method_not_found")
                        elif receiver == "super":
                            callee, reason = unique_method(inherited_parent_methods(class_qual, extends_only=True), name, argc, argument_types)
                            if callee is not None:
                                add_edge(current_method, callee, "java_super_method")
                            else:
                                add_unresolved(current_method, f"super.{name}", reason or "java_parent_method_not_found")
                        elif receiver in explicit_imports:
                            methods, reason = imported_methods(receiver)
                            callee, why = unique_method(methods, name, argc, argument_types)
                            if callee is not None:
                                add_edge(current_method, callee, "java_explicit_import_static_method")
                            else:
                                add_unresolved(current_method, f"{receiver}.{name}", why or reason or "java_method_not_found")
                        elif receiver in types_by_name or receiver.startswith("this.") and receiver[5:] in types_by_name:
                            receiver_name = receiver[5:] if receiver.startswith("this.") else receiver
                            methods, resolution = typed_receiver_methods(types_by_name[receiver_name], name)
                            callee, why = unique_method(methods, name, argc, argument_types)
                            if callee is not None:
                                add_edge(current_method, callee, resolution)
                            else:
                                add_unresolved(current_method, f"{receiver}.{name}", why or resolution)
                        elif (obj := _child_by_field(cur, "object")) is not None and obj.type == "method_invocation":
                            # Conservative one-step chain propagation: resolve the
                            # inner project call exactly, then use only its explicit
                            # declared return type. Generic/JDK continuation (for
                            # example Optional.map/Stream.map) remains unresolved.
                            inner = _call_expr_name(source_bytes, obj)
                            inner_callee = None
                            if inner is not None:
                                inner_name, inner_receiver = inner
                                inner_args = _call_argument_types(source_bytes, obj, types_by_name)
                                if inner_receiver is None:
                                    inner_callee, _ = unique_method(local_methods, inner_name, _call_arg_count(obj), inner_args)
                                elif inner_receiver in types_by_name:
                                    pool, _ = typed_receiver_methods(types_by_name[inner_receiver], inner_name)
                                    inner_callee, _ = unique_method(pool, inner_name, _call_arg_count(obj), inner_args)
                            return_type = declared_return_type(inner_callee) if inner_callee is not None else None
                            if return_type is not None:
                                methods, resolution = typed_receiver_methods(return_type, name)
                                callee, why = unique_method(methods, name, argc, argument_types)
                                if callee is not None:
                                    add_edge(current_method, callee, "java_chained_declared_return_" + resolution)
                                else:
                                    add_unresolved(current_method, f"{receiver}.{name}", why or resolution)
                            else:
                                add_unresolved(current_method, f"{receiver}.{name}", "java_chained_return_type_unresolved")
                        else:
                            add_unresolved(current_method, f"{receiver}.{name}", "java_variable_or_unknown_receiver")
                elif cur.type == "object_creation_expression":
                    type_node = _child_by_field(cur, "type")
                    type_expr = _node_text(source_bytes, type_node).strip() if type_node is not None else "<unknown>"
                    constructors, resolution = constructors_for_type(type_expr)
                    callee, reason = unique_constructor(constructors, _call_arg_count(cur), _call_argument_types(source_bytes, cur, types_by_name))
                    if callee is not None:
                        add_edge(current_method, callee, resolution)
                    else:
                        add_unresolved(current_method, f"new {type_expr}", reason or resolution)
                elif cur.type == "explicit_constructor_invocation":
                    invocation = next((c.type for c in _named_children(cur) if c.type in {"this", "super"}), None)
                    argc = _call_arg_count(cur)
                    argument_types = _call_argument_types(source_bytes, cur, types_by_name)
                    if invocation == "this":
                        candidates = constructors_by_class.get(class_qual, [])
                        resolution = "java_this_constructor"
                    elif invocation == "super":
                        direct = parent_specs_for(path, source, class_qual)
                        candidates = []
                        for parent_path, parent_qual, relation in direct:
                            if relation != "extends":
                                continue
                            try:
                                parent_source = source if parent_path == path else repo.read_file(parent_path)
                            except Exception:
                                continue
                            candidates.extend(m for m in methods_for(parent_path, parent_source)
                                              if m.node_kind == "constructor" and m.qualname.rsplit(".", 1)[0] == parent_qual)
                        resolution = "java_super_constructor"
                    else:
                        candidates, resolution = [], "java_constructor_invocation_not_resolved"
                    callee, reason = unique_constructor(candidates, argc, argument_types)
                    if callee is not None:
                        add_edge(current_method, callee, resolution)
                    else:
                        add_unresolved(current_method, invocation or "constructor", reason or resolution)
                for child in _named_children(cur):
                    # The anonymous body is deferred executable context.  Its
                    # methods and initializers do not execute as calls of the
                    # method which evaluates the explicit `new Base(args)`.
                    # Keep one explicit evidence item until anonymous callable
                    # identity/context nodes have a collision-free schema.
                    if cur.type == "object_creation_expression" and child.type == "class_body":
                        add_unresolved(
                            current_method,
                            _node_text(source_bytes, child).strip(),
                            "java_anonymous_class_body_deferred_context_not_modeled",
                        )
                        continue
                    walk_calls(child)
            walk_calls(node)
            return
        for child in _named_children(node):
            visit(child, next_stack)

    visit(root, [])
    return edges, unresolved


@dataclass(frozen=True)
class JavaFieldEdge:
    accessor_id: str
    field_id: str
    field_qualname: str
    edge_kind: str
    evidence: str = "observed"
    resolution: str = "java_field_syntax"
    accessor_path: str | None = None
    field_path: str | None = None
    accessor_hash: str | None = None
    field_hash: str | None = None
    accessor_qualname: str | None = None
    language: str = "java"


@dataclass(frozen=True)
class JavaUnresolvedFieldAccess:
    accessor_id: str
    expr: str
    reason: str
    edge_kind: str


def _method_params_and_locals(source_bytes: bytes, method_node: Any) -> set[str]:
    names: set[str] = set()
    params = _child_by_field(method_node, "parameters")
    if params is not None:
        for child in _named_children(params):
            if child.type in {"formal_parameter", "spread_parameter"}:
                name = _child_by_field(child, "name")
                if name is not None:
                    names.add(_node_text(source_bytes, name))
    def walk(cur: Any) -> None:
        if cur.type == "lambda_expression":
            return
        if cur.type == "object_creation_expression" and any(c.type == "class_body" for c in _named_children(cur)):
            return
        if cur.type == "variable_declarator":
            name = _child_by_field(cur, "name")
            if name is not None:
                names.add(_node_text(source_bytes, name))
        elif cur.type in {"resource", "catch_formal_parameter"}:
            name = _child_by_field(cur, "name")
            if name is not None:
                names.add(_node_text(source_bytes, name))
        for child in _named_children(cur):
            walk(child)
    body = _child_by_field(method_node, "body")
    if body is not None:
        walk(body)
    return names


def _field_index_by_class(java_fields: list[DeclarationNode]) -> dict[str, dict[str, DeclarationNode]]:
    out: dict[str, dict[str, DeclarationNode]] = {}
    for f in java_fields:
        if "." not in f.qualname:
            continue
        cls, name = f.qualname.rsplit(".", 1)
        out.setdefault(cls, {})[name] = f
    return out


def resolve_java_field_edges(path: str, source: str, java_methods: list[ClassNode], java_fields: list[DeclarationNode], repo: Any | None = None, inherit_edges: list[JavaInheritEdge] | None = None) -> tuple[list[JavaFieldEdge], dict[str, list[JavaUnresolvedFieldAccess]]]:
    if not path.endswith(".java"):
        return [], {}
    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    root = tree.root_node
    explicit_imports, _wildcards, static_imports = _java_imports(source_bytes, root)
    methods_by_qual = {m.qualname: m for m in java_methods if m.node_kind == "method"}
    fields_by_class = _field_index_by_class(java_fields)
    if inherit_edges is None:
        inherit_edges, _ = resolve_java_inherit_edges(path, source, extract_java_classes(path, source), repo=repo)
    parent_edges_by_child: dict[tuple[str, str], list[JavaInheritEdge]] = {}
    for edge in inherit_edges:
        if edge.relation == "extends" and edge.child_path and edge.child_qualname:
            parent_edges_by_child.setdefault((edge.child_path, edge.child_qualname), []).append(edge)
    parent_edges_loaded: set[str] = {path}

    def load_parent_edges(file_path: str, file_source: str) -> None:
        if file_path in parent_edges_loaded:
            return
        parent_edges_loaded.add(file_path)
        classes = extract_java_classes(file_path, file_source)
        edges, _ = resolve_java_inherit_edges(file_path, file_source, classes, repo=repo)
        for edge in edges:
            if edge.relation == "extends" and edge.child_path and edge.child_qualname:
                parent_edges_by_child.setdefault((edge.child_path, edge.child_qualname), []).append(edge)
    inherited_fields_cache: dict[tuple[str, str], tuple[dict[str, DeclarationNode], set[str]]] = {}

    def inherited_fields(file_path: str, file_source: str, class_qual: str, seen: set[tuple[str, str]] | None = None) -> tuple[dict[str, DeclarationNode], set[str]]:
        key = (file_path, class_qual)
        if key in inherited_fields_cache:
            return inherited_fields_cache[key]
        seen = set() if seen is None else seen
        if key in seen:
            return {}, set()
        seen.add(key)
        found: dict[str, DeclarationNode] = {}
        ambiguous: set[str] = set()
        for edge in parent_edges_by_child.get(key, []):
            parent_path = edge.parent_path or file_path
            try:
                parent_source = file_source if parent_path == file_path else repo.read_file(parent_path)
            except Exception:
                continue
            load_parent_edges(parent_path, parent_source)
            parent_fields = java_fields if parent_path == path else extract_java_fields(parent_path, parent_source)
            direct = _field_index_by_class(parent_fields)
            candidates = dict(direct.get(edge.parent_qualname, {}))
            transitive, transitive_ambiguous = inherited_fields(parent_path, parent_source, edge.parent_qualname, seen.copy())
            for name, field in {**transitive, **candidates}.items():
                if name in found and found[name].path != field.path:
                    ambiguous.add(name)
                else:
                    found[name] = field
            ambiguous.update(transitive_ambiguous)
        for name in ambiguous:
            found.pop(name, None)
        inherited_fields_cache[key] = (found, ambiguous)
        return found, ambiguous
    edges: list[JavaFieldEdge] = []
    unresolved: dict[str, list[JavaUnresolvedFieldAccess]] = {}

    ids = __import__("tmf.ids", fromlist=["stable_java_node_claim_id"])

    def accessor_id(m: ClassNode) -> str:
        return java_node_id(m)

    def field_id(f: DeclarationNode) -> str:
        return ids.stable_java_node_claim_id(f.path, f.qualname, f.declaration_kind)

    def add_edge(m: ClassNode, f: DeclarationNode, kind: str, resolution: str) -> None:
        edges.append(JavaFieldEdge(
            accessor_id=accessor_id(m),
            field_id=field_id(f),
            field_qualname=f.qualname,
            edge_kind=kind,
            resolution=resolution,
            accessor_path=m.path,
            field_path=f.path,
            accessor_hash=m.class_hash,
            field_hash=f.declaration_hash,
            accessor_qualname=m.qualname,
        ))

    def add_unresolved(m: ClassNode, expr: str, reason: str, kind: str) -> None:
        unresolved.setdefault(accessor_id(m), []).append(JavaUnresolvedFieldAccess(accessor_id=accessor_id(m), expr=expr, reason=reason, edge_kind=kind))

    def imported_field(type_name: str, field_name: str) -> tuple[DeclarationNode | None, str]:
        if repo is None or type_name not in explicit_imports:
            return None, "java_variable_or_unknown_receiver"
        target_path = explicit_imports[type_name]
        try:
            target_source = repo.read_file(target_path)
        except Exception:
            return None, "java_external_or_jdk_receiver"
        candidates = [f for f in extract_java_fields(target_path, target_source) if f.qualname == f"{type_name}.{field_name}"]
        if len(candidates) == 1:
            return candidates[0], "java_explicit_import_static_field"
        if len(candidates) > 1:
            return None, "java_ambiguous_field"
        return None, "java_field_not_found"

    def field_expr(cur: Any) -> tuple[str, str | None] | None:
        if cur.type == "field_access":
            field = _child_by_field(cur, "field")
            obj = _child_by_field(cur, "object")
            if field is not None and obj is not None:
                return _node_text(source_bytes, field), _node_text(source_bytes, obj).strip()
        if cur.type == "identifier":
            return _node_text(source_bytes, cur), None
        return None

    def visit(node: Any, stack: list[str]) -> None:
        next_stack = stack
        current_method: ClassNode | None = None
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(source_bytes, node)
            if name:
                next_stack = [*stack, name]
        elif node.type in _METHOD_TYPES:
            q = _method_qualname(source_bytes, node, stack)
            current_method = methods_by_qual.get(q or "")
        if current_method is not None:
            class_qual = current_method.qualname.rsplit(".", 1)[0]
            locals_ = _method_params_and_locals(source_bytes, node)
            class_fields = fields_by_class.get(class_qual, {})
            inherited, inherited_ambiguous = inherited_fields(path, source, class_qual)
            seen: set[tuple[str, str]] = set()
            def walk_access(cur: Any, modes: tuple[str, ...] = ("reads",)) -> None:
                # A nested executable context is not part of this method's execution.
                if cur.type == "lambda_expression":
                    text = _node_text(source_bytes, cur).strip()
                    add_unresolved(current_method, text, "java_lambda_deferred_context_not_modeled", "reads")
                    return
                if cur.type == "object_creation_expression" and any(c.type == "class_body" for c in _named_children(cur)):
                    text = _node_text(source_bytes, cur).strip()
                    add_unresolved(current_method, text, "java_anonymous_class_body_deferred_context_not_modeled", "reads")
                    # Constructor arguments execute here, but the anonymous body does not.
                    args = _child_by_field(cur, "arguments")
                    if args is not None:
                        walk_access(args)
                    return
                if cur.type == "assignment_expression":
                    left = _child_by_field(cur, "left")
                    right = _child_by_field(cur, "right")
                    operator = next((c.type for c in cur.children if not c.is_named and c.type.endswith("=")), "=")
                    if left is not None:
                        walk_access(left, ("writes",) if operator == "=" else ("reads", "writes"))
                    if right is not None:
                        walk_access(right)
                    return
                if cur.type == "update_expression":
                    for child in _named_children(cur):
                        walk_access(child, ("reads", "writes"))
                    return
                if cur.type == "variable_declarator":
                    value = _child_by_field(cur, "value")
                    if value is not None:
                        walk_access(value)
                    return
                if cur.type in {"formal_parameter", "spread_parameter", "catch_formal_parameter"}:
                    return
                # An invocation name is not a field, but its receiver and arguments may read fields.
                if cur.type == "method_invocation":
                    obj = _child_by_field(cur, "object")
                    args = _child_by_field(cur, "arguments")
                    if obj is not None:
                        walk_access(obj)
                    if args is not None:
                        walk_access(args)
                    return
                parsed = field_expr(cur)
                if parsed is not None:
                    name, receiver = parsed
                    expr = f"{receiver+'.' if receiver else ''}{name}"
                    for kind in modes:
                      key = (kind, expr)
                      if key not in seen:
                        seen.add(key)
                        if receiver == "this":
                            f = class_fields.get(name)
                            if f is not None:
                                add_edge(current_method, f, kind, "java_this_field")
                            elif name in inherited:
                                add_edge(current_method, inherited[name], kind, "java_inherited_field")
                            elif name in inherited_ambiguous:
                                add_unresolved(current_method, f"this.{name}", "java_ambiguous_inherited_field", kind)
                            else:
                                add_unresolved(current_method, f"this.{name}", "java_field_not_found", kind)
                        elif receiver is None:
                            if name in locals_:
                                add_unresolved(current_method, name, "java_local_or_parameter_shadow", kind)
                            elif name in class_fields:
                                add_edge(current_method, class_fields[name], kind, "java_same_class_static_or_field")
                            elif name in inherited:
                                add_edge(current_method, inherited[name], kind, "java_inherited_field")
                            elif name in inherited_ambiguous:
                                add_unresolved(current_method, name, "java_ambiguous_inherited_field", kind)
                        elif receiver in explicit_imports:
                            f, reason = imported_field(receiver, name)
                            if f is not None:
                                add_edge(current_method, f, kind, reason)
                            else:
                                add_unresolved(current_method, f"{receiver}.{name}", reason, kind)
                        else:
                            add_unresolved(current_method, f"{receiver}.{name}", "java_variable_receiver_field_not_resolved", kind)
                    if receiver is not None:
                        # The object expression itself is evaluated as a read.
                        obj = _child_by_field(cur, "object")
                        if obj is not None and obj.type not in {"this", "type_identifier"}:
                            walk_access(obj)
                        return
                for child in _named_children(cur):
                    walk_access(child, modes)
            body = _child_by_field(node, "body") or node
            walk_access(body)
            return
        for child in _named_children(node):
            visit(child, next_stack)

    visit(root, [])
    return edges, unresolved




@dataclass(frozen=True)
class JavaTypeUseEdge:
    user_id: str
    type_id: str
    type_qualname: str
    use_kind: str
    evidence: str = "observed"
    resolution: str = "java_type_syntax"
    user_path: str | None = None
    type_path: str | None = None
    user_hash: str | None = None
    type_hash: str | None = None
    user_qualname: str | None = None
    user_node_kind: str | None = None
    type_node_kind: str | None = "class"
    language: str = "java"


@dataclass(frozen=True)
class JavaUnresolvedTypeUse:
    user_id: str
    type_expr: str
    reason: str
    use_kind: str


_JAVA_KNOWN_EXTERNAL_TYPES = {"String", "List", "Map", "Set", "Collection", "Optional", "Integer", "Long", "Boolean", "Double", "Float", "Object", "Void"}


def _java_type_tokens(type_text: str) -> list[str]:
    from .java_types import java_type_references
    return [item.erased for item in java_type_references(type_text)]


def resolve_java_type_use_edges(path: str, source: str, java_classes: list[ClassNode], java_methods: list[ClassNode], java_fields: list[DeclarationNode], repo: Any | None = None) -> tuple[list[JavaTypeUseEdge], dict[str, list[JavaUnresolvedTypeUse]]]:
    if not path.endswith(".java"):
        return [], {}
    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    root = tree.root_node
    explicit_imports, wildcard_imports, static_imports = _java_imports(source_bytes, root)
    project_index = None
    if repo is not None:
        from .java_index import java_project_index
        project_index = java_project_index(repo)
    from .java_index import java_package
    package = java_package(source)
    ids = __import__("tmf.ids", fromlist=["stable_java_node_claim_id"])
    class_by_qual = {c.qualname: c for c in java_classes if c.node_kind in {"class", "interface", "enum"}}
    same_by_simple: dict[str, list[ClassNode]] = {}
    for c in class_by_qual.values():
        same_by_simple.setdefault(c.qualname.rsplit(".", 1)[-1], []).append(c)
    methods_by_qual = {m.qualname: m for m in java_methods if m.node_kind in {"method", "constructor"}}
    fields_by_qual = {f.qualname: f for f in java_fields}
    edges: list[JavaTypeUseEdge] = []
    unresolved: dict[str, list[JavaUnresolvedTypeUse]] = {}

    def user_id_for(kind: str, q: str) -> str:
        if kind in {"method", "constructor", "class", "interface", "enum"}:
            node_kind = kind
            return ids.stable_java_node_claim_id(path, q, node_kind)
        decl = fields_by_qual[q]
        return ids.stable_java_node_claim_id(path, q, decl.declaration_kind)

    def user_hash_for(kind: str, q: str) -> str | None:
        if kind in {"method", "constructor"} and q in methods_by_qual:
            return methods_by_qual[q].class_hash
        if kind in {"class", "interface", "enum"} and q in class_by_qual:
            return class_by_qual[q].class_hash
        if q in fields_by_qual:
            return fields_by_qual[q].declaration_hash
        return None

    def add_unresolved(uid: str, type_expr: str, reason: str, use_kind: str) -> None:
        unresolved.setdefault(uid, []).append(JavaUnresolvedTypeUse(user_id=uid, type_expr=type_expr, reason=reason, use_kind=use_kind))

    def resolve_one(type_expr: str) -> tuple[ClassNode | None, str]:
        simple = type_expr.rsplit(".", 1)[-1]
        same = same_by_simple.get(simple, [])
        if len(same) == 1:
            return same[0], "java_same_file_type"
        if len(same) > 1:
            return None, "java_ambiguous_type"
        if project_index is not None:
            symbol, resolution = project_index.resolve(type_expr, package=package, imports=explicit_imports)
            if symbol is not None:
                target_path = symbol.path
                try:
                    target_source = repo.read_file(target_path)
                except Exception:
                    return None, "java_type_not_resolved"
                candidates = [c for c in extract_java_classes(target_path, target_source) if c.qualname == symbol.simple_name]
                if len(candidates) == 1:
                    return candidates[0], f"java_{resolution}"
                return None, "java_ambiguous_type"
            if resolution == "project_ambiguous_simple_name":
                return None, "java_ambiguous_type"
        if simple in explicit_imports:
            target_path = explicit_imports[simple]
            try:
                target_source = repo.read_file(target_path)
            except Exception:
                return None, "java_external_or_jdk_type_not_resolved"
            candidates = [c for c in extract_java_classes(target_path, target_source) if c.qualname.rsplit(".", 1)[-1] == simple]
            top = [c for c in candidates if "." not in c.qualname]
            if len(top) == 1:
                return top[0], "java_explicit_import_type"
            if len(candidates) == 1:
                return candidates[0], "java_explicit_import_type"
            if candidates:
                return None, "java_ambiguous_type"
            return None, "java_external_or_jdk_type_not_resolved"
        if simple in _JAVA_KNOWN_EXTERNAL_TYPES or wildcard_imports:
            return None, "java_external_or_jdk_type_not_resolved"
        return None, "java_type_not_resolved"

    def add_type_uses(user_kind: str, user_q: str, type_text: str, use_kind: str) -> None:
        uid = user_id_for(user_kind, user_q)
        for simple in _java_type_tokens(type_text):
            target, reason = resolve_one(simple)
            if target is None:
                add_unresolved(uid, simple, reason, use_kind)
                continue
            tid = ids.stable_java_node_claim_id(target.path, target.qualname, target.node_kind)
            edges.append(JavaTypeUseEdge(
                user_id=uid, type_id=tid, type_qualname=target.qualname, use_kind=use_kind,
                resolution=reason, user_path=path, type_path=target.path,
                user_hash=user_hash_for(user_kind, user_q), type_hash=target.class_hash,
                user_qualname=user_q, user_node_kind=user_kind, type_node_kind=target.node_kind,
            ))

    def add_annotations(user_kind: str, user_q: str, roots: list[Any]) -> None:
        """Attach only annotations syntactically owned by one declaration.

        Callers pass modifiers/type/parameter subtrees rather than declaration
        bodies, preventing annotations on nested members from leaking upward.
        """
        seen: set[tuple[int, int]] = set()
        def visit_annotation(cur: Any) -> None:
            if cur.type in {"annotation", "marker_annotation"}:
                marker = (int(cur.start_byte), int(cur.end_byte))
                if marker not in seen:
                    seen.add(marker)
                    name = _java_annotation_name(source_bytes, cur)
                    if name:
                        add_type_uses(user_kind, user_q, name, "annotation_type")
                return  # nested annotation values are separate metadata, not ownership
            for child in _named_children(cur):
                visit_annotation(child)
        for root_node in roots:
            if root_node is not None:
                visit_annotation(root_node)

    def walk(node: Any, stack: list[str]) -> None:
        next_stack = stack
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(source_bytes, node)
            if name:
                q = ".".join([*stack, name])
                next_stack = [*stack, name]
                kind = class_by_qual[q].node_kind
                modifiers = next((c for c in _named_children(node) if c.type == "modifiers"), None)
                if node.type == "annotation_type_declaration":
                    # Meta-annotations have retention/target/processor meaning
                    # outside this source-only relationship slice.
                    if modifiers is not None:
                        uid = user_id_for(kind, q)
                        for annotation in _named_children(modifiers):
                            if annotation.type in {"annotation", "marker_annotation"}:
                                annotation_name = _java_annotation_name(source_bytes, annotation)
                                if annotation_name:
                                    add_unresolved(uid, annotation_name, "java_meta_annotation_not_modeled", "annotation_type")
                else:
                    add_annotations(kind, q, [modifiers])
                # superclass/interfaces are handled by inherits; field/method signatures below.
                if node.type == "record_declaration":
                    components = _child_by_field(node, "parameters")
                    if components is not None:
                        for component in _named_children(components):
                            if component.type == "formal_parameter":
                                typ = _child_by_field(component, "type")
                                if typ is not None:
                                    add_type_uses("class", q, _node_text(source_bytes, typ).strip(), "record_component_type")
                                add_annotations("class", q, [component])
        elif node.type in {"field_declaration", "constant_declaration"}:
            typ = _child_by_field(node, "type")
            if typ is not None:
                for fq in _field_qualnames(source_bytes, node, stack):
                    add_type_uses("field", fq, _node_text(source_bytes, typ).strip(), "field_type")
                    modifiers = next((c for c in _named_children(node) if c.type == "modifiers"), None)
                    add_annotations("field", fq, [modifiers, typ])
        elif node.type in _METHOD_TYPES:
            q = _method_qualname(source_bytes, node, stack)
            if q:
                user_kind = "constructor" if node.type in {"constructor_declaration", "compact_constructor_declaration"} else "method"
                ret = _child_by_field(node, "type")
                if ret is not None:
                    add_type_uses(user_kind, q, _node_text(source_bytes, ret).strip(), "return_type")
                modifiers = next((c for c in _named_children(node) if c.type == "modifiers"), None)
                annotation_roots = [modifiers, ret]
                params = _child_by_field(node, "parameters")
                if params is not None:
                    for child in _named_children(params):
                        if child.type in {"formal_parameter", "spread_parameter"}:
                            typ = _child_by_field(child, "type")
                            if typ is not None:
                                add_type_uses(user_kind, q, _node_text(source_bytes, typ).strip(), "param_type")
                            annotation_roots.append(child)
                add_annotations(user_kind, q, annotation_roots)
        for child in _named_children(node):
            walk(child, next_stack)

    walk(root, [])
    return edges, unresolved


@dataclass(frozen=True)
class JavaOverrideEdge:
    method_id: str
    overridden_id: str
    overridden_qualname: str
    evidence: str = "inferred"
    resolution: str = "java_same_file_override_candidate"
    method_path: str | None = None
    overridden_path: str | None = None
    method_hash: str | None = None
    overridden_hash: str | None = None
    method_qualname: str | None = None
    language: str = "java"


@dataclass(frozen=True)
class JavaUnresolvedOverride:
    method_id: str
    expr: str
    reason: str


def resolve_java_override_edges(path, source, java_classes, java_methods, inherit_edges, unresolved_inherits, repo=None):
    """Resolve the unique nearest source-defined ancestor method, transitively."""
    ids = __import__("tmf.ids", fromlist=["stable_java_node_claim_id"])
    edges, unresolved = [], {}
    files = {}
    parents = {}

    def load(p):
        if p in files: return files[p]
        try: text = source if p == path else repo.read_file(p)
        except Exception: return None
        cs = java_classes if p == path else extract_java_classes(p, text)
        ms = java_methods if p == path else extract_java_methods(p, text)
        files[p] = (text, cs, ms, _method_signature_index(p, text))
        return files[p]

    def direct(type_id, p):
        if type_id in parents: return parents[type_id]
        loaded = load(p)
        if not loaded: return []
        if p == path: found = [e for e in inherit_edges if e.child_id == type_id]
        elif repo is not None:
            found, _ = resolve_java_inherit_edges(p, loaded[0], loaded[1], repo=repo)
            found = [e for e in found if e.child_id == type_id]
        else: found = []
        parents[type_id] = sorted(found, key=lambda e: (e.parent_id, e.parent_path or "", e.parent_qualname))
        return parents[type_id]

    def fail(m, reason):
        item = JavaUnresolvedOverride(java_node_id(m), m.qualname.rsplit(".", 1)[-1], reason)
        if item not in unresolved.setdefault(java_node_id(m), []): unresolved[java_node_id(m)].append(item)

    load(path)
    unresolved_owners = set(unresolved_inherits)
    for m in java_methods:
        if m.node_kind != "method" or "." not in m.qualname: continue
        owner_q = m.qualname.rsplit(".", 1)[0]
        owner = next((c for c in java_classes if c.qualname == owner_q and c.node_kind in {"class", "interface"}), None)
        if not owner: continue
        owner_id = ids.stable_java_node_claim_id(path, owner.qualname, owner.node_kind)
        frontier = direct(owner_id, path)
        if not frontier:
            if owner_id in unresolved_owners: fail(m, "java_parent_type_unresolved")
            continue
        name, sig = m.qualname.rsplit(".", 1)[-1], files[path][3].get(m.qualname)
        visited, matches, ambiguous = {owner_id}, {}, False
        while frontier and not matches and not ambiguous:
            nxt = []
            for pe in frontier:
                if pe.parent_id in visited: continue
                visited.add(pe.parent_id)
                loaded = load(pe.parent_path or "")
                if not loaded: ambiguous = True; continue
                named = [x for x in loaded[2] if x.node_kind == "method" and x.qualname.rsplit(".",1)[0] == pe.parent_qualname and x.qualname.rsplit(".",1)[-1] == name]
                good = [x for x in named if sig is None or loaded[3].get(x.qualname) is None or loaded[3].get(x.qualname) == sig]
                if len(named) > 1: ambiguous = True
                elif len(good) == 1: matches[java_node_id(good[0])] = good[0]
                elif not named: nxt.extend(direct(pe.parent_id, pe.parent_path or ""))
            frontier = sorted(nxt, key=lambda e: (e.parent_id, e.parent_path or "", e.parent_qualname))
        if len(matches) == 1 and not ambiguous:
            t = next(iter(matches.values()))
            edges.append(JavaOverrideEdge(java_node_id(m), java_node_id(t), t.qualname,
                method_path=m.path, overridden_path=t.path, method_hash=m.class_hash, overridden_hash=t.class_hash,
                method_qualname=m.qualname, resolution="java_cross_file_override_candidate" if t.path != path else "java_same_file_override_candidate"))
        elif ambiguous or len(matches) > 1: fail(m, "java_overloaded_or_ambiguous_override")
    return edges, unresolved


@dataclass(frozen=True)
class JavaInheritEdge:
    child_id: str
    parent_id: str
    relation: str
    parent_qualname: str
    evidence: str = "observed"
    resolution: str = "same_file_or_explicit_import_top_level"
    child_path: str | None = None
    parent_path: str | None = None
    child_hash: str | None = None
    parent_hash: str | None = None
    child_qualname: str | None = None
    parent_node_kind: str | None = None
    child_node_kind: str | None = None


@dataclass(frozen=True)
class JavaUnresolvedInherit:
    child_id: str
    expr: str
    reason: str
    relation: str


_EXTERNAL_OR_JDK_SIMPLE_TYPES = {
    "Object", "String", "Exception", "RuntimeException", "Throwable", "Error",
    "List", "ArrayList", "LinkedList", "Map", "HashMap", "Set", "HashSet",
    "Comparable", "Comparator", "Iterable", "Collection", "Optional", "Number",
    "Integer", "Long", "Boolean", "Double", "Float", "Short", "Byte", "Character",
}


def _simple_name(name: str) -> str:
    return name.rsplit(".", 1)[-1]


def _bare_type_name(source_bytes: bytes, node: Any) -> str | None:
    """Return the syntactic bare supertype name, erasing generic arguments."""
    if node.type == "generic_type":
        for child in _named_children(node):
            if child.type in {"type_identifier", "scoped_type_identifier"}:
                return _node_text(source_bytes, child)
        return None
    if node.type in {"type_identifier", "scoped_type_identifier", "identifier", "scoped_identifier"}:
        return _node_text(source_bytes, node)
    for child in _named_children(node):
        found = _bare_type_name(source_bytes, child)
        if found:
            return found
    return None


def _type_list_names(source_bytes: bytes, node: Any | None) -> list[str]:
    if node is None:
        return []
    out: list[str] = []
    # For a superclass node, take its direct type child only.
    if node.type == "superclass":
        for child in _named_children(node):
            if child.type in {"type_identifier", "scoped_type_identifier", "generic_type"}:
                name = _bare_type_name(source_bytes, child)
                if name:
                    return [name]
        return []
    # For interface lists, collect direct entries under type_list.
    type_list = node
    if node.type in {"super_interfaces", "extends_interfaces", "permits"}:
        for child in _named_children(node):
            if child.type == "type_list":
                type_list = child
                break
    if type_list.type == "type_list":
        for child in _named_children(type_list):
            if child.type in {"type_identifier", "scoped_type_identifier", "generic_type"}:
                name = _bare_type_name(source_bytes, child)
                if name:
                    out.append(name)
    else:
        name = _bare_type_name(source_bytes, type_list)
        if name:
            out.append(name)
    return out


def _java_imports(source_bytes: bytes, root: Any) -> tuple[dict[str, str], set[str], dict[str, tuple[str, str]]]:
    """Parse Java imports.
    
    Returns:
        explicit: {simple_class_name: path_to_class.java}
        wildcard_packages: {package.name}
        static_imports: {member_simple_name: (declaring_class_simple_name, declaring_class_path)}
    """
    explicit: dict[str, str] = {}
    wildcard_packages: set[str] = set()
    static_imports: dict[str, tuple[str, str]] = {}
    
    for child in _named_children(root):
        if child.type != "import_declaration":
            continue
        text = _node_text(source_bytes, child).strip()
        body = text[len("import"):].strip().rstrip(";").strip()
        is_static = body.startswith("static ")
        if is_static:
            body = body[len("static "):].strip()
        
        if body.endswith(".*"):
            wildcard_packages.add(body[:-2])
            continue
        
        if not body:
            continue
            
        if is_static:
            # Static import: body is like "com.google.common.base.Preconditions.checkNotNull"
            # Split into declaring class and member
            if "." in body:
                declaring_class_qualname = body.rsplit(".", 1)[0]
                member_name = body.rsplit(".", 1)[1]
                declaring_class_simple = _simple_name(declaring_class_qualname)
                declaring_class_path = declaring_class_qualname.replace(".", "/") + ".java"
                static_imports[member_name] = (declaring_class_simple, declaring_class_path)
        else:
            # Regular import
            explicit[_simple_name(body)] = body.replace(".", "/") + ".java"
    
    return explicit, wildcard_packages, static_imports


def _top_level_java_types(path: str, source: str) -> dict[str, list[ClassNode]]:
    return { }


def _current_java_type_nodes(path: str, source: str) -> list[ClassNode]:
    return [node for node in extract_java_classes(path, source) if node.node_kind in {"class", "interface"}]


def _resolve_java_supertype(repo: Any, current_path: str, source: str, type_expr: str, same_file_types: dict[str, list[ClassNode]], explicit_imports: dict[str, str], wildcard_imports: set[str]) -> tuple[ClassNode | None, str]:
    simple = _simple_name(type_expr)
    same = same_file_types.get(simple, [])
    if len(same) == 1:
        return same[0], "same_file_unique"
    if len(same) > 1:
        return None, "ambiguous_type"
    from .java_index import java_package, java_project_index
    symbol, resolution = java_project_index(repo).resolve(
        type_expr, package=java_package(source), imports=explicit_imports
    )
    if symbol is not None:
        try:
            target_source = repo.read_file(symbol.path)
        except Exception:
            return None, "external_or_jdk_type"
        candidates = [node for node in _current_java_type_nodes(symbol.path, target_source) if node.qualname == symbol.simple_name]
        if len(candidates) == 1:
            return candidates[0], resolution
        return None, "ambiguous_type"
    if resolution == "project_ambiguous_simple_name":
        return None, "ambiguous_type"
    if simple in explicit_imports:
        target_path = explicit_imports[simple]
        try:
            target_source = repo.read_file(target_path)
        except Exception:
            return None, "external_or_jdk_type"
        candidates = [node for node in _current_java_type_nodes(target_path, target_source) if node.qualname.split(".")[-1] == simple]
        top_level = [node for node in candidates if "." not in node.qualname]
        if len(top_level) == 1:
            return top_level[0], "explicit_import_top_level"
        if len(top_level) > 1 or len(candidates) > 1:
            return None, "ambiguous_type"
        return None, "external_or_jdk_type"
    if wildcard_imports:
        return None, "wildcard_import"
    if type_expr.startswith("java.") or simple in _EXTERNAL_OR_JDK_SIMPLE_TYPES:
        return None, "external_or_jdk_type"
    return None, "external_or_jdk_type"


def resolve_java_inherit_edges(path: str, source: str, java_classes: list[ClassNode], repo: Any | None = None) -> tuple[list[JavaInheritEdge], dict[str, list[JavaUnresolvedInherit]]]:
    if not path.endswith(".java") or repo is None:
        return [], {}
    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    tree = parser.parse(source_bytes)
    root = tree.root_node
    explicit_imports, wildcard_imports, static_imports = _java_imports(source_bytes, root)
    type_nodes = [node for node in java_classes if node.node_kind in {"class", "interface"}]
    by_qual = {node.qualname: node for node in type_nodes}
    same_file_by_simple: dict[str, list[ClassNode]] = {}
    for node in type_nodes:
        same_file_by_simple.setdefault(node.qualname.split(".")[-1], []).append(node)
    edges: list[JavaInheritEdge] = []
    unresolved: dict[str, list[JavaUnresolvedInherit]] = {}

    def visit(node: Any, stack: list[str]) -> None:
        next_stack = stack
        if node.type in {"class_declaration", "interface_declaration", "record_declaration"}:
            name = _identifier_from_node(source_bytes, node)
            if name:
                qualname = ".".join([*stack, name])
                next_stack = [*stack, name]
                child = by_qual.get(qualname)
                if child is not None and child.node_kind in {"class", "interface"}:
                    child_id = __import__("tmf.ids", fromlist=["stable_java_node_claim_id"]).stable_java_node_claim_id(child.path, child.qualname, child.node_kind)
                    specs: list[tuple[str, str]] = []
                    if node.type == "class_declaration":
                        for expr in _type_list_names(source_bytes, _child_by_field(node, "superclass")):
                            specs.append(("extends", expr))
                        super_ifaces = next((c for c in _named_children(node) if c.type == "super_interfaces"), None)
                        for expr in _type_list_names(source_bytes, super_ifaces):
                            specs.append(("implements", expr))
                    elif node.type == "interface_declaration":
                        ext_ifaces = next((c for c in _named_children(node) if c.type == "extends_interfaces"), None)
                        for expr in _type_list_names(source_bytes, ext_ifaces):
                            specs.append(("extends", expr))
                    elif node.type == "record_declaration":
                        super_ifaces = next((c for c in _named_children(node) if c.type == "super_interfaces"), None)
                        for expr in _type_list_names(source_bytes, super_ifaces):
                            specs.append(("implements", expr))
                    for relation, expr in specs:
                        parent, reason = _resolve_java_supertype(repo, path, source, expr, same_file_by_simple, explicit_imports, wildcard_imports)
                        if parent is None:
                            unresolved.setdefault(child_id, []).append(JavaUnresolvedInherit(child_id=child_id, expr=_simple_name(expr), reason=reason, relation=relation))
                            continue
                        parent_id = __import__("tmf.ids", fromlist=["stable_java_node_claim_id"]).stable_java_node_claim_id(parent.path, parent.qualname, parent.node_kind)
                        edges.append(JavaInheritEdge(
                            child_id=child_id,
                            parent_id=parent_id,
                            relation=relation,
                            parent_qualname=parent.qualname,
                            resolution=reason,
                            child_path=child.path,
                            parent_path=parent.path,
                            child_hash=child.class_hash,
                            parent_hash=parent.class_hash,
                            child_qualname=child.qualname,
                            child_node_kind=child.node_kind,
                            parent_node_kind=parent.node_kind,
                        ))
                    permits = next((c for c in _named_children(node) if c.type == "permits"), None)
                    for expr in _type_list_names(source_bytes, permits):
                        permitted, reason = _resolve_java_supertype(repo, path, source, expr, same_file_by_simple, explicit_imports, wildcard_imports)
                        if permitted is None:
                            unresolved.setdefault(child_id, []).append(JavaUnresolvedInherit(child_id=child_id, expr=_simple_name(expr), reason=reason, relation="permits"))
                            continue
                        permitted_id = __import__("tmf.ids", fromlist=["stable_java_node_claim_id"]).stable_java_node_claim_id(permitted.path, permitted.qualname, permitted.node_kind)
                        edges.append(JavaInheritEdge(
                            child_id=permitted_id, parent_id=child_id, relation="permits",
                            parent_qualname=child.qualname, resolution=reason,
                            child_path=permitted.path, parent_path=child.path,
                            child_hash=permitted.class_hash, parent_hash=child.class_hash,
                            child_qualname=permitted.qualname, child_node_kind=permitted.node_kind,
                            parent_node_kind=child.node_kind,
                        ))
        for child_node in _named_children(node):
            visit(child_node, next_stack)

    visit(root, [])
    return edges, unresolved


def _first_descendant_text(source_bytes: bytes, node: Any, types: set[str]) -> str | None:
    if node.type in types:
        return _node_text(source_bytes, node)
    for child in _named_children(node):
        found = _first_descendant_text(source_bytes, child, types)
        if found is not None:
            return found
    return None


def _java_method_node_for(source: str, method: ClassNode) -> Any | None:
    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    root = parser.parse(source_bytes).root_node
    stack: list[str] = []
    found = None
    def walk(node: Any, st: list[str]) -> None:
        nonlocal found
        if found is not None:
            return
        next_stack = st
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(source_bytes, node)
            if name:
                next_stack = [*st, name]
        elif node.type in _METHOD_TYPES:
            q = _method_qualname(source_bytes, node, st)
            if q == method.qualname and _line_start(node) == method.line_start:
                found = node
                return
        for child in _named_children(node):
            walk(child, next_stack)
    walk(root, stack)
    return found


def _java_method_interface_from_node(source_bytes: bytes, node: Any) -> dict[str, Any]:
    params: list[dict[str, str | None]] = []
    throws: list[str] = []
    annotations: list[str] = []
    modifiers: list[str] = []
    return_type: str | None = None
    for child in _children(node):
        if child.type == "modifiers":
            for m in _children(child):
                if m.type == "marker_annotation":
                    txt = _node_text(source_bytes, m).strip().lstrip("@")
                    annotations.append(txt.split("(", 1)[0])
                elif m.type in {"public", "private", "protected", "static", "final", "abstract", "synchronized", "native"}:
                    modifiers.append(m.type)
        elif child.type in {"void_type", "integral_type", "floating_point_type", "boolean_type", "type_identifier", "generic_type", "scoped_type_identifier"} and return_type is None:
            return_type = _node_text(source_bytes, child)
        elif child.type == "formal_parameters":
            for pnode in _named_children(child):
                if pnode.type not in {"formal_parameter", "spread_parameter"}:
                    continue
                name_node = _child_by_field(pnode, "name")
                type_node = _child_by_field(pnode, "type")
                params.append({"name": _node_text(source_bytes, name_node) if name_node is not None else None, "type": _node_text(source_bytes, type_node) if type_node is not None else None})
        elif child.type == "throws":
            for t in _named_children(child):
                txt = _bare_type_name(source_bytes, t)
                if txt:
                    throws.append(_simple_name(txt))
    # Literal raises inside the body also count as observed raise names.
    def walk_throws(cur: Any) -> None:
        if cur.type == "throw_statement":
            txt = _first_descendant_text(source_bytes, cur, {"type_identifier", "identifier"})
            if txt and txt not in throws:
                throws.append(_simple_name(txt))
        for ch in _named_children(cur):
            walk_throws(ch)
    walk_throws(node)
    return {"language": "java", "signature": _node_text(source_bytes, node).split("{",1)[0].strip(), "params": params, "return_type": return_type, "throws": sorted(set(throws)), "modifiers": sorted(set(modifiers)), "annotations": sorted(set(annotations))}


@lru_cache(maxsize=512)
def _java_method_interface_index(source: str) -> dict[tuple[str, int], dict[str, Any]]:
    _language, parser = _language_and_parser()
    source_bytes = source.encode("utf-8")
    root = parser.parse(source_bytes).root_node
    out: dict[tuple[str, int], dict[str, Any]] = {}

    def walk(node: Any, stack: list[str]) -> None:
        next_stack = stack
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(source_bytes, node)
            if name:
                next_stack = [*stack, name]
        elif node.type in _METHOD_TYPES:
            q = _method_qualname(source_bytes, node, stack)
            if q:
                out[(q, _line_start(node))] = _java_method_interface_from_node(source_bytes, node)
        for child in _named_children(node):
            walk(child, next_stack)

    walk(root, [])
    return out


def java_method_interface(source: str, method: ClassNode) -> dict[str, Any]:
    return dict(_java_method_interface_index(source).get((method.qualname, method.line_start), {}))



@dataclass(frozen=True)
class JavaInjectEdge:
    injector_id: str
    bean_id: str
    bean_qualname: str
    inject_kind: str
    evidence: str = "attributed"
    confidence: float = 0.55
    resolution: str = "spring_autowired_field_type"
    injector_path: str | None = None
    bean_path: str | None = None
    injector_hash: str | None = None
    bean_hash: str | None = None
    injector_qualname: str | None = None
    injector_node_kind: str | None = "class"
    bean_node_kind: str | None = "class"


@dataclass(frozen=True)
class JavaUnresolvedInject:
    injector_id: str
    type_expr: str
    reason: str
    inject_kind: str
    candidates: list[str] | None = None
    expr: str | None = None
    annotation: str | None = None
    qualname: str | None = None
    bucket: str | None = None


@dataclass(frozen=True)
class JavaTopicEdge:
    source_id: str
    topic_name: str
    edge_kind: str
    evidence: str = "attributed"
    confidence: float = 0.5
    resolution: str = "spring_kafka_literal_topic"
    source_path: str | None = None
    source_hash: str | None = None
    source_qualname: str | None = None
    dependency_path: str | None = None
    dependency_qualname: str | None = None
    group_id: str | None = None
    payload_type: str | None = None


@dataclass(frozen=True)
class JavaUnresolvedTopic:
    source_id: str
    expr: str
    reason: str
    edge_kind: str
    annotation: str | None = None
    qualname: str | None = None
    bucket: str | None = None


@dataclass(frozen=True)
class JavaEventTypeEdge:
    source_id: str
    type_id: str
    type_qualname: str
    edge_kind: str
    source_path: str
    source_hash: str
    source_qualname: str
    type_path: str
    type_hash: str
    type_node_kind: str
    anchor_hash: str
    annotation_kind: str | None = None
    metadata: dict[str, Any] | None = None
    resolution: str = "java_source_observed_event_type"


@dataclass(frozen=True)
class JavaUnresolvedEventType:
    source_id: str
    expr: str
    reason: str
    edge_kind: str


@dataclass(frozen=True)
class JavaConfigurationPropertiesBinding:
    source_id: str
    prefix: str
    target_kind: str
    source_path: str
    source_hash: str
    source_qualname: str
    evidence: str = "attributed"
    confidence: float = 0.55
    resolution: str = "spring_configuration_properties_literal"


@dataclass(frozen=True)
class JavaUnresolvedConfigurationProperties:
    source_id: str
    expr: str
    reason: str


def resolve_java_spring_declarations(path: str, source: str, java_classes: list[ClassNode], java_methods: list[ClassNode]) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, str]]]]:
    """Extract declaration-only Spring metadata from exact explicit imports."""
    if not path.endswith(".java"):
        return {}, {}
    import re
    ids = __import__('tmf.ids', fromlist=['stable_java_node_claim_id'])
    imports = _java_explicit_imports(source)
    exact = {"Profile":"org.springframework.context.annotation.Profile", "Conditional":"org.springframework.context.annotation.Conditional", "ConditionalOnProperty":"org.springframework.boot.autoconfigure.condition.ConditionalOnProperty", "ConditionalOnClass":"org.springframework.boot.autoconfigure.condition.ConditionalOnClass", "Scope":"org.springframework.context.annotation.Scope", "Lazy":"org.springframework.context.annotation.Lazy", "DependsOn":"org.springframework.context.annotation.DependsOn", "Primary":"org.springframework.context.annotation.Primary", "Transactional":"org.springframework.transaction.annotation.Transactional"}
    lines = source.splitlines(); metadata: dict[str, dict[str, Any]] = {}; unresolved: dict[str, list[dict[str, str]]] = {}
    def strings(arg: str) -> list[str] | None:
        arg = re.sub(r"^(?:value|name)\s*=\s*", "", arg.strip())
        if re.fullmatch(r'"[^"\\]*"', arg): return [arg[1:-1]]
        if re.fullmatch(r'\{\s*"[^"\\]*"(?:\s*,\s*"[^"\\]*")*\s*\}', arg): return re.findall(r'"([^"\\]*)"', arg)
        return None
    for node in [*java_classes, *java_methods]:
        if node.node_kind not in {"class", "interface", "record", "method", "constructor"}: continue
        node_id = ids.stable_java_node_claim_id(path, node.identity_key or node.qualname, node.node_kind)
        snippet = '\n'.join(lines[max(0, node.line_start - 9):min(len(lines), node.line_start + 1)])
        found: dict[str, Any] = {"coverage":"partial", "effect":"declaration_only", "confidence":0.6}; bad: list[dict[str, str]] = []
        for name, fqn in exact.items():
            if not re.search(r'@' + name + r'\b', snippet): continue
            if imports.get(name) != fqn: bad.append({"annotation":name,"reason":"spring_annotation_not_exact_explicit_import"}); continue
            matches = list(re.finditer(r'@' + name + r'(?:\s*\((.*?)\))?', snippet, re.S)); match = matches[-1] if matches else None; args = match.group(1) if match else None
            if name == "Primary": found["primary"] = True
            elif name == "Lazy":
                if args is None or args.strip() == "true": found["lazy"] = True
                elif args.strip() == "false": found["lazy"] = False
                else: bad.append({"annotation":name,"reason":"spring_annotation_value_dynamic"})
            elif name in {"Profile","Scope","DependsOn"}:
                vals = strings(args or "")
                if vals is None or any("${" in x or "#{" in x for x in vals): bad.append({"annotation":name,"reason":"spring_annotation_value_spel_or_dynamic"})
                else: found[{"Profile":"profiles","Scope":"scope","DependsOn":"depends_on"}[name]] = vals if name != "Scope" else vals[0]
            elif name == "Transactional":
                tx: dict[str, Any] = {"boundary":"method" if node.node_kind in {"method","constructor"} else "class"}; valid = True
                for part in [x.strip() for x in (args or "").split(',') if x.strip()]:
                    if re.fullmatch(r'readOnly\s*=\s*(?:true|false)', part): tx["read_only"] = part.endswith("true")
                    elif (m := re.fullmatch(r'(propagation|isolation)\s*=\s*(?:Propagation|Isolation)\.([A-Z_]+)', part)): tx[m.group(1)] = m.group(2)
                    else: valid = False
                if valid: found["transactional"] = tx
                else: bad.append({"annotation":name,"reason":"spring_transaction_attribute_dynamic_or_unsupported"})
            else:
                vals = strings(args or "")
                if vals is not None: found.setdefault("conditions", []).append({"annotation":name,"literal_values":vals})
                else: bad.append({"annotation":name,"reason":"spring_condition_classpath_or_dynamic_deferred"})
        if len(found) > 3: metadata[node_id] = found
        if bad: unresolved[node_id] = bad
    return metadata, unresolved


def resolve_java_configuration_properties(path: str, source: str, java_classes: list[ClassNode], java_methods: list[ClassNode]) -> tuple[list[JavaConfigurationPropertiesBinding], dict[str, list[JavaUnresolvedConfigurationProperties]]]:
    """Extract declaration metadata only; this deliberately models no binder execution."""
    if not path.endswith('.java'):
        return [], {}
    import re
    imports = _java_explicit_imports(source)
    if imports.get('ConfigurationProperties') != 'org.springframework.boot.context.properties.ConfigurationProperties':
        return [], {}
    ids = __import__('tmf.ids', fromlist=['stable_java_node_claim_id'])
    lines = source.splitlines()
    bindings: list[JavaConfigurationPropertiesBinding] = []
    unresolved: dict[str, list[JavaUnresolvedConfigurationProperties]] = {}

    def annotation(snippet: str) -> tuple[str | None, str | None]:
        match = re.search(r'@ConfigurationProperties\s*\((.*?)\)', snippet, re.S)
        if not match:
            return None, None
        args = match.group(1).strip()
        literal = re.fullmatch(r'(?:prefix\s*=\s*|value\s*=\s*)?"([^"\\]*)"', args)
        return (literal.group(1), None) if literal else (None, args)

    for node in java_classes:
        if node.node_kind != 'class':
            continue
        start = max(0, node.line_start - 8)
        snippet = '\n'.join(lines[start:node.line_start])
        declaration = re.search(r'@ConfigurationProperties\s*\(([^)]*)\)[^;{}]*?(?:public\s+|protected\s+|private\s+)?(?:class|record)\s+' + re.escape(node.qualname.rsplit('.', 1)[-1]) + r'\b', snippet, re.S)
        if not declaration:
            continue
        snippet = '@ConfigurationProperties(' + declaration.group(1) + ')'
        source_id = ids.stable_java_node_claim_id(path, node.qualname, node.node_kind, node.identity_key)
        prefix, bad = annotation(snippet)
        if prefix is not None:
            bindings.append(JavaConfigurationPropertiesBinding(source_id, prefix, node.node_kind, path, node.class_hash, node.qualname))
        else:
            unresolved.setdefault(source_id, []).append(JavaUnresolvedConfigurationProperties(source_id, bad or '@ConfigurationProperties', 'spring_configuration_properties_prefix_not_literal'))

    for node in java_methods:
        if node.node_kind != 'method':
            continue
        start = max(0, node.line_start - 8)
        snippet = '\n'.join(lines[start:node.line_start])
        method_name = node.qualname.rsplit('.', 1)[-1]
        declaration = re.search(r'@ConfigurationProperties\s*\(([^)]*)\)[^;{}]*?(?:public\s+|protected\s+|private\s+)?[A-Za-z_]\w*(?:<[^>]+>)?\s+' + re.escape(method_name) + r'\s*\(', snippet, re.S)
        if not declaration:
            continue
        annotation_snippet = '@ConfigurationProperties(' + declaration.group(1) + ')'
        source_id = ids.stable_java_node_claim_id(path, node.qualname, node.node_kind, node.identity_key)
        prefix, bad = annotation(annotation_snippet)
        # Factory identity is supported only when @Bean itself is exact and explicit.
        if imports.get('Bean') != 'org.springframework.context.annotation.Bean' or not re.search(r'@Bean(?:\s*\([^)]*\))?', snippet):
            unresolved.setdefault(source_id, []).append(JavaUnresolvedConfigurationProperties(source_id, bad or '@ConfigurationProperties', 'spring_configuration_properties_factory_not_explicit_bean'))
        elif prefix is None:
            unresolved.setdefault(source_id, []).append(JavaUnresolvedConfigurationProperties(source_id, bad or '@ConfigurationProperties', 'spring_configuration_properties_prefix_not_literal'))
        else:
            bindings.append(JavaConfigurationPropertiesBinding(source_id, prefix, 'factory_method', path, node.class_hash, node.qualname, resolution='spring_configuration_properties_literal_factory'))
    return bindings, unresolved


def _java_class_annotations_regex(source: str) -> dict[str, set[str]]:
    import re
    anns: dict[str, set[str]] = {}
    pat = re.compile(r"((?:@\w+(?:\([^)]*\))?\s*)*)(?:public\s+)?(?:class|interface)\s+(\w+)")
    for m in pat.finditer(source):
        names = set(re.findall(r"@(\w+)", m.group(1) or ""))
        anns[m.group(2)] = names
    return anns


def _java_implements_regex(source: str) -> dict[str, list[str]]:
    import re
    out: dict[str, list[str]] = {}
    for m in re.finditer(r"(?:class)\s+(\w+)\s+implements\s+([^\{]+)\{", source):
        out[m.group(1)] = [x.strip().split()[-1] for x in m.group(2).split(',') if x.strip()]
    return out


def resolve_java_inject_edges(path: str, source: str, java_classes: list[ClassNode], java_fields: list[DeclarationNode], inherit_edges: list[JavaInheritEdge] | None = None, repo: Any | None = None, java_methods: list[ClassNode] | None = None) -> tuple[list[JavaInjectEdge], dict[str, list[JavaUnresolvedInject]]]:
    """Conservative source-only Spring injection evidence.

    Supported annotations must have an exact fully-qualified spelling or exact
    explicit import.  Simple-name lookalikes, wildcard/classpath-only symbols,
    interface assignability, scanning, and runtime bean naming are not guessed.
    """
    if not path.endswith('.java'):
        return [], {}
    import re
    ids = __import__('tmf.ids', fromlist=['stable_java_node_claim_id'])
    lines = source.splitlines()
    imports = _java_explicit_imports(source)
    spring = {
        'Component': 'org.springframework.stereotype.Component',
        'Service': 'org.springframework.stereotype.Service',
        'Repository': 'org.springframework.stereotype.Repository',
        'Controller': 'org.springframework.stereotype.Controller',
        'Configuration': 'org.springframework.context.annotation.Configuration',
        'ConfigurationProperties': 'org.springframework.boot.context.properties.ConfigurationProperties',
        'Autowired': 'org.springframework.beans.factory.annotation.Autowired',
        'Inject': {'javax.inject.Inject', 'jakarta.inject.Inject'},
        'Qualifier': 'org.springframework.beans.factory.annotation.Qualifier',
        'Bean': 'org.springframework.context.annotation.Bean',
        'Primary': 'org.springframework.context.annotation.Primary',
    }
    def genuine(name: str) -> bool:
        target = spring[name]
        imported = imports.get(name)
        return imported in target if isinstance(target, set) else imported == target
    anns = _java_class_annotations_regex(source)
    bean_ann = {'Component','Service','Repository','Controller','Configuration','ConfigurationProperties'}
    class_by_simple = {c.qualname.rsplit('.',1)[-1]: c for c in java_classes if c.node_kind in {'class','interface'}}
    component_beans = {simple: c for simple, c in class_by_simple.items()
                       if any(a in anns.get(simple, set()) and genuine(a) for a in bean_ann)}
    exact_injection_present = any(
        genuine(name) and re.search(rf"@{name}\b", source)
        for name in ("Autowired", "Inject")
    )
    resource_import = imports.get("Resource")
    exact_injection_present = exact_injection_present or (
        resource_import in {"javax.annotation.Resource", "jakarta.annotation.Resource"}
        and re.search(r"@Resource\b", source) is not None
    )
    # Project-wide, tracked-source bean registry. This is not package scanning:
    # only declarations carrying exact explicitly imported annotations enter it.
    bean_candidates: list[tuple[str, ClassNode, str | None]] = []
    bean_assignable_types: dict[tuple[str, str, str], set[str]] = {}
    primary_candidate_keys: set[tuple[str, str, str]] = set()
    project_sources = [(path, source, java_classes, java_methods or [])]
    if repo is not None and exact_injection_present:
        from .java_project import java_repository_snapshot
        project_sources = []
        snapshot = java_repository_snapshot(repo)
        for candidate_path in snapshot.paths:
            candidate_source = snapshot.texts.get(candidate_path)
            if candidate_source is None:
                continue
            project_sources.append((candidate_path, candidate_source,
                                    list(snapshot.classes.get(candidate_path, ())),
                                    list(snapshot.methods.get(candidate_path, ()))))
    for candidate_path, candidate_source, candidate_classes, candidate_methods in project_sources:
        candidate_imports = _java_explicit_imports(candidate_source)
        candidate_package = _java_package(candidate_source) or ''
        candidate_anns = _java_class_annotations_regex(candidate_source)
        def candidate_genuine(name: str) -> bool:
            target = spring[name]; imported = candidate_imports.get(name)
            return imported in target if isinstance(target, set) else imported == target
        candidate_by_simple = {c.qualname.rsplit('.', 1)[-1]: c for c in candidate_classes if c.node_kind in {'class','interface'}}
        for simple, node in candidate_by_simple.items():
            if any(a in candidate_anns.get(simple, set()) and candidate_genuine(a) for a in bean_ann):
                candidate_fqn = f'{candidate_package}.{simple}' if candidate_package else simple
                bean_candidates.append((candidate_fqn, node, simple[:1].lower()+simple[1:]))
                assignable = {candidate_fqn}
                for iface in _java_implements_regex(candidate_source).get(simple, []):
                    if repo is None:
                        assignable.add(iface)
                    else:
                        from .java_index import java_project_index
                        imported_iface = candidate_imports.get(iface)
                        if imported_iface:
                            assignable.add(imported_iface)
                        else:
                            symbol, _ = java_project_index(repo).resolve(iface, package=candidate_package, imports=candidate_imports)
                            if symbol is not None:
                                assignable.add(symbol.fqn)
                bean_assignable_types[(node.path, node.qualname, node.node_kind)] = assignable
                if candidate_genuine('Primary') and 'Primary' in candidate_anns.get(simple, set()): primary_candidate_keys.add((node.path, node.qualname, node.node_kind))
        candidate_lines = candidate_source.splitlines()
        for method in candidate_methods:
            if method.node_kind != 'method' or not candidate_genuine('Bean'): continue
            snippet = '\n'.join(candidate_lines[method.line_start-1:method.line_end]); method_name=method.qualname.rsplit('.',1)[-1]
            match = re.search(r'@Bean(?:\s*\(\s*(?:name\s*=\s*)?"([^"]+)"\s*\))?(?:\s*@Primary\b)?\s+(?:public\s+|protected\s+|private\s+)?([A-Za-z_]\w*)\s+'+re.escape(method_name)+r'\s*\(', snippet)
            if not match: continue
            if repo is None:
                return_fqn = match.group(2) if match.group(2) in candidate_by_simple else None
            else:
                from .java_index import java_project_index
                symbol, _ = java_project_index(repo).resolve(match.group(2), package=candidate_package, imports=candidate_imports)
                return_fqn = symbol.fqn if symbol else None
            if return_fqn:
                bean_candidates.append((return_fqn, method, match.group(1) or method_name))
                if candidate_genuine('Primary') and re.search(r'@Primary\b', snippet): primary_candidate_keys.add((method.path, method.qualname, method.node_kind))
    def primary_only(nodes: list[ClassNode]) -> ClassNode | None:
        selected = [n for n in nodes if (n.path, n.qualname, n.node_kind) in primary_candidate_keys]
        return selected[0] if len(selected) == 1 else None
    def injection_fqn(type_name: str) -> str | None:
        if repo is None: return type_name if type_name in class_by_simple else None
        from .java_index import java_package, java_project_index
        symbol, _ = java_project_index(repo).resolve(type_name, package=java_package(source), imports=imports)
        return symbol.fqn if symbol else None
    method_snippets: dict[str, str] = {}
    for method in java_methods or []:
        snippet = '\n'.join(lines[method.line_start - 1:method.line_end])
        method_snippets[method.identity_key or method.qualname] = snippet
        method_name = method.qualname.rsplit('.', 1)[-1]
    implements = _java_implements_regex(source)
    impls_by_iface: dict[str, list[ClassNode]] = {}
    for impl_simple, ifaces in implements.items():
        if impl_simple in component_beans:
            for iface in ifaces:
                impls_by_iface.setdefault(iface, []).append(component_beans[impl_simple])
    fields_by_owner: dict[str, list[DeclarationNode]] = {}
    for field in java_fields:
        owner = field.qualname.rsplit('.', 1)[0] if '.' in field.qualname else ''
        fields_by_owner.setdefault(owner, []).append(field)
    edges: list[JavaInjectEdge] = []
    unresolved: dict[str, list[JavaUnresolvedInject]] = {}
    seen: set[tuple[str,str,str]] = set()
    # Narrow trust-model guard: field annotations with injection-role vocabulary
    # are unknown unless they are one of the exact supported FQNs. Arbitrary
    # annotations remain true negatives.
    role_names = re.compile(r"(?:Inject|Autowired|Resource)$")
    exact_injection_names = {name for name in ("Autowired", "Inject") if genuine(name)}
    if resource_import in {"javax.annotation.Resource", "jakarta.annotation.Resource"}:
        exact_injection_names.add("Resource")
    explicitly_imported = _java_explicit_imports(source)
    for field in java_fields:
        owner = field.qualname.rsplit('.', 1)[0] if '.' in field.qualname else ''
        cls = class_by_simple.get(owner)
        if cls is None or not (0 < field.line_start <= len(lines)):
            continue
        line = lines[field.line_start - 1]
        for annotation in re.findall(r"@([A-Za-z_$][\w$]*)\b", line):
            imported = explicitly_imported.get(annotation)
            if role_names.search(annotation) and annotation not in exact_injection_names:
                injector_id = ids.stable_java_node_claim_id(path, cls.qualname, cls.node_kind)
                unresolved.setdefault(injector_id, []).append(JavaUnresolvedInject(
                    injector_id, field.qualname.rsplit('.', 1)[-1], "injection_annotation_not_recognized", "field", [],
                    expr=line.strip(), annotation=annotation, qualname=field.qualname, bucket="dependency_injection",
                ))
    for owner, fields in fields_by_owner.items():
        cls = class_by_simple.get(owner)
        if cls is None:
            continue
        injector_id = ids.stable_java_node_claim_id(path, cls.qualname, cls.node_kind)
        for field in fields:
            line = lines[field.line_start-1] if 0 < field.line_start <= len(lines) else ''
            has_inject = ('@Autowired' in line and genuine('Autowired')) or ('@Inject' in line and genuine('Inject'))
            if not has_inject:
                continue
            fm = re.search(r"(?:@(?:Autowired|Inject)\s+)(?:@Qualifier\(\s*\"[^\"]+\"\s*\)\s+)?(?:private\s+|public\s+|protected\s+)?([A-Za-z_][A-Za-z0-9_]*)\s+([A-Za-z_][A-Za-z0-9_]*)\s*;", line)
            if not fm:
                continue
            typ = fm.group(1)
            resolved_type = injection_fqn(typ)
            typed = [(node, name) for candidate_type, node, name in bean_candidates
                     if resolved_type is not None and resolved_type in bean_assignable_types.get(
                         (node.path, node.qualname, node.node_kind), {candidate_type})]
            target = typed[0][0] if len(typed) == 1 else None
            qualifier = re.search(r'@Qualifier\(\s*"([^"]+)"\s*\)', line) if genuine('Qualifier') else None
            if qualifier:
                literal = qualifier.group(1)
                named = [node for candidate_type, node, name in bean_candidates if resolved_type is not None and candidate_type == resolved_type and name == literal]
                if len(named) != 1:
                    unresolved.setdefault(injector_id, []).append(JavaUnresolvedInject(injector_id, typ, 'spring_qualifier_literal_not_unique', 'field', [x.qualname for x in named]))
                    continue
                target = named[0]
            elif len(typed) > 1:
                target = primary_only([node for node, _ in typed])
            reason = 'spring_autowired_field_type'
            candidates: list[str] = []
            # This first slice permits exact declared type only. Interface
            # assignability requires a project-wide bean registry/schema pass.
            if target is None and typ in class_by_simple and class_by_simple[typ].node_kind == 'interface':
                impls = impls_by_iface.get(typ, [])
                candidates = [x.qualname for x in impls]
                if len(impls) > 1:
                    unresolved.setdefault(injector_id, []).append(JavaUnresolvedInject(injector_id, typ, 'spring_interface_multiple_beans', 'field', candidates))
                    continue
            if target is None:
                reason = 'spring_injection_multiple_beans' if len(typed) > 1 else 'spring_injection_type_not_resolved'
                unresolved.setdefault(injector_id, []).append(JavaUnresolvedInject(injector_id, typ, reason, 'field', [x[0].qualname for x in typed] or candidates))
                continue
            bean_id = ids.stable_java_node_claim_id(target.path, target.qualname, target.node_kind)
            key=(injector_id, bean_id, 'field')
            if key in seen:
                continue
            seen.add(key)
            edges.append(JavaInjectEdge(injector_id, bean_id, target.qualname, 'field', resolution=reason, injector_path=cls.path, bean_path=target.path, injector_hash=cls.class_hash, bean_hash=target.class_hash, injector_qualname=cls.qualname, bean_node_kind=target.node_kind))

    # Explicitly annotated constructors and methods.  Parameter types must be
    # plain, source-declared identifiers; containers/generics/providers are
    # deliberately left unresolved rather than unwrapped.
    for method in java_methods or []:
        if method.node_kind not in {'constructor', 'method'}:
            continue
        snippet = method_snippets.get(method.identity_key or method.qualname, '')
        method_name = method.qualname.rsplit('.', 1)[-1]
        annotated = re.search(r'@(?:Autowired|Inject)\b[\s\S]*?\b' + re.escape(method_name) + r'\s*\(((?:[^()]|\([^()]*\))*)\)\s*(?:throws\s+[^\{]+)?\{', snippet)
        if not annotated or not ((re.search(r'@Autowired\b', annotated.group(0)) and genuine('Autowired')) or
                (re.search(r'@Inject\b', annotated.group(0)) and genuine('Inject'))):
            continue
        owner = method.qualname.rsplit('.', 1)[0]
        cls = class_by_simple.get(owner)
        if cls is None:
            continue
        injector_id = ids.stable_java_node_claim_id(path, cls.qualname, cls.node_kind)
        inject_kind = 'constructor' if method.node_kind == 'constructor' else 'method'
        for raw_param in [p.strip() for p in annotated.group(1).split(',') if p.strip()]:
            q = re.search(r'@Qualifier\(\s*"([^"]+)"\s*\)', raw_param) if genuine('Qualifier') else None
            clean = re.sub(r'@\w+(?:\([^)]*\))?\s*', '', raw_param).strip()
            mparam = re.fullmatch(r'(?:final\s+)?([A-Za-z_]\w*)\s+[A-Za-z_]\w*', clean)
            if not mparam:
                unresolved.setdefault(injector_id, []).append(JavaUnresolvedInject(injector_id, clean, 'spring_injection_parameter_not_plain_type', inject_kind, []))
                continue
            typ = mparam.group(1)
            resolved_type = injection_fqn(typ)
            typed = [(node, name) for candidate_type, node, name in bean_candidates
                     if resolved_type is not None and resolved_type in bean_assignable_types.get(
                         (node.path, node.qualname, node.node_kind), {candidate_type})]
            selected = [node for node, name in typed if q and name == q.group(1)] if q else [node for node, _ in typed]
            if not q and len(selected) > 1:
                primary = primary_only(selected)
                selected = [primary] if primary is not None else selected
            if len(selected) != 1:
                reason = 'spring_qualifier_literal_not_unique' if q else ('spring_injection_multiple_beans' if len(selected) > 1 else 'spring_injection_type_not_resolved')
                unresolved.setdefault(injector_id, []).append(JavaUnresolvedInject(injector_id, typ, reason, inject_kind, [x.qualname for x in selected or [n for n, _ in typed]]))
                continue
            target = selected[0]
            bean_id = ids.stable_java_node_claim_id(target.path, target.identity_key or target.qualname, target.node_kind)
            key = (injector_id, bean_id, inject_kind)
            if key in seen:
                continue
            seen.add(key)
            resolution = f'spring_explicit_{inject_kind}_primary' if (target.path, target.qualname, target.node_kind) in primary_candidate_keys and len(typed) > 1 and not q else f'spring_explicit_{inject_kind}_type'
            edges.append(JavaInjectEdge(injector_id, bean_id, target.qualname, inject_kind, resolution=resolution, injector_path=cls.path, bean_path=target.path, injector_hash=cls.class_hash, bean_hash=target.class_hash, injector_qualname=cls.qualname, bean_node_kind=target.node_kind))
    return edges, unresolved

def _java_package(source: str) -> str | None:
    import re
    match = re.search(r"(?m)^\s*package\s+([A-Za-z_][\w.]*)\s*;", source)
    return match.group(1) if match else None


def _java_explicit_imports(source: str) -> dict[str, str]:
    import re
    return {name.rsplit('.', 1)[-1]: name for name in re.findall(r"(?m)^\s*import\s+([A-Za-z_][\w.]*)\s*;", source)}


def resolve_java_cache_declarations(path: str, source: str, methods: list[ClassNode]) -> tuple[list[JavaCacheDeclaration], dict[str, list[JavaUnresolvedCacheDeclaration]]]:
    """Extract declaration-only Spring Cache metadata; never interpret SpEL/runtime effects."""
    imports = _java_explicit_imports(source)
    fqn = "org.springframework.cache.annotation."
    exact = {name for name in ("Cacheable", "CachePut", "CacheEvict") if imports.get(name) == fqn + name}
    if not exact:
        return [], {}
    _language, parser = _language_and_parser(); data = source.encode("utf-8"); tree = parser.parse(data)
    by_q: dict[str, list[ClassNode]] = {}
    for method in methods: by_q.setdefault(method.qualname, []).append(method)
    found: list[JavaCacheDeclaration] = []; unresolved: dict[str, list[JavaUnresolvedCacheDeclaration]] = {}

    def reject(mid: str, ann: Any, reason: str) -> None:
        unresolved.setdefault(mid, []).append(JavaUnresolvedCacheDeclaration(mid, _node_text(data, ann), reason))

    def parse(ann: Any) -> tuple[tuple[str, ...] | None, dict[str, str | None], str | None]:
        args = _java_annotation_args(ann); names: list[str] | None = None; opaque = {"key": None, "condition": None, "unless": None}
        if len(args) == 1 and args[0].type in {"string_literal", "element_value_array_initializer"}:
            values = _java_literal_string_array(data, args[0]); return (tuple(values) if values else None), opaque, None if values else "cache_names_not_literal"
        for arg in args:
            if arg.type != "element_value_pair": return None, opaque, "unsupported_annotation_argument"
            children = _named_children(arg); key_node = _child_by_field(arg, "key") or (children[0] if children else None); val = _child_by_field(arg, "value")
            if key_node is None or val is None: return None, opaque, "malformed_annotation_argument"
            key = _node_text(data, key_node)
            if key in {"value", "cacheNames"}:
                values = _java_literal_string_array(data, val)
                if not values: return None, opaque, "cache_names_not_literal"
                if names is not None and names != values: return None, opaque, "conflicting_cache_name_aliases"
                names = values
            elif key in opaque:
                value = _java_string_literal_value(data, val)
                if value is None: return None, opaque, f"{key}_not_literal"
                opaque[key] = value
            else:
                return None, opaque, f"unsupported_cache_attribute:{key}"
        return (tuple(names) if names else None), opaque, None if names else "cache_names_missing"

    def walk(node: Any, stack: list[str]) -> None:
        ns = stack
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(data, node); ns = [*stack, name] if name else stack
        elif node.type == "method_declaration":
            q = _method_qualname(data, node, stack); candidates = by_q.get(q or "", [])
            if len(candidates) > 1:
                node_hash = java_hash_for_node(source, node)
                candidates = [candidate for candidate in candidates if candidate.class_hash == node_hash]
            anns = [a for a in _java_annotations(node) if _java_annotation_name(data, a) in exact]
            if anns and q:
                mid = java_node_id(candidates[0]) if len(candidates) == 1 else f"unresolved:{path}:{q}"
                if len(candidates) != 1:
                    for ann in anns: reject(mid, ann, "method_overload_ambiguous")
                else:
                    for ann in anns:
                        names, opaque, reason = parse(ann)
                        if reason: reject(mid, ann, reason); continue
                        found.append(JavaCacheDeclaration(mid, q, path, _java_annotation_name(data, ann) or "", names or (), opaque["key"], opaque["condition"], opaque["unless"], _line_start(ann), _line_end(ann), java_hash_for_node(source, ann), candidates[0].class_hash))
        for child in _named_children(node): walk(child, ns)
    walk(tree.root_node, [])
    return sorted(found, key=lambda x: (x.method_id, x.line_start, x.operation)), unresolved


def resolve_java_scheduling_declarations(path: str, source: str, methods: list[ClassNode]) -> tuple[list[JavaSchedulingDeclaration], dict[str, list[JavaUnresolvedSchedulingDeclaration]]]:
    """Extract only literal @Scheduled source declarations; never model execution."""
    imports = _java_explicit_imports(source)
    exact = imports.get("Scheduled") == "org.springframework.scheduling.annotation.Scheduled"
    if "@Scheduled" not in source:
        return [], {}
    _language, parser = _language_and_parser(); data = source.encode("utf-8"); tree = parser.parse(data)
    by_q: dict[str, list[ClassNode]] = {}
    for method in methods: by_q.setdefault(method.qualname, []).append(method)
    found: list[JavaSchedulingDeclaration] = []; unresolved: dict[str, list[JavaUnresolvedSchedulingDeclaration]] = {}

    def reject(mid: str, ann: Any, reason: str) -> None:
        unresolved.setdefault(mid, []).append(JavaUnresolvedSchedulingDeclaration(mid, _node_text(data, ann), reason))

    def parse(ann: Any) -> tuple[dict[str, str | None], str | None]:
        values = {k: None for k in ("fixedRate", "fixedDelay", "initialDelay", "cron", "zone", "timeUnit")}
        for arg in _java_annotation_args(ann):
            if arg.type != "element_value_pair": return values, "spring_scheduled_unsupported_positional_argument"
            children = _named_children(arg); key_node = _child_by_field(arg, "key") or (children[0] if children else None); val = _child_by_field(arg, "value")
            if key_node is None or val is None: return values, "spring_scheduled_malformed_argument"
            key = _node_text(data, key_node); raw = _node_text(data, val).strip()
            if key not in values: return values, f"spring_scheduled_unsupported_attribute:{key}"
            if values[key] is not None: return values, f"spring_scheduled_conflicting_attribute:{key}"
            if key in {"cron", "zone"}:
                literal = _java_string_literal_value(data, val)
                if literal is None: return values, f"spring_scheduled_{key}_not_literal"
                if "${" in literal or "#{" in literal:
                    return values, f"spring_scheduled_{key}_dynamic_expression_unsupported"
                values[key] = literal
            elif key == "timeUnit":
                if not re.fullmatch(r"(?:java\.util\.concurrent\.)?TimeUnit\.[A-Z_]+", raw):
                    return values, "spring_scheduled_timeUnit_not_literal"
                values[key] = raw
            else:
                # Preserve the Java token spelling; signs, constants, arithmetic and strings fail closed.
                if not re.fullmatch(r"[0-9][0-9_]*[lL]?", raw):
                    return values, f"spring_scheduled_{key}_not_literal"
                values[key] = raw
        if not any(values[k] is not None for k in ("fixedRate", "fixedDelay", "cron")):
            return values, "spring_scheduled_trigger_missing"
        if sum(values[k] is not None for k in ("fixedRate", "fixedDelay", "cron")) != 1:
            return values, "spring_scheduled_conflicting_triggers"
        return values, None

    def walk(node: Any, stack: list[str]) -> None:
        ns = stack
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(data, node); ns = [*stack, name] if name else stack
        elif node.type == "method_declaration":
            q = _method_qualname(data, node, stack); candidates = by_q.get(q or "", [])
            if len(candidates) > 1:
                node_hash = java_hash_for_node(source, node); candidates = [x for x in candidates if x.class_hash == node_hash]
            anns = [a for a in _java_annotations(node) if _java_annotation_name(data, a) == "Scheduled"]
            if anns and q:
                mid = java_node_id(candidates[0]) if len(candidates) == 1 else f"unresolved:{path}:{q}"
                for ann in anns:
                    if not exact: reject(mid, ann, "spring_scheduled_annotation_not_exact_explicit_import"); continue
                    if len(candidates) != 1: reject(mid, ann, "spring_scheduled_method_overload_ambiguous"); continue
                    values, reason = parse(ann)
                    if reason: reject(mid, ann, reason); continue
                    found.append(JavaSchedulingDeclaration(mid, q, path, values["fixedRate"], values["fixedDelay"], values["initialDelay"], values["cron"], values["zone"], values["timeUnit"], _line_start(ann), _line_end(ann), java_hash_for_node(source, ann), candidates[0].class_hash))
        for child in _named_children(node): walk(child, ns)
    walk(tree.root_node, [])
    return sorted(found, key=lambda x: (x.method_id, x.line_start)), unresolved


def resolve_java_transaction_declarations(path: str, source: str, classes: list[ClassNode], methods: list[ClassNode]) -> tuple[list[JavaTransactionDeclaration], dict[str, list[JavaUnresolvedTransactionDeclaration]]]:
    """Retain direct literal @Transactional syntax only; never infer transaction semantics."""
    if "@Transactional" not in source:
        return [], {}
    exact = (_java_explicit_imports(source).get("Transactional") == "org.springframework.transaction.annotation.Transactional"
             and re.search(r"@interface\s+Transactional\b", source) is None)
    _language, parser = _language_and_parser(); data = source.encode("utf-8"); tree = parser.parse(data)
    candidates: dict[tuple[str, str], list[ClassNode]] = {}
    for item in [*classes, *methods]: candidates.setdefault((item.qualname, item.node_kind), []).append(item)
    found: list[JavaTransactionDeclaration] = []; unresolved: dict[str, list[JavaUnresolvedTransactionDeclaration]] = {}

    def reject(owner_id: str, ann: Any, reason: str) -> None:
        unresolved.setdefault(owner_id, []).append(JavaUnresolvedTransactionDeclaration(owner_id, _node_text(data, ann), reason))

    def string_array(node: Any) -> tuple[str, ...] | None:
        values = _java_literal_string_array(data, node)
        if not values or any("${" in x or "#{" in x for x in values): return None
        return tuple(values)

    def class_array(node: Any) -> tuple[str, ...] | None:
        nodes = _named_children(node) if node.type == "element_value_array_initializer" else [node]
        values = tuple(_node_text(data, x).strip() for x in nodes)
        return values if values and all(re.fullmatch(r"(?:[A-Za-z_$][\w$]*\.)*[A-Za-z_$][\w$]*\.class", x) for x in values) else None

    def parse(ann: Any) -> tuple[dict[str, Any], str | None]:
        out: dict[str, Any] = {"propagation":None,"isolation":None,"read_only":None,"timeout":None,"transaction_manager":None,"rollback_for":(),"no_rollback_for":(),"rollback_for_class_name":(),"no_rollback_for_class_name":()}
        seen: set[str] = set()
        for arg in _java_annotation_args(ann):
            if arg.type != "element_value_pair":
                if seen: return out, "spring_transaction_conflicting_manager_aliases"
                value = _java_string_literal_value(data, arg)
                if value is None or "${" in value or "#{" in value: return out, "spring_transaction_value_not_literal_string"
                seen.add("value"); out["transaction_manager"] = value; continue
            children = _named_children(arg); key_node = _child_by_field(arg, "key") or (children[0] if children else None); val = _child_by_field(arg, "value")
            if key_node is None or val is None: return out, "spring_transaction_malformed_attribute"
            key = _node_text(data, key_node); raw = _node_text(data, val).strip()
            if key in seen: return out, f"spring_transaction_conflicting_attribute:{key}"
            seen.add(key)
            if key in {"propagation","isolation"}:
                prefix = "Propagation" if key == "propagation" else "Isolation"
                m = re.fullmatch(rf"(?:org\.springframework\.transaction\.annotation\.)?{prefix}\.([A-Z_]+)", raw)
                if not m: return out, f"spring_transaction_{key}_not_literal_enum"
                out[key] = m.group(1)
            elif key == "readOnly":
                if raw not in {"true","false"}: return out, "spring_transaction_readOnly_not_literal_boolean"
                out["read_only"] = raw == "true"
            elif key == "timeout":
                if not re.fullmatch(r"-?(?:0|[1-9][0-9_]*)", raw): return out, "spring_transaction_timeout_not_literal_int"
                out["timeout"] = raw
            elif key in {"value","transactionManager"}:
                value = _java_string_literal_value(data, val)
                if value is None or "${" in value or "#{" in value: return out, f"spring_transaction_{key}_not_literal_string"
                if out["transaction_manager"] is not None and out["transaction_manager"] != value: return out, "spring_transaction_conflicting_manager_aliases"
                out["transaction_manager"] = value
            elif key in {"rollbackFor","noRollbackFor"}:
                value = class_array(val)
                if value is None: return out, f"spring_transaction_{key}_not_class_literals"
                out["rollback_for" if key == "rollbackFor" else "no_rollback_for"] = value
            elif key in {"rollbackForClassName","noRollbackForClassName"}:
                value = string_array(val)
                if value is None: return out, f"spring_transaction_{key}_not_literal_names"
                out["rollback_for_class_name" if key == "rollbackForClassName" else "no_rollback_for_class_name"] = value
            else: return out, f"spring_transaction_unsupported_attribute:{key}"
        return out, None

    def walk(node: Any, stack: list[str]) -> None:
        ns = stack; q: str | None = None; kind: str | None = None
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(data, node); ns = [*stack, name] if name else stack; q = ".".join(ns); kind = "interface" if node.type == "interface_declaration" else ("record" if node.type == "record_declaration" else "class")
        elif node.type == "method_declaration": q = _method_qualname(data, node, stack); kind = "method"
        if q and kind:
            anns = [a for a in _java_annotations(node) if _java_annotation_name(data, a) == "Transactional"]
            if anns:
                pool = candidates.get((q, kind), [])
                if len(pool) > 1: pool = [x for x in pool if x.class_hash == java_hash_for_node(source, node)]
                owner_id = java_node_id(pool[0]) if len(pool) == 1 else f"unresolved:{path}:{q}:{kind}"
                if not exact:
                    for ann in anns: reject(owner_id, ann, "spring_transaction_annotation_not_exact_explicit_import")
                elif len(anns) != 1:
                    for ann in anns: reject(owner_id, ann, "spring_transaction_duplicate_annotation")
                elif len(pool) != 1: reject(owner_id, anns[0], "spring_transaction_owner_ambiguous")
                else:
                    values, reason = parse(anns[0])
                    if reason: reject(owner_id, anns[0], reason)
                    else: found.append(JavaTransactionDeclaration(owner_id,q,kind,path,values["propagation"],values["isolation"],values["read_only"],values["timeout"],values["transaction_manager"],values["rollback_for"],values["no_rollback_for"],values["rollback_for_class_name"],values["no_rollback_for_class_name"],_line_start(anns[0]),_line_end(anns[0]),java_hash_for_node(source,anns[0]),pool[0].class_hash))
        for child in _named_children(node): walk(child, ns)
    walk(tree.root_node, [])
    return sorted(found,key=lambda x:(x.owner_id,x.line_start)), unresolved


def resolve_java_async_declarations(path: str, source: str, classes: list[ClassNode], methods: list[ClassNode]) -> tuple[list[JavaAsyncDeclaration], dict[str, list[JavaUnresolvedAsyncDeclaration]]]:
    """Retain direct @Async declarations and literal qualifiers; infer no execution semantics."""
    if "@Async" not in source:
        return [], {}
    imports = re.findall(r"(?m)^\s*import\s+(?!static\b)([A-Za-z_][\w.]*)\s*;", source)
    async_imports = [name for name in imports if name.rsplit(".", 1)[-1] == "Async"]
    all_async_imports = re.findall(r"\bimport\s+(?:static\s+)?([^;]*Async[^;]*)\s*;", source)
    exact = (async_imports == ["org.springframework.scheduling.annotation.Async"]
             and all_async_imports == ["org.springframework.scheduling.annotation.Async"]
             and re.search(r"@interface\s+Async\b", source) is None)
    _language, parser = _language_and_parser(); data = source.encode("utf-8"); tree = parser.parse(data)
    candidates: dict[tuple[str, str], list[ClassNode]] = {}
    for item in [*classes, *methods]: candidates.setdefault((item.qualname, item.node_kind), []).append(item)
    found: list[JavaAsyncDeclaration] = []; unresolved: dict[str, list[JavaUnresolvedAsyncDeclaration]] = {}

    def reject(owner_id: str, ann: Any, reason: str) -> None:
        unresolved.setdefault(owner_id, []).append(JavaUnresolvedAsyncDeclaration(owner_id, _node_text(data, ann), reason))

    def parse(ann: Any) -> tuple[str | None, str | None]:
        args = _java_annotation_args(ann)
        if not args:
            return None, None
        qualifier: str | None = None
        seen: set[str] = set()
        for arg in args:
            if arg.type == "element_value_pair":
                children = _named_children(arg); key_node = _child_by_field(arg, "key") or (children[0] if children else None); val = _child_by_field(arg, "value")
                if key_node is None or val is None: return None, "spring_async_malformed_attribute"
                key = _node_text(data, key_node)
                if key not in {"value", "executor"}: return None, f"spring_async_unsupported_attribute:{key}"
            else:
                key, val = "value", arg
            if key in seen: return None, f"spring_async_conflicting_attribute:{key}"
            seen.add(key)
            value = _java_string_literal_value(data, val)
            if value is None or "${" in value or "#{" in value: return None, f"spring_async_{key}_not_literal_string"
            if qualifier is not None and qualifier != value: return None, "spring_async_conflicting_executor_aliases"
            qualifier = value
        return qualifier, None

    def walk(node: Any, stack: list[str]) -> None:
        ns = stack; q: str | None = None; kind: str | None = None
        if node.type in _CLASS_TYPES:
            name = _identifier_from_node(data, node); ns = [*stack, name] if name else stack; q = ".".join(ns)
            kind = "interface" if node.type == "interface_declaration" else ("record" if node.type == "record_declaration" else "class")
        elif node.type == "method_declaration": q = _method_qualname(data, node, stack); kind = "method"
        if q and kind:
            anns = [a for a in _java_annotations(node) if _java_annotation_name(data, a) == "Async"]
            if anns:
                pool = candidates.get((q, kind), [])
                if len(pool) > 1: pool = [x for x in pool if x.class_hash == java_hash_for_node(source, node)]
                owner_id = java_node_id(pool[0]) if len(pool) == 1 else f"unresolved:{path}:{q}:{kind}"
                if not exact:
                    for ann in anns: reject(owner_id, ann, "spring_async_annotation_not_exact_explicit_import")
                elif len(anns) != 1:
                    for ann in anns: reject(owner_id, ann, "spring_async_duplicate_annotation")
                elif len(pool) != 1: reject(owner_id, anns[0], "spring_async_owner_ambiguous")
                else:
                    qualifier, reason = parse(anns[0])
                    if reason: reject(owner_id, anns[0], reason)
                    else: found.append(JavaAsyncDeclaration(owner_id,q,kind,path,qualifier,_line_start(anns[0]),_line_end(anns[0]),java_hash_for_node(source,anns[0]),pool[0].class_hash))
        for child in _named_children(node): walk(child, ns)
    walk(tree.root_node, [])
    return sorted(found,key=lambda x:(x.owner_id,x.line_start)), unresolved


def resolve_java_retry_declarations(path: str, source: str, classes: list[ClassNode], methods: list[ClassNode]) -> tuple[list[JavaRetryDeclaration], dict[str, list[JavaUnresolvedRetryDeclaration]]]:
    """Retain direct Spring Retry literals; infer no retry/recovery behavior."""
    if "@Retryable" not in source and "@Recover" not in source: return [], {}
    imports = re.findall(r"(?m)^\s*import\s+(?!static\b)([A-Za-z_][\w.]*)\s*;", source)
    raw_imports = re.findall(r"\bimport\s+(?:static\s+)?([^;]*(?:Retryable|Recover)[^;]*)\s*;", source)
    expected={"Retryable":"org.springframework.retry.annotation.Retryable","Recover":"org.springframework.retry.annotation.Recover"}
    exact={n: imports.count(f)==1 and len([x for x in imports if x.rsplit('.',1)[-1]==n])==1 and f in raw_imports for n,f in expected.items()}
    if any('*' in x or x not in expected.values() for x in raw_imports) or re.search(r"@interface\s+(?:Retryable|Recover)\b",source): exact={n:False for n in exact}
    _,parser=_language_and_parser();data=source.encode();tree=parser.parse(data); candidates={}
    for item in [*classes,*methods]:candidates.setdefault((item.qualname,item.node_kind),[]).append(item)
    found=[];unresolved={}
    def reject(owner,ann,reason):unresolved.setdefault(owner,[]).append(JavaUnresolvedRetryDeclaration(owner,_node_text(data,ann),reason))
    def class_array(node):
        nodes=_named_children(node) if node.type=='element_value_array_initializer' else [node];vals=tuple(_node_text(data,x).strip() for x in nodes)
        return vals if vals and all(re.fullmatch(r"(?:[A-Za-z_$][\w$]*\.)*[A-Za-z_$][\w$]*\.class",x) for x in vals) else None
    def strings(node):
        vals=_java_literal_string_array(data,node)
        return tuple(vals) if vals and all('${' not in x and '#{' not in x for x in vals) else None
    def parse(ann):
        out={"retry_for":(),"no_retry_for":(),"max_attempts":None,"max_attempts_expression":None,"exception_expression":None,"label":None,"stateful":None,"interceptor":None,"listeners":()};seen=set();aliases={"value":"retry_for","include":"retry_for","retryFor":"retry_for","exclude":"no_retry_for","noRetryFor":"no_retry_for"}
        for arg in _java_annotation_args(ann):
            if arg.type!='element_value_pair':return out,'spring_retry_retryable_unnamed_attribute'
            ch=_named_children(arg);kn=_child_by_field(arg,'key') or (ch[0] if ch else None);val=_child_by_field(arg,'value')
            if kn is None or val is None:return out,'spring_retry_malformed_attribute'
            key=_node_text(data,kn);canonical=aliases.get(key,key)
            if key in seen or canonical in seen:return out,f'spring_retry_conflicting_attribute:{key}'
            seen|={key,canonical};raw=_node_text(data,val).strip()
            if canonical in {'retry_for','no_retry_for'}:
                v=class_array(val)
                if v is None:return out,f'spring_retry_{key}_not_class_literals'
                out[canonical]=v
            elif key=='maxAttempts':
                if not re.fullmatch(r'(?:0|[1-9][0-9_]*)',raw):return out,'spring_retry_maxAttempts_not_literal_int'
                out['max_attempts']=raw
            elif key=='stateful':
                if raw not in {'true','false'}:return out,'spring_retry_stateful_not_literal_boolean'
                out['stateful']=raw=='true'
            elif key=='listeners':
                v=strings(val)
                if v is None:return out,'spring_retry_listeners_not_literal_strings'
                out['listeners']=v
            elif key in {'maxAttemptsExpression','exceptionExpression','label','interceptor'}:
                v=_java_string_literal_value(data,val)
                if v is None or '${' in v or '#{' in v:return out,f'spring_retry_{key}_not_literal_string'
                out[{'maxAttemptsExpression':'max_attempts_expression','exceptionExpression':'exception_expression'}.get(key,key)]=v
            else:return out,f'spring_retry_unsupported_attribute:{key}'
        return out,None
    def walk(node,stack):
        ns=stack;q=None;kind=None
        if node.type in _CLASS_TYPES:
            n=_identifier_from_node(data,node);ns=[*stack,n] if n else stack;q='.'.join(ns);kind='interface' if node.type=='interface_declaration' else ('record' if node.type=='record_declaration' else 'class')
        elif node.type=='method_declaration':q=_method_qualname(data,node,stack);kind='method'
        if q and kind:
            for name in ('Retryable','Recover'):
                anns=[a for a in _java_annotations(node) if _java_annotation_name(data,a)==name]
                if not anns:continue
                pool=candidates.get((q,kind),[])
                if len(pool)>1:pool=[x for x in pool if x.class_hash==java_hash_for_node(source,node)]
                owner=java_node_id(pool[0]) if len(pool)==1 else f'unresolved:{path}:{q}:{kind}'
                if not exact[name]:
                    for a in anns:reject(owner,a,'spring_retry_annotation_not_exact_explicit_import')
                elif len(anns)!=1:
                    for a in anns:reject(owner,a,'spring_retry_duplicate_annotation')
                elif len(pool)!=1:reject(owner,anns[0],'spring_retry_owner_ambiguous')
                elif name=='Recover' and _java_annotation_args(anns[0]):reject(owner,anns[0],'spring_retry_recover_unsupported_attribute')
                else:
                    metadata,reason=parse(anns[0]) if name=='Retryable' else ({},None)
                    if reason:reject(owner,anns[0],reason)
                    else:found.append(JavaRetryDeclaration(owner,q,kind,name.lower(),path,metadata,_line_start(anns[0]),_line_end(anns[0]),java_hash_for_node(source,anns[0]),pool[0].class_hash))
        for child in _named_children(node):walk(child,ns)
    walk(tree.root_node,[]);return sorted(found,key=lambda x:(x.owner_id,x.annotation_kind)),unresolved


def resolve_java_circuit_breaker_declarations(path: str, source: str, classes: list[ClassNode], methods: list[ClassNode]) -> tuple[list[JavaCircuitBreakerDeclaration], dict[str, list[JavaUnresolvedCircuitBreakerDeclaration]]]:
    """Retain direct Resilience4j CircuitBreaker literals; infer no runtime behavior."""
    if "@CircuitBreaker" not in source: return [], {}
    expected = "io.github.resilience4j.circuitbreaker.annotation.CircuitBreaker"
    imports = re.findall(r"(?m)^\s*import\s+(?!static\b)([A-Za-z_][\w.]*)\s*;", source)
    raw = re.findall(r"\bimport\s+(?:static\s+)?([^;]*CircuitBreaker[^;]*)\s*;", source)
    exact = imports.count(expected) == 1 and [x for x in imports if x.rsplit('.',1)[-1]=='CircuitBreaker'] == [expected] and raw == [expected] and re.search(r"@interface\s+CircuitBreaker\b",source) is None
    _,parser=_language_and_parser();data=source.encode();tree=parser.parse(data);candidates={}
    for item in [*classes,*methods]: candidates.setdefault((item.qualname,item.node_kind),[]).append(item)
    found=[];unresolved={}
    def reject(owner,ann,reason): unresolved.setdefault(owner,[]).append(JavaUnresolvedCircuitBreakerDeclaration(owner,_node_text(data,ann),reason))
    def parse(ann):
        values={};seen=set()
        for arg in _java_annotation_args(ann):
            if arg.type!='element_value_pair': return None,'resilience4j_circuit_breaker_unnamed_attribute'
            ch=_named_children(arg);kn=_child_by_field(arg,'key') or (ch[0] if ch else None);val=_child_by_field(arg,'value')
            if kn is None or val is None:return None,'resilience4j_circuit_breaker_malformed_attribute'
            key=_node_text(data,kn)
            if key not in {'name','fallbackMethod'}:return None,f'resilience4j_circuit_breaker_unsupported_attribute:{key}'
            if key in seen:return None,f'resilience4j_circuit_breaker_duplicate_attribute:{key}'
            seen.add(key);value=_java_string_literal_value(data,val)
            if value is None or '${' in value or '#{' in value:return None,f'resilience4j_circuit_breaker_{key}_not_literal_string'
            values[key]=value
        if not values.get('name'):return None,'resilience4j_circuit_breaker_name_missing_or_empty'
        return values,None
    def walk(node,stack):
        ns=stack;q=None;kind=None
        if node.type in _CLASS_TYPES:
            n=_identifier_from_node(data,node);ns=[*stack,n] if n else stack;q='.'.join(ns);kind='interface' if node.type=='interface_declaration' else ('record' if node.type=='record_declaration' else 'class')
        elif node.type=='method_declaration':q=_method_qualname(data,node,stack);kind='method'
        if q and kind:
            anns=[a for a in _java_annotations(node) if _java_annotation_name(data,a)=='CircuitBreaker']
            if anns:
                pool=candidates.get((q,kind),[])
                if len(pool)>1:pool=[x for x in pool if x.class_hash==java_hash_for_node(source,node)]
                owner=java_node_id(pool[0]) if len(pool)==1 else f'unresolved:{path}:{q}:{kind}'
                if not exact:
                    for a in anns:reject(owner,a,'resilience4j_circuit_breaker_annotation_not_exact_explicit_import')
                elif len(anns)!=1:
                    for a in anns:reject(owner,a,'resilience4j_circuit_breaker_duplicate_annotation')
                elif len(pool)!=1:reject(owner,anns[0],'resilience4j_circuit_breaker_owner_ambiguous')
                else:
                    values,reason=parse(anns[0])
                    if reason:reject(owner,anns[0],reason)
                    else:found.append(JavaCircuitBreakerDeclaration(owner,q,kind,path,values['name'],values.get('fallbackMethod'),_line_start(anns[0]),_line_end(anns[0]),java_hash_for_node(source,anns[0]),pool[0].class_hash))
        for child in _named_children(node):walk(child,ns)
    walk(tree.root_node,[]);return sorted(found,key=lambda x:x.owner_id),unresolved


def resolve_java_rate_limiter_declarations(path: str, source: str, classes: list[ClassNode], methods: list[ClassNode]) -> tuple[list[JavaRateLimiterDeclaration], dict[str, list[JavaUnresolvedRateLimiterDeclaration]]]:
    """Retain direct Resilience4j RateLimiter literals; infer no runtime behavior."""
    if "@RateLimiter" not in source: return [], {}
    expected = "io.github.resilience4j.ratelimiter.annotation.RateLimiter"
    imports = re.findall(r"(?m)^\s*import\s+(?!static\b)([A-Za-z_][\w.]*)\s*;", source)
    raw = re.findall(r"\bimport\s+(?:static\s+)?([^;]*RateLimiter[^;]*)\s*;", source)
    exact = imports.count(expected) == 1 and [x for x in imports if x.rsplit('.',1)[-1]=='RateLimiter'] == [expected] and raw == [expected] and re.search(r"@interface\s+RateLimiter\b",source) is None
    _,parser=_language_and_parser();data=source.encode();tree=parser.parse(data);candidates={}
    for item in [*classes,*methods]: candidates.setdefault((item.qualname,item.node_kind),[]).append(item)
    found=[];unresolved={}
    def reject(owner,ann,reason): unresolved.setdefault(owner,[]).append(JavaUnresolvedRateLimiterDeclaration(owner,_node_text(data,ann),reason))
    def parse(ann):
        values={};seen=set()
        for arg in _java_annotation_args(ann):
            if arg.type!='element_value_pair': return None,'resilience4j_rate_limiter_unnamed_attribute'
            ch=_named_children(arg);kn=_child_by_field(arg,'key') or (ch[0] if ch else None);val=_child_by_field(arg,'value')
            if kn is None or val is None:return None,'resilience4j_rate_limiter_malformed_attribute'
            key=_node_text(data,kn)
            if key not in {'name','fallbackMethod'}:return None,f'resilience4j_rate_limiter_unsupported_attribute:{key}'
            if key in seen:return None,f'resilience4j_rate_limiter_duplicate_attribute:{key}'
            seen.add(key);value=_java_string_literal_value(data,val)
            if value is None or '${' in value or '#{' in value:return None,f'resilience4j_rate_limiter_{key}_not_literal_string'
            values[key]=value
        if not values.get('name'):return None,'resilience4j_rate_limiter_name_missing_or_empty'
        return values,None
    def walk(node,stack):
        ns=stack;q=None;kind=None
        if node.type in _CLASS_TYPES:
            n=_identifier_from_node(data,node);ns=[*stack,n] if n else stack;q='.'.join(ns);kind='interface' if node.type=='interface_declaration' else ('record' if node.type=='record_declaration' else 'class')
        elif node.type=='method_declaration':q=_method_qualname(data,node,stack);kind='method'
        if q and kind:
            anns=[a for a in _java_annotations(node) if _java_annotation_name(data,a)=='RateLimiter']
            if anns:
                pool=candidates.get((q,kind),[])
                if len(pool)>1:pool=[x for x in pool if x.class_hash==java_hash_for_node(source,node)]
                owner=java_node_id(pool[0]) if len(pool)==1 else f'unresolved:{path}:{q}:{kind}'
                if not exact:
                    for a in anns:reject(owner,a,'resilience4j_rate_limiter_annotation_not_exact_explicit_import')
                elif len(anns)!=1:
                    for a in anns:reject(owner,a,'resilience4j_rate_limiter_duplicate_annotation')
                elif len(pool)!=1:reject(owner,anns[0],'resilience4j_rate_limiter_owner_ambiguous')
                else:
                    values,reason=parse(anns[0])
                    if reason:reject(owner,anns[0],reason)
                    else:found.append(JavaRateLimiterDeclaration(owner,q,kind,path,values['name'],values.get('fallbackMethod'),_line_start(anns[0]),_line_end(anns[0]),java_hash_for_node(source,anns[0]),pool[0].class_hash))
        for child in _named_children(node):walk(child,ns)
    walk(tree.root_node,[]);return sorted(found,key=lambda x:x.owner_id),unresolved


def resolve_java_bulkhead_declarations(path: str, source: str, classes: list[ClassNode], methods: list[ClassNode]) -> tuple[list[JavaBulkheadDeclaration], dict[str, list[JavaUnresolvedBulkheadDeclaration]]]:
    """Retain direct Resilience4j Bulkhead literals; infer no runtime behavior."""
    if "@Bulkhead" not in source: return [], {}
    expected = "io.github.resilience4j.bulkhead.annotation.Bulkhead"
    imports = re.findall(r"(?m)^\s*import\s+(?!static\b)([A-Za-z_][\w.]*)\s*;", source)
    raw = re.findall(r"\bimport\s+(?:static\s+)?([^;]*Bulkhead[^;]*)\s*;", source)
    exact = imports.count(expected) == 1 and [x for x in imports if x.rsplit('.',1)[-1]=='Bulkhead'] == [expected] and raw == [expected] and re.search(r"@interface\s+Bulkhead\b",source) is None
    _,parser=_language_and_parser();data=source.encode();tree=parser.parse(data);candidates={}
    for item in [*classes,*methods]: candidates.setdefault((item.qualname,item.node_kind),[]).append(item)
    found=[];unresolved={}
    def reject(owner,ann,reason): unresolved.setdefault(owner,[]).append(JavaUnresolvedBulkheadDeclaration(owner,_node_text(data,ann),reason))
    def parse(ann):
        values={};seen=set()
        for arg in _java_annotation_args(ann):
            if arg.type!='element_value_pair': return None,'resilience4j_bulkhead_unnamed_attribute'
            ch=_named_children(arg);kn=_child_by_field(arg,'key') or (ch[0] if ch else None);val=_child_by_field(arg,'value')
            if kn is None or val is None:return None,'resilience4j_bulkhead_malformed_attribute'
            key=_node_text(data,kn)
            if key not in {'name','fallbackMethod'}:return None,f'resilience4j_bulkhead_unsupported_attribute:{key}'
            if key in seen:return None,f'resilience4j_bulkhead_duplicate_attribute:{key}'
            seen.add(key);value=_java_string_literal_value(data,val)
            if value is None or '${' in value or '#{' in value:return None,f'resilience4j_bulkhead_{key}_not_literal_string'
            values[key]=value
        if not values.get('name'):return None,'resilience4j_bulkhead_name_missing_or_empty'
        return values,None
    def walk(node,stack):
        ns=stack;q=None;kind=None
        if node.type in _CLASS_TYPES:
            n=_identifier_from_node(data,node);ns=[*stack,n] if n else stack;q='.'.join(ns);kind='interface' if node.type=='interface_declaration' else ('record' if node.type=='record_declaration' else 'class')
        elif node.type=='method_declaration':q=_method_qualname(data,node,stack);kind='method'
        if q and kind:
            anns=[a for a in _java_annotations(node) if _java_annotation_name(data,a)=='Bulkhead']
            if anns:
                pool=candidates.get((q,kind),[])
                if len(pool)>1:pool=[x for x in pool if x.class_hash==java_hash_for_node(source,node)]
                owner=java_node_id(pool[0]) if len(pool)==1 else f'unresolved:{path}:{q}:{kind}'
                if not exact:
                    for a in anns:reject(owner,a,'resilience4j_bulkhead_annotation_not_exact_explicit_import')
                elif len(anns)!=1:
                    for a in anns:reject(owner,a,'resilience4j_bulkhead_duplicate_annotation')
                elif len(pool)!=1:reject(owner,anns[0],'resilience4j_bulkhead_owner_ambiguous')
                else:
                    values,reason=parse(anns[0])
                    if reason:reject(owner,anns[0],reason)
                    else:found.append(JavaBulkheadDeclaration(owner,q,kind,path,values['name'],values.get('fallbackMethod'),_line_start(anns[0]),_line_end(anns[0]),java_hash_for_node(source,anns[0]),pool[0].class_hash))
        for child in _named_children(node):walk(child,ns)
    walk(tree.root_node,[]);return sorted(found,key=lambda x:x.owner_id),unresolved


def resolve_java_time_limiter_declarations(path: str, source: str, classes: list[ClassNode], methods: list[ClassNode]) -> tuple[list[JavaTimeLimiterDeclaration], dict[str, list[JavaUnresolvedTimeLimiterDeclaration]]]:
    """Retain direct Resilience4j TimeLimiter literals; infer no runtime behavior."""
    if "@TimeLimiter" not in source: return [], {}
    expected = "io.github.resilience4j.timelimiter.annotation.TimeLimiter"
    imports = re.findall(r"(?m)^\s*import\s+(?!static\b)([A-Za-z_][\w.]*)\s*;", source)
    raw = re.findall(r"\bimport\s+(?:static\s+)?([^;]*TimeLimiter[^;]*)\s*;", source)
    exact = imports.count(expected) == 1 and [x for x in imports if x.rsplit('.',1)[-1]=='TimeLimiter'] == [expected] and raw == [expected] and re.search(r"@interface\s+TimeLimiter\b",source) is None
    _,parser=_language_and_parser();data=source.encode();tree=parser.parse(data);candidates={}
    for item in [*classes,*methods]: candidates.setdefault((item.qualname,item.node_kind),[]).append(item)
    found=[];unresolved={}
    def reject(owner,ann,reason): unresolved.setdefault(owner,[]).append(JavaUnresolvedTimeLimiterDeclaration(owner,_node_text(data,ann),reason))
    def parse(ann):
        values={};seen=set()
        for arg in _java_annotation_args(ann):
            if arg.type!='element_value_pair': return None,'resilience4j_time_limiter_unnamed_attribute'
            ch=_named_children(arg);kn=_child_by_field(arg,'key') or (ch[0] if ch else None);val=_child_by_field(arg,'value')
            if kn is None or val is None:return None,'resilience4j_time_limiter_malformed_attribute'
            key=_node_text(data,kn)
            if key not in {'name','fallbackMethod'}:return None,f'resilience4j_time_limiter_unsupported_attribute:{key}'
            if key in seen:return None,f'resilience4j_time_limiter_duplicate_attribute:{key}'
            seen.add(key);value=_java_string_literal_value(data,val)
            if value is None or '${' in value or '#{' in value:return None,f'resilience4j_time_limiter_{key}_not_literal_string'
            values[key]=value
        if not values.get('name'):return None,'resilience4j_time_limiter_name_missing_or_empty'
        return values,None
    def walk(node,stack):
        ns=stack;q=None;kind=None
        if node.type in _CLASS_TYPES:
            n=_identifier_from_node(data,node);ns=[*stack,n] if n else stack;q='.'.join(ns);kind='interface' if node.type=='interface_declaration' else ('record' if node.type=='record_declaration' else 'class')
        elif node.type=='method_declaration':q=_method_qualname(data,node,stack);kind='method'
        if q and kind:
            anns=[a for a in _java_annotations(node) if _java_annotation_name(data,a)=='TimeLimiter']
            if anns:
                pool=candidates.get((q,kind),[])
                if len(pool)>1:pool=[x for x in pool if x.class_hash==java_hash_for_node(source,node)]
                owner=java_node_id(pool[0]) if len(pool)==1 else f'unresolved:{path}:{q}:{kind}'
                if not exact:
                    for a in anns:reject(owner,a,'resilience4j_time_limiter_annotation_not_exact_explicit_import')
                elif len(anns)!=1:
                    for a in anns:reject(owner,a,'resilience4j_time_limiter_duplicate_annotation')
                elif len(pool)!=1:reject(owner,anns[0],'resilience4j_time_limiter_owner_ambiguous')
                else:
                    values,reason=parse(anns[0])
                    if reason:reject(owner,anns[0],reason)
                    else:found.append(JavaTimeLimiterDeclaration(owner,q,kind,path,values['name'],values.get('fallbackMethod'),_line_start(anns[0]),_line_end(anns[0]),java_hash_for_node(source,anns[0]),pool[0].class_hash))
        for child in _named_children(node):walk(child,ns)
    walk(tree.root_node,[]);return sorted(found,key=lambda x:x.owner_id),unresolved


def resolve_java_resilience4j_retry_declarations(path: str, source: str, classes: list[ClassNode], methods: list[ClassNode]) -> tuple[list[JavaResilience4jRetryDeclaration], dict[str, list[JavaUnresolvedResilience4jRetryDeclaration]]]:
    """Retain direct Resilience4j Retry literals; infer no runtime behavior."""
    if "@Retry" not in source: return [], {}
    expected = "io.github.resilience4j.retry.annotation.Retry"
    imports = re.findall(r"(?m)^\s*import\s+(?!static\b)([A-Za-z_][\w.]*)\s*;", source)
    raw = re.findall(r"\bimport\s+(?:static\s+)?([^;]*Retry[^;]*)\s*;", source)
    exact = imports.count(expected) == 1 and [x for x in imports if x.rsplit('.',1)[-1]=='Retry'] == [expected] and raw == [expected] and re.search(r"@interface\s+Retry\b",source) is None
    _,parser=_language_and_parser();data=source.encode();tree=parser.parse(data);candidates={}
    for item in [*classes,*methods]: candidates.setdefault((item.qualname,item.node_kind),[]).append(item)
    found=[];unresolved={}
    def reject(owner,ann,reason): unresolved.setdefault(owner,[]).append(JavaUnresolvedResilience4jRetryDeclaration(owner,_node_text(data,ann),reason))
    def parse(ann):
        values={};seen=set()
        for arg in _java_annotation_args(ann):
            if arg.type!='element_value_pair': return None,'resilience4j_retry_unnamed_attribute'
            ch=_named_children(arg);kn=_child_by_field(arg,'key') or (ch[0] if ch else None);val=_child_by_field(arg,'value')
            if kn is None or val is None:return None,'resilience4j_retry_malformed_attribute'
            key=_node_text(data,kn)
            if key not in {'name','fallbackMethod'}:return None,f'resilience4j_retry_unsupported_attribute:{key}'
            if key in seen:return None,f'resilience4j_retry_duplicate_attribute:{key}'
            seen.add(key);value=_java_string_literal_value(data,val)
            if value is None or '${' in value or '#{' in value:return None,f'resilience4j_retry_{key}_not_literal_string'
            values[key]=value
        if not values.get('name'):return None,'resilience4j_retry_name_missing_or_empty'
        return values,None
    def walk(node,stack):
        ns=stack;q=None;kind=None
        if node.type in _CLASS_TYPES:
            n=_identifier_from_node(data,node);ns=[*stack,n] if n else stack;q='.'.join(ns);kind='interface' if node.type=='interface_declaration' else ('record' if node.type=='record_declaration' else 'class')
        elif node.type=='method_declaration':q=_method_qualname(data,node,stack);kind='method'
        if q and kind:
            anns=[a for a in _java_annotations(node) if _java_annotation_name(data,a)=='Retry']
            if anns:
                pool=candidates.get((q,kind),[])
                if len(pool)>1:pool=[x for x in pool if x.class_hash==java_hash_for_node(source,node)]
                owner=java_node_id(pool[0]) if len(pool)==1 else f'unresolved:{path}:{q}:{kind}'
                if not exact:
                    for a in anns:reject(owner,a,'resilience4j_retry_annotation_not_exact_explicit_import')
                elif len(anns)!=1:
                    for a in anns:reject(owner,a,'resilience4j_retry_duplicate_annotation')
                elif len(pool)!=1:reject(owner,anns[0],'resilience4j_retry_owner_ambiguous')
                else:
                    values,reason=parse(anns[0])
                    if reason:reject(owner,anns[0],reason)
                    else:found.append(JavaResilience4jRetryDeclaration(owner,q,kind,path,values['name'],values.get('fallbackMethod'),_line_start(anns[0]),_line_end(anns[0]),java_hash_for_node(source,anns[0]),pool[0].class_hash))
        for child in _named_children(node):walk(child,ns)
    walk(tree.root_node,[]);return sorted(found,key=lambda x:x.owner_id),unresolved


def _java_source_type_fqn(source: str, type_name: str) -> str | None:
    simple = type_name.strip()
    if '.' in simple:
        return simple
    imported = _java_explicit_imports(source).get(simple)
    if imported:
        return imported
    package = _java_package(source)
    return f"{package}.{simple}" if package else simple


def resolve_java_event_type_edges(path: str, source: str, java_methods: list[ClassNode], repo: Any | None = None) -> tuple[list[JavaEventTypeEdge], dict[str, list[JavaUnresolvedEventType]]]:
    """Source-observed event type rendezvous, never runtime registration/delivery."""
    if repo is None or not path.endswith(".java") or not any(x in source for x in ("publishEvent", "@EventListener", "@TransactionalEventListener", "@ApplicationModuleListener")):
        return [], {}
    imports = _java_explicit_imports(source)
    exact_annotations = {
        "EventListener": imports.get("EventListener") == "org.springframework.context.event.EventListener",
        "TransactionalEventListener": imports.get("TransactionalEventListener") == "org.springframework.transaction.event.TransactionalEventListener",
        "ApplicationModuleListener": imports.get("ApplicationModuleListener") == "org.springframework.modulith.events.ApplicationModuleListener",
    }
    exact_publisher = imports.get("ApplicationEventPublisher") == "org.springframework.context.ApplicationEventPublisher"
    publisher_receivers = set(re.findall(r"\bApplicationEventPublisher\s+([A-Za-z_][\w]*)\s*(?:[;,)])", source)) if exact_publisher else set()
    type_index: dict[str, list[tuple[str, ClassNode]]] = {}
    from .java_project import java_repository_snapshot
    snapshot = java_repository_snapshot(repo)
    for rel in snapshot.paths:
        text = snapshot.texts.get(rel)
        if text is None:
            continue
        for node in extract_java_classes(rel, text):
            fqn = _java_source_type_fqn(text, node.qualname.rsplit(".", 1)[-1])
            if fqn:
                type_index.setdefault(fqn, []).append((rel, node))
    edges: list[JavaEventTypeEdge] = []
    unresolved: dict[str, list[JavaUnresolvedEventType]] = {}
    data = source.encode("utf-8")
    ids = __import__("tmf.ids", fromlist=["stable_java_node_claim_id"])

    def add(method: ClassNode, type_expr: str, edge_kind: str, anchor: Any, annotation_kind: str | None = None, metadata: dict[str, Any] | None = None) -> None:
        sid = java_node_id(method)
        if any(c in type_expr for c in "<>?[]") or not re.fullmatch(r"[A-Za-z_][\w.]*", type_expr):
            unresolved.setdefault(sid, []).append(JavaUnresolvedEventType(sid, type_expr, "event_type_generic_or_unknown", edge_kind)); return
        fqn = _java_source_type_fqn(source, type_expr)
        candidates = type_index.get(fqn or "", [])
        if len(candidates) != 1:
            unresolved.setdefault(sid, []).append(JavaUnresolvedEventType(sid, type_expr, "event_type_not_unique_or_external", edge_kind)); return
        type_path, node = candidates[0]
        tid = ids.stable_java_node_claim_id(type_path, node.qualname, node.node_kind)
        edges.append(JavaEventTypeEdge(sid, tid, node.qualname, edge_kind, path, method.class_hash, method.qualname, type_path, node.class_hash, node.node_kind, java_hash_for_node(source, anchor), annotation_kind, metadata))

    for method in java_methods:
        if method.node_kind != "method":
            continue
        node = _java_method_node_for(source, method)
        if node is None:
            continue
        span = _node_text(data, node)
        sid = java_node_id(method)
        for match in re.finditer(r"\b([A-Za-z_][\w]*)\.publishEvent\s*\(\s*new\s+([A-Za-z_][\w.]*)\s*\(", span):
            receiver, event_type = match.groups()
            if receiver in publisher_receivers:
                add(method, event_type, "publishes_type", node)
            else:
                unresolved.setdefault(sid, []).append(JavaUnresolvedEventType(sid, match.group(0), "publish_event_receiver_not_exact_application_event_publisher", "publishes_type"))
        interface = java_method_interface(source, method)
        for ann in _java_annotations(node):
            name = _java_annotation_name(data, ann)
            if name not in exact_annotations:
                continue
            if not exact_annotations[name]:
                unresolved.setdefault(sid, []).append(JavaUnresolvedEventType(sid, f"@{name}", "event_listener_annotation_not_exact_explicit_import", "listens_type")); continue
            params = interface.get("params", [])
            args = _java_annotation_args(ann)
            if name in {"EventListener", "TransactionalEventListener"} and args and any("classes" in _node_text(data, a) or "value" in _node_text(data, a) for a in args):
                unresolved.setdefault(sid, []).append(JavaUnresolvedEventType(sid, _node_text(data, ann), "event_listener_classes_attribute_unsupported", "listens_type")); continue
            if len(params) != 1 or not params[0].get("type"):
                unresolved.setdefault(sid, []).append(JavaUnresolvedEventType(sid, method.qualname, "event_listener_requires_one_known_parameter_type", "listens_type")); continue
            metadata = None
            if name == "TransactionalEventListener":
                raw = _node_text(data, ann)
                phase = re.search(r"\bphase\s*=\s*([A-Za-z_][\w.]*)", raw)
                fallback = re.search(r"\bfallbackExecution\s*=\s*(true|false)", raw)
                metadata = {"phase": phase.group(1) if phase else None, "fallback_execution": fallback.group(1) == "true" if fallback else None, "handling": "declaration-only-never-evaluated"}
            add(method, params[0]["type"], "listens_type", ann, name, metadata)
    return edges, unresolved


def _eventuate_wrapper_channels(repo: Any, source: str) -> tuple[dict[str, tuple[str, str, str]], set[str]]:
    import re
    receiver_types = {
        receiver: type_name
        for type_name, receiver in re.findall(
            r"\b([A-Za-z_][\w.]*(?:EventPublisher|DomainEventPublisher))\s+([a-zA-Z_][\w]*)\s*(?:[;,)])",
            source,
        )
    }
    channels: dict[str, tuple[str, str, str]] = {}
    ambiguous: set[str] = set()
    if repo is None:
        return channels, set(receiver_types)
    for receiver, type_name in receiver_types.items():
        simple = type_name.rsplit('.', 1)[-1]
        if simple == "DomainEventPublisher":
            continue
        candidates: list[tuple[str, str, str]] = []
        from .java_project import java_repository_snapshot
        snapshot = java_repository_snapshot(repo)
        for candidate_path in snapshot.paths:
            candidate_source = snapshot.texts.get(candidate_path)
            if candidate_source is None:
                continue
            match = re.search(
                rf"\binterface\s+{re.escape(simple)}\s+extends\s+DomainEventPublisherForAggregate\s*<\s*([A-Za-z_][\w.]*)\s*,",
                candidate_source,
            )
            if match:
                aggregate = _java_source_type_fqn(candidate_source, match.group(1))
                if aggregate:
                    candidates.append((aggregate, candidate_path, simple))
        unique = sorted(set(candidates))
        if len(unique) == 1:
            channels[receiver] = unique[0]
        else:
            ambiguous.add(receiver)
    return channels, ambiguous


def resolve_java_topic_edges(path: str, source: str, java_methods: list[ClassNode], repo: Any | None = None) -> tuple[list[JavaTopicEdge], dict[str, list[JavaUnresolvedTopic]]]:
    if not path.endswith('.java'):
        return [], {}
    import re
    # Keep expensive cross-file wrapper discovery gated, but always scan method
    # annotations: role-shaped listener annotations must become explicit unknowns
    # rather than indistinguishable true negatives.
    topic_markers = ("KafkaTemplate", "@KafkaListener", "DomainEventPublisher", "EventPublisher", "@EventuateDomainEventHandler")
    role_annotation_present = bool(re.search(r"@[A-Za-z_$][\w$]*(?:Listener|Consumer|Receiver|Receive)\b", source))
    if not any(marker in source for marker in topic_markers) and not role_annotation_present:
        return [], {}
    ids = __import__('tmf.ids', fromlist=['stable_java_node_claim_id'])
    source_bytes = source.encode('utf-8')
    edges: list[JavaTopicEdge] = []
    unresolved: dict[str, list[JavaUnresolvedTopic]] = {}
    exact_listener = bool(re.search(r"(?m)^\s*import\s+org\.springframework\.kafka\.annotation\.KafkaListener\s*;", source))
    exact_template = bool(re.search(r"(?m)^\s*import\s+org\.springframework\.kafka\.core\.KafkaTemplate\s*;", source))
    template_receivers = set()
    if exact_template:
        template_receivers = set(re.findall(r"\bKafkaTemplate\s*<[^;=(){}]+>\s+([A-Za-z_][\w]*)\s*(?:[;=,)])", source))
    wrapper_channels, ambiguous_wrappers = _eventuate_wrapper_channels(repo, source) if any(marker in source for marker in ("DomainEventPublisher", "EventPublisher")) else ({}, set())
    receiver_types = {
        receiver: type_name.rsplit('.', 1)[-1]
        for type_name, receiver in re.findall(
            r"\b([A-Za-z_][\w.]*(?:EventPublisher|DomainEventPublisher))\s+([a-zA-Z_][\w]*)\s*(?:[;,)])",
            source,
        )
    }
    for m in java_methods:
        if m.node_kind != 'method':
            continue
        sid=ids.stable_java_node_claim_id(path, m.qualname, m.node_kind)
        node = _java_method_node_for(source, m)
        span = _node_text(source_bytes, node) if node is not None else ''
        if node is not None:
            for ann in _java_annotations(node):
                ann_name = _java_annotation_name(source_bytes, ann)
                if ann_name and ann_name != "KafkaListener" and re.fullmatch(r"[A-Za-z_$][\w$]*(?:Listener|Consumer|Receiver|Receive)", ann_name):
                    unresolved.setdefault(sid, []).append(JavaUnresolvedTopic(
                        sid, _node_text(source_bytes, ann), "topic_annotation_not_recognized",
                        "subscribes_to", ann_name, m.qualname, "topic_subscription",
                    ))
            kafka_annotations = [ann for ann in _java_annotations(node) if _java_annotation_name(source_bytes, ann) == "KafkaListener"]
            if kafka_annotations and not exact_listener:
                for ann in kafka_annotations:
                    unresolved.setdefault(sid, []).append(JavaUnresolvedTopic(
                        sid, _node_text(source_bytes, ann), "topic_annotation_not_recognized",
                        "subscribes_to", "KafkaListener", m.qualname, "topic_subscription",
                    ))
        lm = re.search(r"@KafkaListener\s*\((.*?)\)\s*(?:public\s+|protected\s+|private\s+|static\s+|final\s+|synchronized\s+)*[\w.<>, ?\[\]]+\s+\w+\s*\(", span, re.DOTALL) if exact_listener else None
        if lm:
            annotation = lm.group(1)
            topic_match = re.search(r"\btopics\s*=\s*\"([^\"]+)\"", annotation)
            dynamic_topic = re.search(r"\btopics\s*=\s*([^,]+)", annotation)
            if topic_match:
                group_match = re.search(r"\bgroupId\s*=\s*\"([^\"]+)\"", annotation)
                dynamic_group = re.search(r"\bgroupId\s*=\s*([^,]+)", annotation)
                interface = java_method_interface(source, m)
                params = interface.get("params", [])
                payload_type = params[0].get("type") if len(params) == 1 else None
                edges.append(JavaTopicEdge(sid, topic_match.group(1), 'subscribes_to', source_path=m.path, source_hash=m.class_hash, source_qualname=m.qualname, resolution="spring_kafka_listener_literal", group_id=group_match.group(1) if group_match else None, payload_type=payload_type))
                if dynamic_group and not group_match:
                    unresolved.setdefault(sid, []).append(JavaUnresolvedTopic(sid, dynamic_group.group(1).strip(), 'kafka_group_id_not_literal', 'subscribes_to'))
            elif dynamic_topic:
                unresolved.setdefault(sid, []).append(JavaUnresolvedTopic(sid, dynamic_topic.group(1).strip(), 'kafka_topic_not_literal', 'subscribes_to'))
        em = re.search(r"@EventuateDomainEventHandler\s*\([^)]*\bchannel\s*=\s*\"([^\"]+)\"", span, re.DOTALL)
        if em:
            edges.append(JavaTopicEdge(sid, em.group(1), 'subscribes_to', source_path=m.path, source_hash=m.class_hash, source_qualname=m.qualname, resolution='eventuate_literal_channel'))
        send_pattern = r"\b([A-Za-z_][\w]*)\.send\s*\(\s*([^,\)]+)\s*,\s*([^,\)]+)\s*\)"
        for sm in re.finditer(send_pattern, span):
            receiver, expr, payload_expr = (x.strip() for x in sm.groups())
            if not exact_template or receiver not in template_receivers:
                continue
            if len(expr) >= 2 and expr[0] == '"' and expr[-1] == '"':
                payload_type = None
                if re.fullmatch(r'"(?:[^"\\]|\\.)*"', payload_expr):
                    payload_type = "String"
                elif re.fullmatch(r"-?\d+[lL]?", payload_expr):
                    payload_type = "long" if payload_expr[-1:] in {"l", "L"} else "int"
                else:
                    for param in java_method_interface(source, m).get("params", []):
                        if param.get("name") == payload_expr:
                            payload_type = param.get("type")
                            break
                edges.append(JavaTopicEdge(sid, expr[1:-1], 'publishes_to', source_path=m.path, source_hash=m.class_hash, source_qualname=m.qualname, resolution="spring_kafka_template_literal_send", payload_type=payload_type))
            else:
                unresolved.setdefault(sid, []).append(JavaUnresolvedTopic(sid, expr, 'kafka_topic_not_literal', 'publishes_to'))
        for pm in re.finditer(r"\b([a-zA-Z_][\w]*)\.(publish|publishById)\s*\(\s*([^,\)]+)", span):
            receiver, _operation, first_arg = pm.groups()
            if receiver not in receiver_types:
                continue
            wrapper = wrapper_channels.get(receiver)
            topic_name = wrapper[0] if wrapper else None
            dependency_path = wrapper[1] if wrapper else None
            dependency_qualname = wrapper[2] if wrapper else None
            resolution = "eventuate_aggregate_wrapper_unique"
            if receiver_types[receiver] == "DomainEventPublisher":
                class_match = re.fullmatch(r"([A-Za-z_][\w.]*)\.class", first_arg.strip())
                string_match = re.fullmatch(r'"([^\"]+)"', first_arg.strip())
                if class_match:
                    topic_name = _java_source_type_fqn(source, class_match.group(1))
                    resolution = "eventuate_direct_class_literal"
                elif string_match and '.' in string_match.group(1):
                    topic_name = string_match.group(1)
                    resolution = "eventuate_direct_fqn_literal"
                else:
                    unresolved.setdefault(sid, []).append(JavaUnresolvedTopic(sid, first_arg.strip(), 'eventuate_aggregate_not_literal', 'publishes_to'))
                    continue
            elif receiver in ambiguous_wrappers or topic_name is None:
                unresolved.setdefault(sid, []).append(JavaUnresolvedTopic(sid, receiver, 'eventuate_publisher_wrapper_not_unique', 'publishes_to'))
                continue
            edges.append(JavaTopicEdge(sid, topic_name, 'publishes_to', source_path=m.path, source_hash=m.class_hash, source_qualname=m.qualname, resolution=resolution, dependency_path=dependency_path, dependency_qualname=dependency_qualname))
    return edges, unresolved


def resolve_java_saga_definitions(path: str, source: str, java_classes: list[ClassNode], repo: Any | None = None) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Extract only literal Eventuate SimpleSaga DSL structure.

    This deliberately records the definition on the saga class rather than
    inventing call edges for method references or runtime command delivery.
    """
    if not path.endswith(".java"):
        return {}, {}
    import re
    ids = __import__("tmf.ids", fromlist=["stable_java_node_claim_id"])
    classes = {c.qualname: c for c in java_classes if c.node_kind == "class"}
    if not re.search(r"implements\s+[^\{]*\bSimpleSaga\s*<", source):
        return {}, {}
    result: dict[str, dict[str, Any]] = {}
    unresolved: dict[str, list[dict[str, Any]]] = {}
    proxy_operations: dict[tuple[str, str], list[dict[str, Any]]] = {}
    handlers: dict[tuple[str, str], list[dict[str, Any]]] = {}
    if repo is not None:
        from .java_project import java_repository_snapshot
        snapshot = java_repository_snapshot(repo)
        for candidate_path in snapshot.paths:
            candidate = snapshot.texts.get(candidate_path)
            if candidate is None:
                continue
            proxy = re.search(r"@SagaParticipantProxy\s*\(\s*channel\s*=\s*([A-Za-z_][\w.]*)\s*\)\s*public\s+class\s+(\w+)", candidate)
            if proxy:
                channel_expr, proxy_name = proxy.groups()
                channel_match = re.search(rf"\b{re.escape(proxy_name)}\s*\.\s*CHANNEL\b", candidate)
                constant_match = re.search(r"\bCHANNEL\s*=\s*\"([^\"]+)\"", candidate)
                channel = constant_match.group(1) if channel_match and constant_match else None
                if channel is None:
                    channel = channel_expr.strip('"') if channel_expr.startswith('"') else None
                if channel:
                    for op in re.finditer(r"@SagaParticipantOperation\s*\(\s*commandClass\s*=\s*([\w.]+)\.class\s*,\s*replyClasses\s*=\s*([\w.]+)\.class\s*\)\s*public\s+[^\s]+\s+(\w+)\s*\(", candidate):
                        command, reply, method = op.groups()
                        proxy_operations.setdefault((channel, method), []).append({"path": candidate_path, "proxy": proxy_name, "command": command, "reply": reply, "channel": channel})
            handler = re.search(r"@EventuateCommandHandler\s*\([^)]*\bchannel\s*=\s*\"([^\"]+)\"[^)]*\)\s*public\s+[^\s]+\s+(\w+)\s*\(\s*CommandMessage\s*<\s*([\w.]+)\s*>", candidate, re.DOTALL)
            if handler:
                channel, method, command = handler.groups()
                handlers.setdefault((channel, command.rsplit('.', 1)[-1]), []).append({"path": candidate_path, "method": method, "channel": channel, "command": command.rsplit('.', 1)[-1]})
    for cls in java_classes:
        if cls.node_kind != "class":
            continue
        class_match = re.search(rf"\bclass\s+{re.escape(cls.qualname.rsplit('.', 1)[-1])}\b[^\{{]*\bimplements\s+[^\{{]*\bSimpleSaga\s*<", source)
        if not class_match:
            continue
        cid = ids.stable_java_node_claim_id(path, cls.qualname, cls.node_kind)
        definition = re.search(r"SagaDefinition\s*<[^>]+>\s+\w+\s*=\s*(.*?\.build\s*\(\s*\))\s*;", source, re.DOTALL)
        if not definition:
            unresolved[cid] = [{"expr": "SagaDefinition", "reason": "eventuate_saga_definition_not_literal"}]
            continue
        text = definition.group(1)
        steps: list[dict[str, Any]] = []
        for step_text in re.split(r"(?=(?:^|\.)step\s*\(\s*\))", text):
            if not re.search(r"(?:^|\.)step\s*\(\s*\)", step_text):
                continue
            local = re.search(r"\.invokeLocal\s*\(\s*this::(\w+)\s*\)", step_text)
            participant = re.search(r"\.invokeParticipant\s*\(\s*this::(\w+)\s*\)", step_text)
            compensation = re.search(r"\.withCompensation\s*\(\s*this::(\w+)\s*\)", step_text)
            replies = re.findall(r"\.onReply\s*\(\s*([A-Za-z_][\w.]*)\s*,\s*this::(\w+)\s*\)", step_text)
            if local:
                steps.append({"kind": "local", "method": local.group(1), "compensation": compensation.group(1) if compensation else None})
            elif participant:
                step = {"kind": "participant", "method": participant.group(1), "replies": [{"reply": r, "handler": h} for r, h in replies]}
                matches = []
                for (channel, method), operations in proxy_operations.items():
                    if method == participant.group(1):
                        for operation in operations:
                            operation = dict(operation)
                            operation["handlers"] = handlers.get((channel, operation["command"].rsplit('.', 1)[-1]), [])
                            matches.append(operation)
                if len(matches) == 1:
                    step["participant_contract"] = matches[0]
                else:
                    unresolved.setdefault(cid, []).append({"expr": participant.group(1), "reason": "eventuate_saga_participant_operation_not_unique", "candidates": matches})
                steps.append(step)
            else:
                unresolved.setdefault(cid, []).append({"expr": step_text.strip(), "reason": "eventuate_saga_step_not_unique"})
        result[cid] = {"saga_definition": True, "resolution": "eventuate_simple_saga_literal_dsl", "steps": steps, "coverage": "partial"}
    return result, unresolved


def resolve_java_persistence_declarations(path: str, source: str, java_classes: list[ClassNode], java_methods: list[ClassNode], java_fields: list[DeclarationNode]) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, str]]]]:
    """Conservative declaration-only JPA/Jakarta metadata on existing Java nodes."""
    if not path.endswith('.java'): return {}, {}
    imports = _java_explicit_imports(source)
    names = {'Entity','Embeddable','MappedSuperclass','Id','EmbeddedId','IdClass','Table','Column','JoinColumn'}
    exact = {n for n in names if imports.get(n) in {f'jakarta.persistence.{n}', f'javax.persistence.{n}'}}
    if not exact: return {}, {}
    by_line = {(n.line_start, n.qualname, n.declaration_kind if isinstance(n, DeclarationNode) else n.node_kind): n for n in [*java_classes,*java_methods,*java_fields]}
    lines=source.splitlines(); metadata={}; unresolved={}; ids=__import__('tmf.ids',fromlist=['stable_java_node_claim_id'])
    for (_line,q,kind), node in by_line.items():

        start=max(0,node.line_start-1); tail=lines[start:min(len(lines),start+12)]
        stop=next((i for i,line in enumerate(tail) if (kind in {'class','interface','record','enum'} and re.search(r'\b(?:class|interface|record|enum)\b',line)) or (kind in {'field','constant'} and ';' in line) or (kind in {'method','constructor'} and ('{' in line or ';' in line))),len(tail)-1)
        snippet='\n'.join(tail[:stop+1]).split('{',1)[0]
        anns={n: (list(re.finditer(r'@'+n+r'\s*\(([^)]*)\)|@'+n+r'\b',snippet,re.S))[-1] if re.search(r'@'+n+r'\b',snippet) else None) for n in names}
        present={n:m for n,m in anns.items() if m is not None}
        if not present: continue
        bad=[{'annotation':n,'reason':'java_persistence_annotation_not_exact_explicit_import'} for n in present if n not in exact]
        good={n:m for n,m in present.items() if n in exact}
        out={'coverage':'partial','effect':'declaration_only','confidence':0.6,'annotations':sorted(good)}
        marker=next((n for n in ('Entity','Embeddable','MappedSuperclass') if n in good),None)
        if marker: out['persistence_kind']={'Entity':'entity','Embeddable':'embeddable','MappedSuperclass':'mapped_superclass'}[marker]
        if 'Id' in good: out['identifier_kind']='id'
        if 'EmbeddedId' in good: out['identifier_kind']='embedded_id'
        for ann,prefix,attrs in (('Table','table',('name','schema','catalog')),('Column','column',('name','table')),('JoinColumn','join_column',('name','referencedColumnName','table'))):
            if ann not in good: continue
            args=good[ann].group(1) or ''
            for attr in attrs:
                m=re.search(rf'(?:^|,)\s*{attr}\s*=\s*([^,]+)\s*(?=,|$)',args)
                if not m: continue
                lit=re.fullmatch(r'"((?:\\.|[^"\\])*)"',m.group(1).strip())
                if lit: out[f'{prefix}_'+re.sub(r'(?<!^)(?=[A-Z])','_',attr).lower()]=lit.group(1)
                else: bad.append({'annotation':ann,'attribute':attr,'reason':'java_persistence_attribute_not_literal'})
        if 'IdClass' in good:
            m=re.fullmatch(r'\s*([A-Za-z_$][\w$]*(?:\.[A-Za-z_$][\w$]*)*)\.class\s*',good['IdClass'].group(1) or '')
            if m: out['id_class']=m.group(1)
            else: bad.append({'annotation':'IdClass','reason':'java_persistence_class_not_literal'})
        identity=None if isinstance(node,DeclarationNode) else node.identity_key
        cid=ids.stable_java_node_claim_id(path,q,kind,identity)
        if len(out)>4: metadata[cid]=out
        if bad: unresolved[cid]=bad
    return metadata, unresolved


def resolve_java_repository_declarations(path: str, source: str, java_classes: list[ClassNode], java_methods: list[ClassNode], repo=None) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Spring Data repository declarations; query strings remain opaque metadata."""
    if not path.endswith('.java'): return {}, {}
    imports = _java_explicit_imports(source)
    repository_fqns = {
        'Repository':'org.springframework.data.repository.Repository',
        'CrudRepository':'org.springframework.data.repository.CrudRepository',
        'ListCrudRepository':'org.springframework.data.repository.ListCrudRepository',
        'PagingAndSortingRepository':'org.springframework.data.repository.PagingAndSortingRepository',
        'JpaRepository':'org.springframework.data.jpa.repository.JpaRepository',
    }
    jpa_wildcard = bool(re.search(r'(?m)^\s*import\s+org\.springframework\.data\.jpa\.repository\.\*\s*;', source))
    exact = {n:f for n,f in repository_fqns.items() if imports.get(n)==f or (jpa_wildcard and n=='JpaRepository')}
    query_exact = imports.get('Query') == 'org.springframework.data.jpa.repository.Query' or jpa_wildcard
    ids=__import__('tmf.ids',fromlist=['stable_java_node_claim_id']); metadata={}; unresolved={}
    if not exact:
        return metadata, unresolved
    source_types: dict[str,str] = {}
    source_type_dependencies: dict[str,dict[str,Any]] = {}
    if repo is not None:
        from .java_project import java_repository_snapshot
        snapshot = java_repository_snapshot(repo)
        for candidate_path in snapshot.paths:
            text = snapshot.texts.get(candidate_path)
            if text is None: continue
            im=_java_explicit_imports(text)
            persistence_wildcard = bool(re.search(r'(?m)^\s*import\s+(?:jakarta|javax)\.persistence\.\*\s*;', text))
            if not (im.get('Entity') in {'jakarta.persistence.Entity','javax.persistence.Entity'} or persistence_wildcard) or not re.search(r'@Entity\b',text): continue
            pkg=_java_package(text)
            entity_classes = list(snapshot.classes.get(candidate_path, ()))
            for m in re.finditer(r'\b(?:class|record|enum)\s+([A-Za-z_$][\w$]*)\b',text):
                fqn=f'{pkg}.{m.group(1)}' if pkg else m.group(1)
                node = next((n for n in entity_classes if n.qualname.rsplit('.',1)[-1] == m.group(1)), None)
                if m.group(1) in source_types and source_types[m.group(1)] != fqn:
                    source_types[m.group(1)]=''; source_type_dependencies.pop(m.group(1), None)
                else:
                    source_types[m.group(1)]=fqn
                    if node is not None:
                        source_type_dependencies[m.group(1)] = {'path': node.path, 'qualname': node.qualname,
                            'node_kind': node.node_kind, 'declaration_hash': node.class_hash, 'fqn': fqn}
    repo_classes: dict[str,dict[str,Any]]={}
    for cls in java_classes:
        if cls.node_kind != 'interface': continue
        simple=cls.qualname.rsplit('.',1)[-1]
        header=re.search(rf'\binterface\s+{re.escape(simple)}(?:\s*<([^{{>]*)>)?\s+extends\s+([^{{]+)\{{',source,re.S)
        if not header: continue
        cid=ids.stable_java_node_claim_id(path,cls.qualname,cls.node_kind,cls.identity_key)
        inherited=[]; bad=[]
        for item in re.split(r',(?![^<]*>)',header.group(2)):
            m=re.fullmatch(r'\s*([A-Za-z_$][\w$]*)\s*<\s*([^,<>]+)\s*,\s*([^,<>]+)\s*>\s*',item)
            if not m: continue
            base,domain,id_type=m.groups()
            if base not in exact: continue
            if any(x.strip().startswith('?') for x in (domain,id_type)):
                bad.append({'expr':item.strip(),'reason':'spring_data_repository_wildcard_generic'}); continue
            typevars={x.strip().split()[0] for x in (header.group(1) or '').split(',') if x.strip()}
            if domain.strip() in typevars or id_type.strip() in typevars:
                bad.append({'expr':item.strip(),'reason':'spring_data_repository_type_variable_generic'}); continue
            def resolve_type(t):
                t=t.strip()
                if t in {'Boolean','Byte','Character','Double','Float','Integer','Long','Short','String','Void'}: return f'java.lang.{t}'
                return imports.get(t) or source_types.get(t) or (_java_source_type_fqn(source,t) if re.search(rf'\b(?:class|record|enum|interface)\s+{re.escape(t)}\b',source) else None)
            df,ifqn=resolve_type(domain),resolve_type(id_type)
            if not df or not ifqn:
                bad.append({'expr':item.strip(),'reason':'spring_data_repository_unresolved_generic'}); continue
            inherited.append({'repository_type':exact[base],'declaration':item.strip(),'domain_type':df,'id_type':ifqn,'domain_entity_source_proven':source_types.get(domain.strip())==df,
                              'domain_entity_dependency': source_type_dependencies.get(domain.strip()) if source_types.get(domain.strip())==df else None})
        if inherited:
            repo_classes[cid]={'coverage':'partial','effect':'declaration_only','confidence':0.6,'inherited_repository_types':inherited}
            metadata[cid]=repo_classes[cid]
        if bad: unresolved[cid]=bad
    for method in java_methods:
        if method.node_kind not in {'method'}: continue
        owner=method.qualname.rsplit('.',1)[0]; owner_node=next((c for c in java_classes if c.qualname==owner),None)
        if owner_node is None: continue
        owner_id=ids.stable_java_node_claim_id(path,owner,owner_node.node_kind,owner_node.identity_key)
        if owner_id not in repo_classes and owner_id not in unresolved: continue
        cid=ids.stable_java_node_claim_id(path,method.qualname,method.node_kind,method.identity_key)
        lines=source.splitlines(); snippet='\n'.join(lines[max(0,method.line_start-1):method.line_end])
        decl=next((x.strip() for x in reversed(snippet.splitlines()) if re.search(rf'\b{re.escape(method.qualname.rsplit(".",1)[-1])}\s*\(',x)), '')
        out={'coverage':'partial','effect':'declaration_only','confidence':0.6,'repository_method_declaration':decl,'derived_query_name':method.qualname.rsplit('.',1)[-1]}
        qms=list(re.finditer(r'@Query\s*\((.*?)\)',snippet,re.S)); qm=qms[-1] if qms else None
        if qm:
            if not query_exact: unresolved.setdefault(cid,[]).append({'annotation':'Query','reason':'spring_data_query_annotation_not_exact_explicit_import'})
            else:
                args=qm.group(1); value=re.search(r'(?:^|,)\s*(?:value\s*=\s*)?("(?:\\.|[^"\\])*")',args)
                native=re.search(r'(?:^|,)\s*nativeQuery\s*=\s*(true|false)\b',args)
                if not value or ('nativeQuery' in args and not native): unresolved.setdefault(cid,[]).append({'annotation':'Query','reason':'spring_data_query_attribute_not_literal'})
                else: out['query_declaration']={'text':bytes(value.group(1)[1:-1],'utf-8').decode('unicode_escape'),'native': native.group(1)=='true' if native else False,'language':'native_sql' if native and native.group(1)=='true' else 'jpql','effect':'opaque_declaration_only'}
        metadata[cid]=out
    return metadata, unresolved


def resolve_java_mybatis_declarations(path: str, source: str, java_classes: list[ClassNode], java_methods: list[ClassNode]) -> tuple[dict[str, dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Exact-import, declaration-only MyBatis mapper annotation metadata.

    SQL text is deliberately opaque.  In particular this function does not
    parse statements or create database/runtime relationships.
    """
    if not path.endswith('.java'):
        return {}, {}
    imports = _java_explicit_imports(source)
    ids = __import__('tmf.ids', fromlist=['stable_java_node_claim_id'])
    sql_kinds = ('Select', 'Insert', 'Update', 'Delete')
    provider_kinds = ('SelectProvider', 'InsertProvider', 'UpdateProvider', 'DeleteProvider')
    exact_mapper = imports.get('Mapper') == 'org.apache.ibatis.annotations.Mapper'
    exact_sql = {name for name in sql_kinds if imports.get(name) == f'org.apache.ibatis.annotations.{name}'}
    lines = source.splitlines()
    metadata: dict[str, dict[str, Any]] = {}
    unresolved: dict[str, list[dict[str, Any]]] = {}

    def cid(node: ClassNode) -> str:
        return ids.stable_java_node_claim_id(path, node.qualname, node.node_kind, node.identity_key)

    def declaration_snippet(node: ClassNode) -> str:
        start = max(0, node.line_start - 1)
        # Retain the contiguous annotation prefix, stopping at the preceding
        # declaration/body boundary so metadata cannot leak between members.
        while start > 0 and not re.search(r'[;{}]', lines[start - 1]):
            start -= 1
        return '\n'.join(lines[start:node.line_end])

    mapper_owners: set[str] = set()
    for node in java_classes:
        if node.node_kind != 'interface':
            continue
        snippet = declaration_snippet(node).split('{', 1)[0]
        if not re.search(r'@Mapper\b', snippet):
            continue
        node_id = cid(node)
        if not exact_mapper:
            unresolved[node_id] = [{'annotation': 'Mapper', 'reason': 'mybatis_mapper_annotation_not_exact_explicit_import'}]
            continue
        mapper_owners.add(node.qualname)
        metadata[node_id] = {'coverage': 'partial', 'effect': 'declaration_only', 'confidence': 0.6,
                             'declaration_kind': 'mybatis_mapper_interface',
                             'annotation': 'org.apache.ibatis.annotations.Mapper'}

    java_string = r'"(?:\\.|[^"\\])*"'
    literal_value = re.compile(rf'\s*(?:value\s*=\s*)?(?P<value>{java_string}|\{{\s*{java_string}(?:\s*,\s*{java_string})*\s*\}})\s*', re.S)
    def annotation_args(snippet: str, name: str) -> str | None:
        match = re.search(rf'@{name}\s*\(', snippet)
        if match is None:
            return None
        start = match.end(); depth = 1; quoted = False; escaped = False
        for index in range(start, len(snippet)):
            char = snippet[index]
            if quoted:
                if escaped: escaped = False
                elif char == '\\': escaped = True
                elif char == '"': quoted = False
            elif char == '"': quoted = True
            elif char == '(': depth += 1
            elif char == ')':
                depth -= 1
                if depth == 0: return snippet[start:index]
        return None
    for method in java_methods:
        if method.node_kind != 'method':
            continue
        snippet = declaration_snippet(method)
        present = [name for name in (*sql_kinds, *provider_kinds) if re.search(rf'@{name}\b', snippet)]
        if not present:
            continue
        node_id = cid(method)
        bad: list[dict[str, Any]] = []
        owner = method.qualname.rsplit('.', 1)[0]
        if owner not in mapper_owners:
            bad.append({'reason': 'mybatis_mapper_owner_not_exact', 'owner': owner})
        for name in present:
            if name in provider_kinds:
                bad.append({'annotation': name, 'reason': 'mybatis_provider_annotation_deferred'})
            elif name not in exact_sql:
                bad.append({'annotation': name, 'reason': 'mybatis_sql_annotation_not_exact_explicit_import'})
        supported = [name for name in present if name in exact_sql]
        if len(supported) > 1:
            bad.append({'annotations': supported, 'reason': 'mybatis_multiple_sql_annotations_deferred'})
        if len(supported) == 1:
            name = supported[0]
            args = annotation_args(snippet, name)
            args = args if args is not None else ''
            parsed = literal_value.fullmatch(args)
            if parsed is None:
                bad.append({'annotation': name, 'reason': 'mybatis_sql_value_not_literal'})
            else:
                raw = parsed.group('value').strip()
                tokens = re.findall(java_string, raw)
                values = [bytes(token[1:-1], 'utf-8').decode('unicode_escape') for token in tokens]
                lowered = '\n'.join(values).lower()
                if '<script' in lowered:
                    bad.append({'annotation': name, 'reason': 'mybatis_script_annotation_deferred'})
                elif '<foreach' in lowered:
                    bad.append({'annotation': name, 'reason': 'mybatis_foreach_annotation_deferred'})
                else:
                    if owner in mapper_owners:
                        metadata[node_id] = {
                            'coverage': 'partial', 'effect': 'declaration_only', 'confidence': 0.6,
                            'declaration_kind': 'mybatis_mapper_method',
                            'annotation_kind': f'org.apache.ibatis.annotations.{name}',
                            'sql_declaration': {'strings': values, 'effect': 'opaque_declaration_only'},
                        }
        if bad:
            unresolved[node_id] = bad
    return metadata, unresolved
