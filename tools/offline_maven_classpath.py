#!/usr/bin/env python3
"""Fail-closed offline Maven classpath resolver. Never executes build code or networks."""
from __future__ import annotations
import hashlib, json, os, re
from pathlib import Path
import xml.etree.ElementTree as ET

_COORD = re.compile(r"^[A-Za-z0-9_.-]+$")
_BAD_XML = re.compile(br"<!\s*(?:DOCTYPE|ENTITY)", re.I)

class Unsupported(Exception): pass

def _inside(base: Path, p: Path) -> Path:
    base = base.resolve(strict=True)
    p = p.resolve(strict=True)
    if p != base and base not in p.parents:
        raise Unsupported("path_or_symlink_escapes_allowed_root")
    return p

def _child(e, name):
    return e.find("{*}" + name)

def _text(e, name, required=False):
    x = _child(e, name)
    v = (x.text or "").strip() if x is not None else ""
    if required and not v: raise Unsupported("missing_" + name)
    if "${" in v: raise Unsupported("dynamic_property_value")
    return v

def _pom(path: Path, allowed: Path, project=False):
    path = _inside(allowed, path)
    if path.is_symlink() or not path.is_file(): raise Unsupported("pom_not_regular_file")
    raw = path.read_bytes()
    if _BAD_XML.search(raw): raise Unsupported("unsafe_xml_declaration")
    try: root = ET.fromstring(raw)
    except ET.ParseError as e: raise Unsupported("invalid_xml") from e
    if root.tag.rsplit("}",1)[-1] != "project": raise Unsupported("not_a_maven_project")
    if project:
        for n, reason in (("profiles","profiles_unsupported"),("repositories","repositories_unsupported"),
                          ("pluginRepositories","plugin_repositories_unsupported")):
            if _child(root,n) is not None: raise Unsupported(reason)
        build=_child(root,"build")
        if build is not None and any(_child(build,n) is not None for n in ("plugins","pluginManagement","extensions")):
            raise Unsupported("plugins_or_extensions_unsupported")
        props=_child(root,"properties")
        if props is not None and list(props): raise Unsupported("properties_unsupported")
    if _child(root,"dependencyManagement") is not None: raise Unsupported("dependency_management_or_bom_unsupported")
    parent=_child(root,"parent")
    if parent is not None: raise Unsupported("parent_unsupported")
    deps=[]; ds=_child(root,"dependencies")
    if ds is not None:
        for d in list(ds):
            if d.tag.rsplit("}",1)[-1] != "dependency": continue
            g,a,v=(_text(d,x,True) for x in ("groupId","artifactId","version"))
            typ=_text(d,"type") or "jar"; classifier=_text(d,"classifier")
            scope=_text(d,"scope") or "compile"; optional=_text(d,"optional").lower()=="true"
            if typ != "jar" or classifier: raise Unsupported("non_plain_jar_dependency")
            if scope in ("test","provided","system") or optional: continue
            if scope not in ("compile","runtime"): raise Unsupported("unsupported_dependency_scope")
            deps.append((g,a,v))
    return root,deps,hashlib.sha256(raw).hexdigest()

def resolve(repo, module=".", cache=None):
    repo=Path(repo).resolve(strict=True); module=_inside(repo, repo/module)
    cache=Path(cache or Path.home()/".m2/repository").resolve(strict=True)
    pom=_inside(repo,module/"pom.xml")
    try:
        _, roots, project_hash=_pom(pom,repo,project=True)
        seen=set(); rows=[]; stack=list(roots)
        while stack:
            c=stack.pop()
            if c in seen: continue
            if not all(_COORD.fullmatch(x) for x in c): raise Unsupported("unsafe_coordinate")
            seen.add(c); g,a,v=c; base=cache/Path(*g.split('.'))/a/v
            pp=_inside(cache,base/f"{a}-{v}.pom"); jar=_inside(cache,base/f"{a}-{v}.jar")
            if pp.is_symlink() or jar.is_symlink() or not jar.is_file(): raise Unsupported("artifact_or_pom_missing_or_symlink")
            _,deps,ph=_pom(pp,cache)
            jh=hashlib.sha256(jar.read_bytes()).hexdigest()
            rows.append({"coordinate":f"{g}:{a}:{v}","path":str(jar),"jar_sha256":jh,"pom_sha256":ph})
            stack.extend(deps)
        rows.sort(key=lambda x:x["coordinate"])
        canonical=json.dumps(rows,sort_keys=True,separators=(",",":"))
        return {"status":"complete","kind":"maven","module":str(module.relative_to(repo)) or ".",
                "project_pom_sha256":project_hash,"classpath":rows,
                "classpath_fingerprint":"sha256:"+hashlib.sha256(canonical.encode()).hexdigest(),
                "annotation_processing":"disabled"}
    except (Unsupported,FileNotFoundError,OSError) as e:
        return {"status":"partial","kind":"maven","module":str(module.relative_to(repo)) or ".",
                "reason":str(e) or type(e).__name__,"annotation_processing":"disabled"}
