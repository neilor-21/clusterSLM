"""Build a tiny reproducible starter dataset for ClusterSLM SLM fine-tuning.

IMPORTANT: this is synthetic smoke-test data, not a scientifically adequate
training/evaluation corpus. Replace/augment it with reviewed, licensed examples.
"""
import json
import random
from pathlib import Path

SYSTEM_PROMPT = (
    "You are a source-code security reviewer. Analyze the supplied code context. "
    "Return ONLY a JSON object of the form {\"findings\": [...]} with vulnerability, "
    "cwe, symbol, confidence, and evidence for each finding. If no issue is supported, "
    "return {\"findings\": []}. Do not invent evidence."
)

EXAMPLES = [
    ("sql_vulnerable", "CWE-89", "Potential SQL Injection",
     "def fetch_user(user_id):\n    query = f\"SELECT * FROM users WHERE id = {user_id}\"\n    return db.execute(query)",
     True, "Dynamic SQL interpolation reaches db.execute."),
    ("sql_safe", "CWE-89", "Potential SQL Injection",
     "def fetch_user(user_id):\n    query = \"SELECT * FROM users WHERE id = ?\"\n    return db.execute(query, (user_id,))", False, ""),
    ("command_vulnerable", "CWE-78", "Potential Command Injection",
     "def ping(host):\n    cmd = \"ping \" + host\n    return subprocess.run(cmd, shell=True)", True,
     "A dynamically constructed command is executed with shell=True."),
    ("command_safe", "CWE-78", "Potential Command Injection",
     "def ping(host):\n    return subprocess.run([\"ping\", host], shell=False)", False, ""),
    ("path_vulnerable", "CWE-22", "Potential Path Traversal",
     "def read_doc(filename):\n    path = os.path.join(\"/srv/docs\", filename)\n    return open(path).read()", True,
     "A filename-derived path reaches a file-read sink without a recognized containment guard."),
    ("path_safe", "CWE-22", "Potential Path Traversal",
     "def read_doc(filename):\n    path = os.path.realpath(os.path.join(\"/srv/docs\", filename))\n    if not path.startswith(\"/srv/docs/\"):\n        raise ValueError()\n    return open(path).read()", False, ""),
    ("deser_vulnerable", "CWE-502", "Potential Insecure Deserialization",
     "def load_session(raw):\n    return pickle.loads(raw)", True,
     "pickle.loads deserializes a byte stream; determine whether it can be attacker-controlled."),
    ("deser_safe", "CWE-502", "Potential Insecure Deserialization",
     "def load_session(raw):\n    return json.loads(raw)", False, ""),
    ("secret_vulnerable", "CWE-798", "Potential Hard-coded Credentials",
     "def connect():\n    return db.connect(password=\"prod-password-123\")", True,
     "A credential-like argument contains a hard-coded string literal."),
    ("secret_safe", "CWE-798", "Potential Hard-coded Credentials",
     "def connect():\n    return db.connect(password=os.environ[\"DB_PASSWORD\"])", False, ""),
]


def build_examples(repeats=5, seed=42):
    rng = random.Random(seed)
    rows = []
    for repeat in range(repeats):
        for name, cwe, title, code, vulnerable, evidence in EXAMPLES:
            symbol = f"sample_{repeat}.{name}"
            payload = {"partition_id": repeat + 1, "internal_symbols": [symbol],
                       "boundary_incoming": [], "boundary_outgoing": [],
                       "scoped_code": {symbol: code}}
            if vulnerable:
                findings = [{"vulnerability": title, "cwe": cwe, "symbol": symbol,
                             "confidence": 0.7, "evidence": evidence}]
            else:
                findings = []
            rows.append({"messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": "Review this partition context:\n" + json.dumps(payload)},
                {"role": "assistant", "content": json.dumps({"findings": findings})},
            ], "example_id": f"{name}_{repeat}", "synthetic": True})
    rng.shuffle(rows)
    return rows


def write_jsonl(path, rows):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps({"messages": row["messages"]}, ensure_ascii=False) + "\n")


def build_dataset(output_dir="data/synthetic", repeats=5, seed=42):
    rows = build_examples(repeats=repeats, seed=seed)
    # Deterministic split; note that variants are template-derived and can leak
    # patterns across splits, so use this only as a pipeline smoke test.
    split = max(1, int(len(rows) * 0.8))
    train, test = rows[:split], rows[split:]
    out = Path(output_dir)
    write_jsonl(out / "train.jsonl", train)
    write_jsonl(out / "test.jsonl", test)
    metadata = {"synthetic": True, "seed": seed, "repeats": repeats,
                "total": len(rows), "train": len(train), "test": len(test),
                "warning": "Smoke-test data only; do not report these results as benchmark performance."}
    (out / "dataset_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Generated {len(train)} train and {len(test)} test examples in {out}")


if __name__ == "__main__":
    build_dataset()
