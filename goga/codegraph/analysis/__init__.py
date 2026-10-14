"""Facade of the analysis cell — the three-stage facts pipeline."""

from .collect import collect_facts

__all__ = [
    "collect_facts",
]
