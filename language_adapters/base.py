"""Common contracts shared by language-specific source parsers."""
from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol, runtime_checkable


@dataclass
class ImportInfo:
    """A normalized import/dependency reference extracted from a source file."""

    module: str
    level: int = 0

    def __repr__(self):
        return f"ImportInfo(module={self.module!r}, level={self.level})"


@dataclass
class FileInfo:
    """Language-neutral container consumed by the graph-building pipeline.

    Adapters may populate the fields they can reliably extract. Keeping a common
    shape lets graph/partition/reporting code avoid language-specific branches.
    """

    path: Path
    language: str = "unknown"
    imports: list = field(default_factory=list)
    classes: list = field(default_factory=list)
    functions: list = field(default_factory=list)
    calls: list = field(default_factory=list)
    call_map: dict = field(default_factory=dict)


@runtime_checkable
class LanguageAdapter(Protocol):
    language: str
    extensions: tuple[str, ...]

    def parse_file(self, path: Path) -> FileInfo:
        """Parse one file into the common FileInfo representation."""
        ...
