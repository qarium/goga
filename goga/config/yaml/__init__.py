"""The yaml configuration cell — the environment-aware YAML load (``!ENV``)."""

from __future__ import annotations

from .loader import parse_env_yaml

__all__ = [
    "parse_env_yaml",
]
