"""
Centralized collection of errors and warnings during the build pipeline.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass
class Diagnostic:
    severity: Severity
    message: str
    source: str | None = None  # ex: .odt file path

    def __str__(self) -> str:  # pragma: no cover - trivial
        prefix = "ERROR" if self.severity is Severity.ERROR else "WARNING"
        loc = f" [{self.source}]" if self.source else ""
        return f"{prefix}{loc}: {self.message}"


class Diagnostics:
    """Changeable diagnostics collector, shared between components."""

    def __init__(self) -> None:
        self._items: list[Diagnostic] = []

    def error(self, message: str, source: str | None = None) -> None:
        self._items.append(Diagnostic(Severity.ERROR, message, source))

    def warning(self, message: str, source: str | None = None) -> None:
        self._items.append(Diagnostic(Severity.WARNING, message, source))

    @property
    def errors(self) -> list[Diagnostic]:
        return [d for d in self._items if d.severity is Severity.ERROR]

    @property
    def warnings(self) -> list[Diagnostic]:
        return [d for d in self._items if d.severity is Severity.WARNING]

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    def __iter__(self):
        return iter(self._items)

    def __len__(self) -> int:
        return len(self._items)

    def extend(self, other: "Diagnostics") -> None:
        self._items.extend(other._items)

    def report(self) -> str:
        lines = [str(d) for d in self._items]
        return "\n".join(lines)


class AsteriaError(Exception):
    """Fatal error that immediately halts the build (e.g., invalid YAML)."""
