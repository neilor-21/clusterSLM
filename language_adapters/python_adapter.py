"""Python AST adapter for the language-neutral ClusterSLM pipeline."""
import ast
from pathlib import Path

from language_adapters.base import FileInfo, ImportInfo


class _PythonVisitor(ast.NodeVisitor):
    def __init__(self, info: FileInfo):
        self.info = info
        self.scope_stack = []

    def visit_Import(self, node):
        for alias in node.names:
            self.info.imports.append(ImportInfo(alias.name))
        self.generic_visit(node)

    def visit_ImportFrom(self, node):
        self.info.imports.append(ImportInfo(node.module or "", node.level))
        self.generic_visit(node)

    def visit_ClassDef(self, node):
        self.info.classes.append(node.name)
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_FunctionDef(self, node):
        self.info.functions.append(node.name)
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_AsyncFunctionDef(self, node):
        self.info.functions.append(node.name)
        self.scope_stack.append(node.name)
        self.generic_visit(node)
        self.scope_stack.pop()

    def visit_Call(self, node):
        call_name = None
        if isinstance(node.func, ast.Name):
            call_name = node.func.id
        elif isinstance(node.func, ast.Attribute):
            parts = []
            current = node.func
            while isinstance(current, ast.Attribute):
                parts.append(current.attr)
                current = current.value
            if isinstance(current, ast.Name):
                parts.append(current.id)
            call_name = ".".join(reversed(parts))

        if call_name:
            caller = ".".join(self.scope_stack) if self.scope_stack else "<module>"
            self.info.call_map.setdefault(caller, []).append(call_name)
            self.info.calls.append({"caller": caller, "callee": call_name})
        self.generic_visit(node)


class PythonAdapter:
    language = "python"
    extensions = (".py",)

    def parse_file(self, path: Path) -> FileInfo:
        path = Path(path)
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        info = FileInfo(path=path, language=self.language)
        _PythonVisitor(info).visit(tree)
        return info
