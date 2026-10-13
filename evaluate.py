"""Simple finding-level precision/recall/F1 evaluator for labeled JSON findings."""
import argparse
import json
from pathlib import Path


def _read_findings(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = data.get("findings", [])
    if not isinstance(data, list):
        raise ValueError(f"Expected a JSON list or an object with a findings list: {path}")
    return data


def _key(item):
    symbol = item.get("symbol", item.get("function", ""))
    cwe = item.get("cwe", "")
    return str(symbol), str(cwe)


def evaluate(predicted, gold):
    predicted_keys = {_key(item) for item in predicted if _key(item) != ("", "")}
    gold_keys = {_key(item) for item in gold if _key(item) != ("", "")}
    tp = len(predicted_keys & gold_keys)
    fp = len(predicted_keys - gold_keys)
    fn = len(gold_keys - predicted_keys)
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"true_positives": tp, "false_positives": fp, "false_negatives": fn,
            "precision": round(precision, 4), "recall": round(recall, 4), "f1": round(f1, 4),
            "matching_rule": "exact (symbol, CWE) pair; duplicates collapsed"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predicted", required=True, help="ClusterSLM report JSON or findings list")
    parser.add_argument("--gold", required=True, help="Ground-truth JSON list or report")
    args = parser.parse_args()
    print(json.dumps(evaluate(_read_findings(args.predicted), _read_findings(args.gold)), indent=2))


if __name__ == "__main__":
    main()
