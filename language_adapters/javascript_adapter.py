"""Tree-sitter based JavaScript/TypeScript structural parser.

This extracts syntax-level symbols and dependencies only. It does not perform
full type resolution or prove cross-language data flow.
"""
from pathlib import Path
import re

from language_adapters.base import FileInfo, ImportInfo

try:
    from tree_sitter_language_pack import get_parser
except ImportError:  # Report a clear actionable error if dependencies were not installed.
    get_parser = None


LANGUAGE_BY_EXTENSION = {
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "tsx",
}


def _text(node, source: bytes) -> str:
    return source[node.start_byte:node.end_byte].decode("utf-8", errors="replace")


def _callee_name(node, source: bytes) -> str:
    """Return a compact textual callee name, e.g. api.fetch or saveUser."""
    if node is None:
        return ""
    raw = _text(node, source).strip()
    # Remove optional-call syntax noise while retaining member chains.
    return re.sub(r"\s+", "", raw)[:200]


def _named_child(node, field_name):
    try:
        return node.child_by_field_name(field_name)
    except AttributeError:
        return None


class JavaScriptAdapter:
    """Parse JavaScript, JSX, TypeScript and TSX into ClusterSLM's common model."""

    language = "javascript-typescript"
    extensions = tuple(LANGUAGE_BY_EXTENSION)

    def parse_file(self, path: Path) -> FileInfo:
        path = Path(path)
        if get_parser is None:
            raise RuntimeError(
                "JavaScript/TypeScript parsing requires tree-sitter-language-pack. "
                "Install project dependencies with: python -m pip install -r requirements.txt"
            )
        suffix = path.suffix.lower()
        grammar = LANGUAGE_BY_EXTENSION.get(suffix)
        if grammar is None:
            raise ValueError(f"Unsupported JavaScript/TypeScript extension: {suffix}")

        source = path.read_bytes()
        parser = get_parser(grammar)
        tree = parser.parse(source)
        if tree.root_node.has_error:
            # Tree-sitter can recover from syntax errors, so keep valid extracted
            # structures instead of discarding the entire file.
            pass

        language = "typescript" if suffix in {".ts", ".tsx"} else "javascript"
        info = FileInfo(path=path, language=language)
        root = tree.root_node

        def walk(node, scope):
            node_type = node.type
            next_scope = scope

            if node_type in {"class_declaration", "abstract_class_declaration"}:
                name_node = _named_child(node, "name")
                if name_node is not None:
                    name = _text(name_node, source)
                    info.classes.append(name)
                    next_scope = scope + [name]
            elif node_type in {"function_declaration", "generator_function_declaration"}:
                name_node = _named_child(node, "name")
                if name_node is not None:
                    name = _text(name_node, source)
                    info.functions.append(name)
                    next_scope = scope + [name]
            elif node_type in {"method_definition", "method_signature"}:
                name_node = _named_child(node, "name")
                if name_node is not None:
                    name = _text(name_node, source)
                    info.functions.append(name)
                    next_scope = scope + [name]
            elif node_type in {"lexical_declaration", "variable_declaration"}:
                # Capture common const handler = (...) => {} and function expressions.
                for declarator in node.named_children:
                    if declarator.type != "variable_declarator":
                        continue
                    value_node = _named_child(declarator, "value")
                    name_node = _named_child(declarator, "name")
                    if value_node is not None and name_node is not None and value_node.type in {
                        "arrow_function", "function_expression", "generator_function",
                    }:
                        name = _text(name_node, source)
                        info.functions.append(name)
                        next_scope = scope + [name]

            if node_type == "import_statement":
                # Handles: import x from "pkg"; import "pkg"; import x = require("pkg")
                raw = _text(node, source)
                match = re.search(r"\bfrom\s*['\"]([^'\"]+)['\"]", raw)
                if not match:
                    match = re.search(r"^\s*import\s*['\"]([^'\"]+)['\"]", raw)
                if match:
                    info.imports.append(ImportInfo(match.group(1)))
            elif node_type == "call_expression":
                function_node = _named_child(node, "function")
                callee = _callee_name(function_node, source)
                if callee:
                    caller = ".".join(scope) if scope else "<module>"
                    info.call_map.setdefault(caller, []).append(callee)
                    info.calls.append({"caller": caller, "callee": callee})

            for child in node.named_children:
                walk(child, next_scope)

        walk(root, [])
        # Keep stable order while removing duplicate declarations caused by
        # overload/signature syntax or repeated traversal patterns.
        info.classes = list(dict.fromkeys(info.classes))
        info.functions = list(dict.fromkeys(info.functions))
        return info
