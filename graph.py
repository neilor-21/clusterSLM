import networkx as nx
from pathlib import Path


def get_module_name(file_path, repo_path):
    """
    Convert:
        Test/auth/authenticator.py
    into:
        Test.auth.authenticator
    """
    relative = file_path.relative_to(repo_path)
    parts = list(relative.parts)

    # Remove the complete source extension so modules from multiple languages
    # receive stable names (e.g. src.client.ts -> src.client).
    source_extensions = (
        ".py", ".jsx", ".mjs", ".cjs", ".js", ".tsx", ".ts", ".java",
        ".sql", ".html", ".htm", ".css", ".scss", ".sass", ".go", ".rs",
        ".cs", ".php", ".rb", ".kt", ".kts", ".swift", ".sh", ".bash",
        ".cpp", ".cxx", ".hpp", ".cc", ".h", ".c",
    )
    for extension in source_extensions:
        if parts[-1].lower().endswith(extension):
            parts[-1] = parts[-1][:-len(extension)]
            break

    if parts[-1] == "__init__":
        parts.pop()

    return ".".join(parts)


def build_module_map(files, repo_path):
    module_map = {}
    for file in files:
        module_name = get_module_name(Path(file.path).resolve(), Path(repo_path).resolve().parent)
        module_map[module_name] = file.path
    return module_map


def resolve_import(import_info, module_map, source_module):
    module = import_info.module
    level = import_info.level

    if level > 0:
        # Relative import: walk up `level` packages from the importing module
        parts = source_module.split(".")
        base = parts[:-level] if level <= len(parts) else []
        target = ".".join(base + [module]) if module else ".".join(base)
    else:
        target = module

    if target in module_map:
        return module_map[target]

    return None


def build_dependency_graph(files, repo_path):
    graph = nx.DiGraph()
    module_map = build_module_map(files, repo_path)

    for file in files:
        source_module = get_module_name(Path(file.path).resolve(), Path(repo_path).resolve().parent)
        graph.add_node(source_module, path=str(file.path))

    for file in files:
        source_module = get_module_name(Path(file.path).resolve(), Path(repo_path).resolve().parent)

        for import_info in file.imports:
            target_path = resolve_import(import_info, module_map, source_module)

            if target_path is None:
                continue

            target_module = get_module_name(Path(target_path).resolve(), Path(repo_path).resolve().parent)
            graph.add_edge(source_module, target_module)

    return graph


def build_symbol_graph(edges, dependency_edges=None, files=None, repo_path=None):
    """Build a unified graph of calls and repository-local module dependencies.

    ``edges`` remains the legacy iterable of (caller, callee) call edges.
    ``dependency_edges`` accepts (source, target, relation) triples, currently
    used for resolved import relationships. Optional file metadata adds module
    nodes even when a file has no calls or imports.
    """
    G = nx.DiGraph()

    if files is not None and repo_path is not None:
        for file in files:
            module = get_module_name(Path(file.path).resolve(), Path(repo_path).resolve().parent)
            language = getattr(file, "language", "unknown")
            G.add_node(module, node_type="module", language=language, path=str(file.path))
            # Add every declared symbol, not just functions that happen to make
            # calls. This preserves leaf functions for context extraction and
            # ensures isolated code is represented in the repository graph.
            spans = getattr(file, "symbol_spans", {}) or {}
            for local_name, span in spans.items():
                symbol = f"{module}.{local_name}"
                G.add_node(
                    symbol,
                    node_type="symbol",
                    language=language,
                    path=str(file.path),
                    symbol_name=local_name,
                    symbol_kind=span.get("kind", "symbol"),
                    start_line=span.get("start_line"),
                    end_line=span.get("end_line"),
                )
                G.add_edge(module, symbol, relation="CONTAINS")

    # We filter out highly common built-ins so they don't skew the partitioning algorithm
    # (e.g., we don't want two unrelated functions clustered together just because they both call len())
    ignore_builtins = {
        "len",
        "str",
        "int",
        "bool",
        "isinstance",
        "open",
        "print",
        "set",
        "dict",
        "join",
        "lower",
        "get",
        "decode",
        "encode",
    }

    for caller, callee in edges:
        if callee not in ignore_builtins:
            if caller not in G:
                G.add_node(caller, node_type="symbol")
            if callee not in G:
                G.add_node(callee, node_type="symbol")
            G.add_edge(caller, callee, relation="CALLS")

    for source, target, relation in (dependency_edges or []):
        if source not in G:
            G.add_node(source, node_type="module")
        if target not in G:
            G.add_node(target, node_type="module")
        G.add_edge(source, target, relation=relation)

    return G


def print_graph(graph):
    print("\nDEPENDENCY GRAPH")
    print("=" * 60)
    print(f"Nodes: {graph.number_of_nodes()}")
    print(f"Edges: {graph.number_of_edges()}")
    print("\nDependencies:")

    for source, target in graph.edges():
        print(f"  {source} -> {target}")


import matplotlib.pyplot as plt


def plot_graph(graph):
    if graph.number_of_nodes() == 0:
        print("Nothing to plot — graph is empty.")
        return

    plt.figure(figsize=(12, 8))

    pos = nx.spring_layout(graph, k=0.6, seed=42)  # consistent layout

    nx.draw_networkx_nodes(graph, pos, node_size=1500, node_color="#8ecae6")
    nx.draw_networkx_edges(
        graph, pos, arrowstyle="-|>", arrowsize=15, edge_color="#555555"
    )
    nx.draw_networkx_labels(graph, pos, font_size=8)

    plt.title("Module Dependency Graph")
    plt.axis("off")
    plt.tight_layout()
    plt.show()
