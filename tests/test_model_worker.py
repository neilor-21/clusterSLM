import unittest
from model_worker import extract_json_object


class ModelWorkerTests(unittest.TestCase):
    def test_parses_json_findings(self):
        result = extract_json_object('{"findings": []}')
        self.assertEqual(result, {'findings': []})

    def test_parses_fenced_json_list(self):
        result = extract_json_object('```json\n[{"vulnerability":"SQLi","cwe":"CWE-89","symbol":"app.f"}]\n```')
        self.assertEqual(len(result['findings']), 1)

    def test_rejects_invalid_response(self):
        with self.assertRaises(ValueError):
            extract_json_object('I think the code is vulnerable but here is no JSON')


if __name__ == '__main__':
    unittest.main()
