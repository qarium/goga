"""The ``ProfileSource`` enum — the origin of a resolved profile."""

from __future__ import annotations

from enum import Enum


class ProfileSource(str, Enum):
    """Origin of a resolved profile; ``str``-based so each member serializes as its plain value.

    Attributes:
        PROJECT: origin is the project-level ``<cwd>/.goga/profiles/`` directory
            (committed alongside the project).
        HOME: origin is the home-level ``~/.goga/profiles/`` directory
            (personal, carried in the decoded home bundle).
    """

    PROJECT = "project"
    """Origin = project-level ``<cwd>/.goga/profiles/`` (committed)."""

    HOME = "home"
    """Origin = home-level ``~/.goga/profiles/`` (personal, carried in the decoded home bundle)."""
