"""Backward-compatible parser API backed by the language-adapter registry.

Existing modules can keep importing parse_file and discover_repository while
new code uses scan_repository to inspect multi-language repository coverage.
"""
from pathlib import Path

from language_adapters.base import FileInfo, ImportInfo
from language_adapters.python_adapter import PythonAdapter
from language_adapters.registry import scan_repository

# Preserve the old public class name for code that imports Parser directly.
# New code should use PythonAdapter via the registry.
Parser = PythonAdapter
Import = ImportInfo


def parse_file(path):
    """Parse one Python file; retained for backward compatibility."""
    path = Path(path)
    if path.suffix.lower() != ".py":
        raise ValueError(f"parse_file currently supports Python only: {path}")
    return PythonAdapter().parse_file(path)


def discover_repository(repo_path):
    """Return successfully parsed files, preserving the original API."""
    scan = scan_repository(repo_path)
    for item in scan.skipped_files:
        if item["language"] == "python":
            print(f"Skipping {item['path']}: {item['reason']}")
    return scan.parsed_files
