"""Language detection and adapter dispatch for repository ingestion.

Only languages with a registered parser adapter are parsed. Other recognized
source files are reported as detected-but-not-yet-analyzed, never silently
presented as fully supported.
"""
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from language_adapters.python_adapter import PythonAdapter
from language_adapters.javascript_adapter import JavaScriptAdapter


# Extension detection is intentionally broader than parser support.
EXTENSION_LANGUAGE = {
    ".py": "python",
    ".js": "javascript", ".jsx": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".java": "java",
    ".sql": "sql",
    ".html": "html", ".htm": "html",
    ".css": "css", ".scss": "scss", ".sass": "sass",
    ".json": "json", ".yaml": "yaml", ".yml": "yaml", ".toml": "toml", ".xml": "xml",
    ".c": "c", ".h": "c-header", ".cc": "cpp", ".cpp": "cpp", ".cxx": "cpp", ".hpp": "cpp-header",
    ".go": "go", ".rs": "rust", ".cs": "csharp", ".php": "php", ".rb": "ruby",
    ".kt": "kotlin", ".kts": "kotlin", ".swift": "swift", ".sh": "shell", ".bash": "shell",
}

IGNORED_DIRS = {
    ".git", ".hg", ".svn", ".venv", "venv", "env", "node_modules", "__pycache__",
    ".mypy_cache", ".pytest_cache", ".tox", "build", "dist", "target", "vendor",
    ".next", ".nuxt", "coverage",
}


@dataclass
class RepositoryScan:
    root: Path
    parsed_files: list = field(default_factory=list)
    detected_languages: dict = field(default_factory=dict)
    parsed_languages: list = field(default_factory=list)
    unsupported_files: list = field(default_factory=list)
    skipped_files: list = field(default_factory=list)
    source_file_count: int = 0

    @property
    def unsupported_language_counts(self):
        counts = Counter(item["language"] for item in self.unsupported_files)
        return dict(sorted(counts.items()))


class LanguageRegistry:
    def __init__(self, adapters=None):
        adapters = adapters if adapters is not None else [PythonAdapter(), JavaScriptAdapter()]
        self.adapters_by_extension = {
            extension.lower(): adapter
            for adapter in adapters
            for extension in adapter.extensions
        }

    def detect_language(self, path: Path):
        return EXTENSION_LANGUAGE.get(path.suffix.lower())

    def get_adapter(self, path: Path):
        return self.adapters_by_extension.get(path.suffix.lower())

    def scan_repository(self, repo_path) -> RepositoryScan:
        root = Path(repo_path).resolve()
        if not root.exists() or not root.is_dir():
            raise NotADirectoryError(f"Repository path is not a directory: {root}")

        result = RepositoryScan(root=root)
        language_counts = Counter()
        parsed_languages = set()

        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            relative = path.relative_to(root)
            if any(part in IGNORED_DIRS for part in relative.parts):
                continue

            language = self.detect_language(path)
            if language is None:
                continue

            result.source_file_count += 1
            language_counts[language] += 1
            adapter = self.get_adapter(path)
            if adapter is None:
                result.unsupported_files.append({
                    "path": str(relative),
                    "language": language,
                    "reason": "Language detected; parser adapter not implemented yet",
                })
                continue

            try:
                result.parsed_files.append(adapter.parse_file(path))
                parsed_languages.add(language)
            except RuntimeError as exc:
                # Optional parser dependencies may not be installed yet. Report
                # the file as detected-but-not-analyzed rather than aborting the scan.
                result.unsupported_files.append({
                    "path": str(relative),
                    "language": language,
                    "reason": str(exc),
                })
            except (SyntaxError, UnicodeDecodeError, OSError, ValueError) as exc:
                result.skipped_files.append({
                    "path": str(relative),
                    "language": language,
                    "reason": str(exc),
                })

        result.detected_languages = dict(sorted(language_counts.items()))
        result.parsed_languages = sorted(parsed_languages)
        return result


_default_registry = LanguageRegistry()


def scan_repository(repo_path) -> RepositoryScan:
    """Scan a repository and return parsed files plus explicit coverage metadata."""
    return _default_registry.scan_repository(repo_path)
