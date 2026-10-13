"""Repository-local import and symbol resolution.

Resolution is deliberately conservative: unresolved or ambiguous calls are not
connected to guessed targets. Import bindings improve cross-module precision,
but this is static name resolution, not full language/type analysis.
"""
from pathlib import Path

from graph import get_module_name

JS_EXTENSIONS = (".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx")


def _symbol_names(file_info):
    """Return unique qualified symbols known to the adapter for one file."""
    spans = getattr(file_info, "symbol_spans", {}) or {}
    if spans:
        names = list(spans.keys())
    else:
        names = list(getattr(file_info, "classes", []))
        names.extend(getattr(file_info, "functions", []))
    return list(dict.fromkeys(name for name in names if name and name != "<module>"))


def build_symbol_index(files, repo_path):
    """Index declared symbols by local qualified name and short final name."""
    index = {}
    root = Path(repo_path).resolve()
    for file in files:
        module = get_module_name(Path(file.path).resolve(), root.parent)
        for local_name in _symbol_names(file):
            fqn = f"{module}.{local_name}"
            index.setdefault(local_name, []).append(fqn)
            index.setdefault(local_name.split(".")[-1], []).append(fqn)
    return {key: list(dict.fromkeys(values)) for key, values in index.items()}


def _choose_candidate(candidates, caller_module):
    """Choose one candidate, preferring a unique same-module declaration."""
    candidates = list(dict.fromkeys(candidates))
    if not candidates:
        return None
    local = [candidate for candidate in candidates if candidate.startswith(caller_module + ".")]
    if len(local) == 1:
        return local[0]
    if len(local) > 1:
        return None
    return candidates[0] if len(candidates) == 1 else None


def _build_file_lookup(files, repo_path):
    """Map normalized repo-relative source stems and module names to FileInfo."""
    root = Path(repo_path).resolve()
    by_stem = {}
    by_module = {}
    for file in files:
        path = Path(file.path).resolve()
        try:
            relative = path.relative_to(root)
        except ValueError:
            continue
        stem = relative.with_suffix("").as_posix()
        by_stem[stem] = file
        if relative.name.startswith("index."):
            by_stem[relative.parent.as_posix()] = file
        by_module[get_module_name(path, root.parent)] = file
    return by_stem, by_module


def _target_for_import(source_file, item, repo_path, by_stem, by_module):
    """Resolve an import record to a repository-local FileInfo, if possible."""
    root = Path(repo_path).resolve()
    source_path = Path(source_file.path).resolve()
    module = getattr(item, "module", "") or ""

    if module.startswith("."):
        base = (source_path.parent / module).resolve()
        candidates = [base]
        candidates.extend(Path(str(base) + ext) for ext in JS_EXTENSIONS)
        candidates.extend(base / ("index" + ext) for ext in JS_EXTENSIONS)
        for candidate in candidates:
            try:
                stem = candidate.relative_to(root).with_suffix("").as_posix()
            except ValueError:
                continue
            if stem in by_stem:
                return by_stem[stem]
        return None

    module_path = module.replace(".", "/")
    level = getattr(item, "level", 0)
    if level > 0:
        base = source_path.parent
        for _ in range(max(0, level - 1)):
            base = base.parent
        candidate_base = (base / module_path).resolve() if module_path else base
    else:
        candidate_base = (root / module_path).resolve()

    candidates = [candidate_base.with_suffix(".py"), candidate_base / "__init__.py"]
    for candidate in candidates:
        try:
            stem = candidate.relative_to(root).with_suffix("").as_posix()
        except ValueError:
            continue
        if stem in by_stem:
            return by_stem[stem]
    # Fallback for imports whose module spelling matches the indexed module.
    return by_module.get(module)


def resolve_call_graph(files, repo_path, index, include_unresolved=False):
    """Resolve local calls, prioritizing explicit import bindings over name guesses."""
    root = Path(repo_path).resolve()
    by_stem, by_module = _build_file_lookup(files, root)
    edges = set()

    for file in files:
        source_path = Path(file.path).resolve()
        module = get_module_name(source_path, root.parent)
        # Build aliases for this source file from its imports.
        module_bindings = {}
        symbol_bindings = {}
        for item in getattr(file, "imports", []):
            target_file = _target_for_import(file, item, root, by_stem, by_module)
            if target_file is None:
                continue
            target_module = get_module_name(Path(target_file.path).resolve(), root.parent)
            alias = getattr(item, "module_alias", None)
            if alias:
                module_bindings[alias] = (target_file, target_module)
            for local_name, imported_name in (getattr(item, "names", {}) or {}).items():
                symbol_bindings[local_name] = (target_file, imported_name, target_module)

        for caller, calls in getattr(file, "call_map", {}).items():
            caller_fqn = module if caller == "<module>" else f"{module}.{caller}"
            for call in calls:
                call = str(call).strip()
                if not call:
                    continue
                target = None
                explicitly_bound = False

                # `verify()` from `from auth import check_user as verify`.
                if call in symbol_bindings:
                    explicitly_bound = True
                    target_file, imported_name, target_module = symbol_bindings[call]
                    local_names = _symbol_names(target_file)
                    if imported_name in local_names:
                        target = f"{target_module}.{imported_name}"

                # `api.check_user()` from `import auth as api` / `import * as api`.
                if target is None and "." in call:
                    prefix, suffix = call.split(".", 1)
                    if prefix in module_bindings:
                        _, target_module = module_bindings[prefix]
                        local_names = _symbol_names(module_bindings[prefix][0])
                        if suffix in local_names:
                            target = f"{target_module}.{suffix}"

                # Fallback: precise same-module or globally unique symbol matching.
                if target is None and not explicitly_bound:
                    candidates = index.get(call, [])
                    if not candidates:
                        candidates = index.get(call.split(".")[-1], [])
                    target = _choose_candidate(candidates, module)

                if target and target != caller_fqn:
                    edges.add((caller_fqn, target))
                elif include_unresolved and not target:
                    edges.add((caller_fqn, call))
    return edges


def resolve_import_graph_edges(files, repo_path):
    """Resolve repository-local imports into module-level IMPORTS edges."""
    root = Path(repo_path).resolve()
    by_stem, by_module = _build_file_lookup(files, root)
    edges = set()
    for file in files:
        source_module = get_module_name(Path(file.path).resolve(), root.parent)
        for item in getattr(file, "imports", []):
            target_file = _target_for_import(file, item, root, by_stem, by_module)
            if target_file is None:
                continue
            target_module = get_module_name(Path(target_file.path).resolve(), root.parent)
            if source_module != target_module:
                edges.add((source_module, target_module, "IMPORTS"))
    return sorted(edges)
