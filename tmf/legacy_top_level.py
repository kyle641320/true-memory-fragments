"""Legacy Python module regions; keep old identities and token hash semantics."""
import ast
from dataclasses import dataclass
from .extract import fn_hash_for_span, _identifier_keywords

@dataclass
class ModuleTopLevelNode:
    path: str
    region_id: str
    line_start: int
    line_end: int
    top_level_hash: str
    keywords: list[str]

def _module_top_level_stmt_lines(stmt: ast.stmt) -> tuple[int, int] | None:
    if isinstance(stmt, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        return None
    if isinstance(stmt, ast.Expr) and isinstance(getattr(stmt, "value", None), ast.Constant) and isinstance(stmt.value.value, str):
        return None
    line_start = int(getattr(stmt, "lineno", 0) or 0)
    line_end = int(getattr(stmt, "end_lineno", line_start) or line_start)
    if line_start <= 0 or line_end <= 0:
        return None
    return line_start, line_end


def extract_module_top_levels(path: str, source: str, ) -> list[ModuleTopLevelNode]:
    if not path.endswith(".py"):
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    regions: list[list[tuple[int, int, ast.stmt]]] = []
    current: list[tuple[int, int, ast.stmt]] = []
    previous_end: int | None = None
    for stmt in tree.body:
        lines = _module_top_level_stmt_lines(stmt)
        if lines is None:
            if current:
                regions.append(current)
                current = []
            previous_end = None
            continue
        line_start, line_end = lines
        if current and previous_end is not None and line_start > previous_end + 1:
            regions.append(current)
            current = []
        current.append((line_start, line_end, stmt))
        previous_end = line_end
    if current:
        regions.append(current)

    nodes: list[ModuleTopLevelNode] = []
    for idx, region in enumerate(regions, start=1):
        line_start = region[0][0]
        line_end = region[-1][1]
        region_id = f"top_level_{idx:04d}"
        names: list[str] = []
        for _start, _end, stmt in region:
            if isinstance(stmt, (ast.Import, ast.ImportFrom)):
                names.append("import")
            elif isinstance(stmt, ast.Assign):
                for target in stmt.targets:
                    if isinstance(target, ast.Name):
                        names.append(target.id)
            elif isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
                names.append(stmt.target.id)
            elif isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Call):
                func = stmt.value.func
                if isinstance(func, ast.Name):
                    names.append(func.id)
                elif isinstance(func, ast.Attribute):
                    names.append(func.attr)
        keywords = []
        for name in names:
            for keyword in _identifier_keywords(name):
                if keyword not in keywords:
                    keywords.append(keyword)
            if len(keywords) >= 16:
                break
        nodes.append(ModuleTopLevelNode(
            path=path,
            region_id=region_id,
            line_start=line_start,
            line_end=line_end,
            top_level_hash=fn_hash_for_span(source, line_start, line_end),
            keywords=keywords,
        ))
    return nodes
