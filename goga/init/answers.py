from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class GogaConfigAnswers:
    """Answers for creating .goga/config.yml."""

    language: str
    image: str
    agent: str | None = None
    pipeline_agent: str | None = None
    pipeline_env: dict | None = None
    env: dict | None = None
    codemanifest_usages: dict | None = None
    codemanifest_annotations: str | None = None
    dockerfile_path: str | None = None


@dataclass(frozen=True, kw_only=True)
class InitAnswers:
    """User answers container. Extensible for future config files."""

    goga_config: GogaConfigAnswers
