import unittest
from static_analyzer import analyze_symbol, analyze_partition_context


class StaticAnalyzerTests(unittest.TestCase):
    def test_flags_dynamic_sql(self):
        code = 'def f(user_id):\n    query = f"SELECT * FROM users WHERE id={user_id}"\n    return db.execute(query)'
        findings = analyze_symbol('app.f', code, 'python')
        self.assertTrue(any(item['cwe'] == 'CWE-89' for item in findings))

    def test_does_not_flag_parameterized_sql(self):
        code = 'def f(user_id):\n    query = "SELECT * FROM users WHERE id = ?"\n    return db.execute(query, (user_id,))'
        findings = analyze_symbol('app.f', code, 'python')
        self.assertFalse(any(item['cwe'] == 'CWE-89' for item in findings))

    def test_flags_shell_command_injection_pattern(self):
        code = 'def f(host):\n    cmd = "ping " + host\n    subprocess.run(cmd, shell=True)'
        findings = analyze_symbol('app.f', code, 'python')
        self.assertTrue(any(item['cwe'] == 'CWE-78' for item in findings))

    def test_flags_path_traversal_pattern(self):
        code = 'def read_file(filename):\n    path = os.path.join("/srv/files", filename)\n    return open(path).read()'
        findings = analyze_symbol('app.read_file', code, 'python')
        self.assertTrue(any(item['cwe'] == 'CWE-22' for item in findings))

    def test_flags_hardcoded_credential_pattern(self):
        code = 'def connect():\n    return db.connect(password="prod-secret-123")'
        findings = analyze_symbol('app.connect', code, 'python')
        self.assertTrue(any(item['cwe'] == 'CWE-798' for item in findings))

    def test_flags_pickle_deserialization(self):
        findings = analyze_symbol('app.load', 'def load(data):\n    return pickle.loads(data)', 'python')
        self.assertTrue(any(item['cwe'] == 'CWE-502' for item in findings))

    def test_partition_skips_class_level_duplicate(self):
        context = {'partition_id': 1, 'scoped_code': {'app.C': 'class C:\n    def f(self):\n        return pickle.loads(data)', 'app.C.f': 'def f(self):\n    return pickle.loads(data)'}, 'symbol_kinds': {'app.C': 'class', 'app.C.f': 'function'}}
        result = analyze_partition_context(context)
        self.assertEqual(len([x for x in result['findings'] if x['cwe'] == 'CWE-502']), 1)


if __name__ == '__main__':
    unittest.main()
