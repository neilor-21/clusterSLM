"""Conservative, heuristic source-to-sink checks for Python and JS/TS snippets.

This is a baseline static analyzer, not a proof of exploitability or a replacement
for a mature taint-analysis engine. Findings are deliberately marked as potential.
"""
from __future__ import annotations

import re


def _has_dynamic_sql(code: str) -> bool:
    has_query_sink = re.search(r"\.(?:execute|executemany|query)\s*\(", code, re.I) or re.search(r"\b(?:execute|query)\s*\(", code, re.I)
    dynamic_sql = (
        re.search(r"f[\"'][^\n]*\{", code)
        or re.search(r"`[^`]*\$\{", code)
        or re.search(r"(?:query|sql|statement)\s*=\s*[^\n]*(?:\+|\.format\s*\(|%\s*\(?|\bf[\"'])", code, re.I)
        or re.search(r"(?:execute|query)\s*\(\s*[^,\n]*\+", code, re.I)
    )
    # Parameterized SQL is a strong safe signal when it is the only sink form.
    parameterized = re.search(r"\.(?:execute|query)\s*\(\s*[^,]+,\s*\(", code, re.I)
    return bool(has_query_sink and dynamic_sql and not parameterized)


def _has_command_injection(code: str) -> bool:
    shell_true = re.search(r"\bshell\s*=\s*True\b", code)
    dangerous_api = re.search(r"\b(?:subprocess\.(?:run|Popen|call|check_call|check_output)|os\.system|child_process\.(?:exec|execSync))\s*\(", code)
    dynamic = bool(
        re.search(r"f[\"'][^\n]*\{", code)
        or re.search(r"`[^`]*\$\{", code)
        or re.search(r"(?:command|cmd)\s*=\s*[^\n]*\+", code, re.I)
        or re.search(r"\b(?:os\.system|child_process\.exec(?:Sync)?)\s*\(\s*[^)\n]*\+", code)
    )
    return bool(dangerous_api and (shell_true or dynamic or re.search(r"\bos\.system\s*\(", code)))


def _has_path_traversal(code: str) -> bool:
    file_sink = re.search(r"\b(?:open|readFile|readFileSync|createReadStream|send_file)\s*\(", code)
    path_join = re.search(r"(?:os\.path\.join|path\.join|resolve)\s*\(", code)
    userish = re.search(r"\b(?:filename|file_name|filepath|file_path|path|name|req\.params|request\.args)\b", code, re.I)
    guarded = re.search(r"\b(?:commonpath|realpath|resolve)\b", code) and re.search(r"(?:startswith|commonpath|is_relative_to|\.startsWith\s*\()", code)
    return bool(file_sink and userish and (path_join or re.search(r"\bopen\s*\(\s*(?:filename|file_path|path|name)\b", code)) and not guarded)


def _has_unsafe_deserialization(code: str) -> bool:
    if re.search(r"\bpickle\.(?:loads|load)\s*\(", code):
        return True
    # yaml.load is risky unless a safe loader is explicitly supplied.
    yaml_load = re.search(r"\byaml\.load\s*\(", code)
    safe_loader = re.search(r"Loader\s*=\s*yaml\.SafeLoader|Loader\s*=\s*SafeLoader|safe_load\s*\(", code)
    return bool(yaml_load and not safe_loader)


def _has_hardcoded_secret(code: str) -> bool:
    assignment = re.search(
        r"\b(?:password|passwd|secret|api[_-]?key|access[_-]?token)\b\s*[:=]\s*(['\"])([^'\"]{4,})\1",
        code,
        re.I,
    )
    if not assignment:
        return False
    value = assignment.group(2).strip().lower()
    return value not in {"changeme", "placeholder", "example", "your-secret", "redacted"} and "${" not in value


RULES = [
    ("CWE-89", "Potential SQL Injection", _has_dynamic_sql,
     "Dynamic SQL construction appears to reach an execute/query sink; verify parameterization and input flow."),
    ("CWE-78", "Potential Command Injection", _has_command_injection,
     "A command-execution API appears to receive dynamically constructed input or use shell execution."),
    ("CWE-22", "Potential Path Traversal", _has_path_traversal,
     "A file-access sink appears to use a path influenced by a filename/path value without a recognized containment guard."),
    ("CWE-502", "Potential Insecure Deserialization", _has_unsafe_deserialization,
     "An unsafe deserialization API is present; confirm whether the serialized data is trusted."),
    ("CWE-798", "Potential Hard-coded Credentials", _has_hardcoded_secret,
     "A credential-like setting appears to contain a literal value rather than a secret reference."),
]


def analyze_symbol(symbol: str, code: str, language: str = "unknown") -> list[dict]:
    """Return heuristic findings for one scoped symbol body."""
    findings = []
    lines = code.splitlines()
    for cwe, title, predicate, evidence in RULES:
        try:
            matched = predicate(code)
        except (re.error, TypeError):
            matched = False
        if not matched:
            continue
        line_number = None
        # Give a useful approximate sink line for reports.
        patterns = {
            "CWE-89": r"execute|executemany|\.query\s*\(",
            "CWE-78": r"subprocess\.|os\.system|child_process\.",
            "CWE-22": r"open\s*\(|readFile|createReadStream|send_file",
            "CWE-502": r"pickle\.(?:loads|load)|yaml\.load",
            "CWE-798": r"password|passwd|secret|api[_-]?key|access[_-]?token",
        }
        for idx, line in enumerate(lines, 1):
            if re.search(patterns[cwe], line, re.I):
                line_number = idx
                break
        findings.append({
            "vulnerability": title,
            "cwe": cwe,
            "symbol": symbol,
            "confidence": 0.65,
            "evidence": evidence,
            "line": line_number,
            "language": language,
            "detector": "static-heuristic",
            "validation_status": "needs_review",
        })
    return findings


def analyze_partition_context(context: dict) -> dict:
    """Analyze each scoped symbol and return the pipeline's standard result shape."""
    findings = []
    language_by_symbol = context.get("symbol_languages", {})
    kind_by_symbol = context.get("symbol_kinds", {})
    for symbol, code in (context.get("scoped_code") or {}).items():
        # Analyze functions/methods only; class bodies can contain the same method
        # code and would otherwise produce duplicate class-level alerts.
        if kind_by_symbol.get(symbol) == "class":
            continue
        findings.extend(analyze_symbol(symbol, code, language_by_symbol.get(symbol, "unknown")))
    return {"partition_id": context["partition_id"], "findings": findings}
