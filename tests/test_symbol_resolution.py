import tempfile
import unittest
from pathlib import Path

from language_adapters import scan_repository
from resolver import build_symbol_index, resolve_call_graph
from graph import build_symbol_graph, get_module_name


class SymbolResolutionTests(unittest.TestCase):
    def test_index_includes_leaf_functions_with_no_calls(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            (root / "app.py").write_text(
                "def caller():\n    return leaf()\n\ndef leaf():\n    return 7\n",
                encoding="utf-8",
            )
            files = scan_repository(root).parsed_files
            index = build_symbol_index(files, root)
            module = get_module_name(root / "app.py", root.parent)
            self.assertIn(f"{module}.leaf", index["leaf"])

    def test_call_resolution_prefers_same_module_and_ignores_unknown_external(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            (root / "app.py").write_text(
                "def caller():\n    print('hi')\n    return leaf()\n\ndef leaf():\n    return 7\n",
                encoding="utf-8",
            )
            files = scan_repository(root).parsed_files
            index = build_symbol_index(files, root)
            edges = resolve_call_graph(files, root, index)
            module = get_module_name(root / "app.py", root.parent)
            self.assertIn((f"{module}.caller", f"{module}.leaf"), edges)
            self.assertFalse(any(target == "print" for _, target in edges))

    def test_graph_contains_declared_leaf_symbols_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            (root / "app.py").write_text("def leaf():\n    return 1\n", encoding="utf-8")
            files = scan_repository(root).parsed_files
            graph = build_symbol_graph([], files=files, repo_path=root)
            module = get_module_name(root / "app.py", root.parent)
            symbol = f"{module}.leaf"
            self.assertIn(symbol, graph)
            self.assertEqual(graph.nodes[symbol]["node_type"], "symbol")
            self.assertEqual(graph.nodes[symbol]["symbol_kind"], "function")
            self.assertEqual(graph[module][symbol]["relation"], "CONTAINS")

    def test_ambiguous_short_name_is_not_guessed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            (root / "a.py").write_text("def run():\n    return 1\n", encoding="utf-8")
            (root / "b.py").write_text("def run():\n    return 2\n", encoding="utf-8")
            (root / "caller.py").write_text("def caller():\n    return run()\n", encoding="utf-8")
            files = scan_repository(root).parsed_files
            index = build_symbol_index(files, root)
            edges = resolve_call_graph(files, root, index)
            caller_module = get_module_name(root / "caller.py", root.parent)
            self.assertFalse(any(source == f"{caller_module}.caller" and target.endswith(".run") for source, target in edges))


    def test_python_named_import_alias_resolves_to_imported_symbol(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            (root / "auth.py").write_text("def check_user():\n    return True\n", encoding="utf-8")
            (root / "app.py").write_text(
                "from auth import check_user as verify\ndef main():\n    return verify()\n",
                encoding="utf-8",
            )
            files = scan_repository(root).parsed_files
            index = build_symbol_index(files, root)
            edges = resolve_call_graph(files, root, index)
            app_module = get_module_name(root / "app.py", root.parent)
            auth_module = get_module_name(root / "auth.py", root.parent)
            self.assertIn((f"{app_module}.main", f"{auth_module}.check_user"), edges)

    def test_python_module_alias_resolves_attribute_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            (root / "auth.py").write_text("def check_user():\n    return True\n", encoding="utf-8")
            (root / "app.py").write_text(
                "import auth as a\ndef main():\n    return a.check_user()\n",
                encoding="utf-8",
            )
            files = scan_repository(root).parsed_files
            index = build_symbol_index(files, root)
            edges = resolve_call_graph(files, root, index)
            app_module = get_module_name(root / "app.py", root.parent)
            auth_module = get_module_name(root / "auth.py", root.parent)
            self.assertIn((f"{app_module}.main", f"{auth_module}.check_user"), edges)

    def test_js_named_import_alias_resolves_to_imported_symbol(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            (root / "auth.ts").write_text(
                "export function checkUser() { return true; }\n", encoding="utf-8"
            )
            (root / "app.ts").write_text(
                'import { checkUser as verify } from "./auth";\n'
                "export function main() { return verify(); }\n",
                encoding="utf-8",
            )
            files = scan_repository(root).parsed_files
            if not any(item.language == "typescript" for item in files):
                self.skipTest("Tree-sitter language pack is not installed")
            index = build_symbol_index(files, root)
            edges = resolve_call_graph(files, root, index)
            app_module = get_module_name(root / "app.ts", root.parent)
            auth_module = get_module_name(root / "auth.ts", root.parent)
            self.assertIn((f"{app_module}.main", f"{auth_module}.checkUser"), edges)

    def test_js_namespace_import_resolves_member_call(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            root.mkdir()
            (root / "auth.ts").write_text(
                "export function checkUser() { return true; }\n", encoding="utf-8"
            )
            (root / "app.ts").write_text(
                'import * as authApi from "./auth";\n'
                "export function main() { return authApi.checkUser(); }\n",
                encoding="utf-8",
            )
            files = scan_repository(root).parsed_files
            if not any(item.language == "typescript" for item in files):
                self.skipTest("Tree-sitter language pack is not installed")
            index = build_symbol_index(files, root)
            edges = resolve_call_graph(files, root, index)
            app_module = get_module_name(root / "app.ts", root.parent)
            auth_module = get_module_name(root / "auth.ts", root.parent)
            self.assertIn((f"{app_module}.main", f"{auth_module}.checkUser"), edges)


if __name__ == "__main__":
    unittest.main()
