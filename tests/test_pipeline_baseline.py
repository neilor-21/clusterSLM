import json
import tempfile
import unittest
from pathlib import Path

import networkx as nx

from analyzer import mock_slm_worker
from parser import parse_file, discover_repository
from partition import partition_graph
from reconciler import reconcile_findings
from reporter import generate_report


class PipelineBaselineTests(unittest.TestCase):
    def test_python_parser_extracts_functions_calls_and_imports(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.py"
            path.write_text(
                "import os\nfrom pathlib import Path\n\ndef read_file(path):\n    return Path(path).read_text()\n",
                encoding="utf-8",
            )
            info = parse_file(path)
            self.assertIn("os", [item.module for item in info.imports])
            self.assertIn("read_file", info.functions)
            self.assertIn("read_text", info.call_map["read_file"])

    def test_discovery_skips_invalid_python_and_finds_valid_python(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "ok.py").write_text("def good():\n    return 1\n", encoding="utf-8")
            (root / "bad.py").write_text("def broken(:\n", encoding="utf-8")
            files = discover_repository(root)
            self.assertEqual(len(files), 1)
            self.assertEqual(files[0].path.name, "ok.py")

    def test_empty_graph_is_partitionable(self):
        self.assertEqual(partition_graph(nx.DiGraph()), [])

    def test_context_and_mock_worker_use_same_symbol_key(self):
        context = {
            "partition_id": 1,
            "internal_symbols": ["Test.services.admin_service.AdminService.run_network_diagnostic"],
            "scoped_code": {},
            "boundary_incoming": [],
            "boundary_outgoing": [],
        }
        result = mock_slm_worker(context)
        self.assertEqual(result["partition_id"], 1)
        self.assertTrue(result["findings"])
        self.assertIn("symbol", result["findings"][0])

    def test_reconciler_accepts_legacy_function_key(self):
        graph = nx.DiGraph()
        graph.add_node("module.fn")
        partitions = [{"partition_id": 1, "nodes": ["module.fn"], "subgraph": graph}]
        findings = [{"partition_id": 1, "findings": [{
            "vulnerability": "Test issue", "cwe": "CWE-000", "function": "module.fn",
            "confidence": 0.5, "evidence": "test"
        }]}]
        result = reconcile_findings(findings, [], partitions)
        self.assertEqual(result[0]["symbol"], "module.fn")
        self.assertFalse(result[0]["cross_boundary"])

    def test_report_is_written_as_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "report.json"
            report = generate_report([], output_path=str(output))
            self.assertEqual(report["total_vulnerabilities"], 0)
            self.assertEqual(json.loads(output.read_text(encoding="utf-8"))["findings"], [])


if __name__ == "__main__":
    unittest.main()
