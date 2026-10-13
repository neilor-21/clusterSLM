import unittest
from evaluate import evaluate


class EvaluateTests(unittest.TestCase):
    def test_precision_recall_f1(self):
        predicted = [{'symbol': 'a.f', 'cwe': 'CWE-89'}, {'symbol': 'b.g', 'cwe': 'CWE-78'}]
        gold = [{'symbol': 'a.f', 'cwe': 'CWE-89'}, {'symbol': 'c.h', 'cwe': 'CWE-22'}]
        metrics = evaluate(predicted, gold)
        self.assertEqual(metrics['true_positives'], 1)
        self.assertEqual(metrics['false_positives'], 1)
        self.assertEqual(metrics['false_negatives'], 1)
        self.assertEqual(metrics['f1'], 0.5)


if __name__ == '__main__':
    unittest.main()
