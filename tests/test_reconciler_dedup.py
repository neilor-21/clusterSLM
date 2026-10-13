import unittest
import networkx as nx
from reconciler import reconcile_findings


class ReconcilerDedupTests(unittest.TestCase):
    def test_static_and_model_duplicates_are_merged(self):
        graph = nx.DiGraph()
        graph.add_node('repo.app.run')
        partitions = [{'partition_id': 1, 'nodes': ['repo.app.run'], 'subgraph': graph}]
        findings = [
            {'partition_id': 1, 'findings': [{'symbol': 'repo.app.run', 'vulnerability': 'Potential SQL Injection', 'cwe': 'CWE-89', 'confidence': 0.65, 'evidence': 'static', 'detector': 'static-heuristic'}]},
            {'partition_id': 1, 'findings': [{'symbol': 'repo.app.run', 'vulnerability': 'SQL Injection', 'cwe': 'CWE-89', 'confidence': 0.9, 'evidence': 'model', 'detector': 'slm'}]},
        ]
        result = reconcile_findings(findings, [], partitions)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['confidence'], 0.9)
        self.assertIn('slm', result[0]['detector'])
        self.assertIn('static-heuristic', result[0]['detector'])
        self.assertEqual(result[0]['validation_status'], 'needs_review')


if __name__ == '__main__':
    unittest.main()
