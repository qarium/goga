"""Facade of the drift cell — the structural drift report between the declared and code-derived views."""

from .compare import DriftEntry, compare_views, scope_entries
from .drift import drift

__all__ = [
    "DriftEntry",
    "compare_views",
    "drift",
    "scope_entries",
]
