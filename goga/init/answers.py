from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True, kw_only=True)
class GogaConfigAnswers:
    """Answers for creating .goga/config.yml."""

    language: str
    agent: str
    image: str
    env: dict
    codemanifest_usages: Optional[dict] = None
    codemanifest_annotations: Optional[str] = None


@dataclass(frozen=True, kw_only=True)
class InitAnswers:
    """User answers container. Extensible for future config files."""

    goga_config: GogaConfigAnswers
