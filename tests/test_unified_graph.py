import tempfile
import unittest
from pathlib import Path

from language_adapters import scan_repository
from resolver import resolve_import_graph_edges, build_symbol_index, resolve_call_graph
from graph import build_symbol_graph
from analyzer import extract_symbol_snippet
from partition import partition_graph


class UnifiedGraphTests(unittest.TestCase):
    def test_relative_typescript_import_is_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "client.ts").write_text('import { request } from "./api";\nexport function load() { return request(); }\n', encoding="utf-8")
            (root / "api.ts").write_text('export function request() { return 1; }\n', encoding="utf-8")
            scan = scan_repository(root)
            if not any(item.language == "typescript" for item in scan.parsed_files):
                self.skipTest("Tree-sitter language pack is not installed")
            edges = resolve_import_graph_edges(scan.parsed_files, root)
            self.assertEqual(len(edges), 1)
            self.assertEqual(edges[0][2], "IMPORTS")
            self.assertIn("client", edges[0][0])
            self.assertIn("api", edges[0][1])

    def test_graph_keeps_call_and_import_relations(self):
        graph = build_symbol_graph(
            [("py.mod.run", "py.mod.helper")],
            dependency_edges=[("js.client", "js.api", "IMPORTS")],
        )
        self.assertEqual(graph["py.mod.run"]["py.mod.helper"]["relation"], "CALLS")
        self.assertEqual(graph["js.client"]["js.api"]["relation"], "IMPORTS")


    def test_python_adapter_records_source_spans(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "app.py"
            path.write_text("def run():\n    value = 1\n    return value\n", encoding="utf-8")
            scan = scan_repository(root)
            info = scan.parsed_files[0]
            self.assertIn("run", info.symbol_spans)
            snippet = extract_symbol_snippet(path.read_text(encoding="utf-8"), "run", info.symbol_spans)
            self.assertIn("return value", snippet)

    def test_non_python_source_can_use_adapter_spans(self):
        source = "export function run() {\n  return 42;\n}"
        snippet = extract_symbol_snippet(source, "run", {"run": {"start_line": 1, "end_line": 3, "kind": "function"}})
        self.assertIn("return 42", snippet)

    def test_edgeless_graph_produces_singleton_partitions(self):
        graph = build_symbol_graph([], files=[], repo_path=Path("."))
        graph.add_node("isolated-module", node_type="module")
        partitions = partition_graph(graph)
        self.assertEqual(len(partitions), 1)
        self.assertEqual(partitions[0]["nodes"], ["isolated-module"])

    def test_python_import_is_resolved(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("from helpers import run\ndef main():\n    return run()\n", encoding="utf-8")
            (root / "helpers.py").write_text("def run():\n    return 1\n", encoding="utf-8")
            scan = scan_repository(root)
            edges = resolve_import_graph_edges(scan.parsed_files, root)
            self.assertEqual(len(edges), 1)
            self.assertEqual(edges[0][2], "IMPORTS")


if __name__ == "__main__":
    unittest.main()
