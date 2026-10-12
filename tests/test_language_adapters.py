import tempfile
import unittest
from pathlib import Path

from language_adapters import LanguageRegistry, scan_repository
from parser import parse_file, discover_repository


class LanguageAdapterTests(unittest.TestCase):
    def test_python_adapter_returns_common_file_info(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.py"
            path.write_text("import os\ndef run():\n    return os.getcwd()\n", encoding="utf-8")
            info = parse_file(path)
            self.assertEqual(info.language, "python")
            self.assertEqual(info.functions, ["run"])
            self.assertIn("os", [item.module for item in info.imports])
            self.assertIn("getcwd", info.call_map["run"][0])

    def test_mixed_repository_reports_unimplemented_languages_explicitly(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("def run():\n    return 1\n", encoding="utf-8")
            (root / "client.ts").write_text("export function run() { return 1; }\n", encoding="utf-8")
            (root / "schema.sql").write_text("SELECT 1;\n", encoding="utf-8")
            scan = scan_repository(root)
            self.assertEqual(scan.detected_languages, {"python": 1, "sql": 1, "typescript": 1})
            self.assertIn("python", scan.parsed_languages)
            self.assertIn("sql", scan.unsupported_language_counts)
            if any(item.language == "typescript" for item in scan.parsed_files):
                ts_info = next(item for item in scan.parsed_files if item.language == "typescript")
                self.assertIn("run", ts_info.functions)
            else:
                self.assertIn("typescript", scan.unsupported_language_counts)

    def test_javascript_adapter_extracts_functions_imports_and_calls(self):
        from language_adapters.javascript_adapter import get_parser
        if get_parser is None:
            self.skipTest("tree-sitter-language-pack is not installed in this environment")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "client.ts"
            path.write_text(
                'import { request } from "./api";\n'
                'export function loadUser() { return request("/users"); }\n'
                'const saveUser = (user) => persist(user);\n',
                encoding="utf-8",
            )
            from language_adapters import JavaScriptAdapter
            info = JavaScriptAdapter().parse_file(path)
            self.assertEqual(info.language, "typescript")
            self.assertIn("loadUser", info.functions)
            self.assertIn("saveUser", info.functions)
            self.assertIn("./api", [item.module for item in info.imports])
            callees = [call["callee"] for call in info.calls]
            self.assertIn("request", callees)
            self.assertIn("persist", callees)

    def test_ignored_directories_are_not_scanned(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "node_modules" / "pkg").mkdir(parents=True)
            (root / "src" / "app.py").write_text("def app(): pass\n", encoding="utf-8")
            (root / "node_modules" / "pkg" / "bad.py").write_text("def ignored(): pass\n", encoding="utf-8")
            scan = scan_repository(root)
            self.assertEqual([f.path.name for f in scan.parsed_files], ["app.py"])

    def test_registry_can_be_extended_with_another_adapter(self):
        class FakeAdapter:
            language = "fake"
            extensions = (".fake",)
            def parse_file(self, path):
                from language_adapters import FileInfo
                return FileInfo(path=path, language="fake")

        registry = LanguageRegistry(adapters=[FakeAdapter()])
        self.assertIsInstance(registry.get_adapter(Path("example.fake")), FakeAdapter)

    def test_discover_repository_returns_all_supported_parsed_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "app.py").write_text("def app(): pass\n", encoding="utf-8")
            (root / "app.js").write_text("function app() {}\n", encoding="utf-8")
            # Returns all successfully parsed files; JavaScript is included only
            # when its optional Tree-sitter dependency is installed.
            from language_adapters.javascript_adapter import get_parser
            self.assertEqual(len(discover_repository(root)), 2 if get_parser else 1)


if __name__ == "__main__":
    unittest.main()
