"""Naming and time primitives for the history domain."""

from __future__ import annotations

import re
from datetime import datetime


def normalize_topic_slug(name: str) -> str:
    """Normalize a branch name into the history topic slug.

    Args:
        name: Branch name as entered by the user.

    Returns:
        The history topic slug, possibly empty — a fully non-ASCII or
        all-separator name yields the empty string; the caller owns the
        empty-slug decision. No git, no filesystem, no side effects.
    """
    lowered = name.lower()
    ascii_only = "".join(character for character in lowered if character.isascii())
    hyphened = re.sub(r"[^a-z0-9]", "-", ascii_only)
    collapsed = re.sub(r"-{2,}", "-", hyphened)
    return collapsed.strip("-")


def current_year() -> str:
    """Return the current local calendar year as a 4-digit string.

    Returns:
        The current calendar year — naive local time, no timezone, no
        override — as a four-digit string.
    """
    return f"{datetime.now().year:04d}"  # noqa: DTZ005 — bare now() is the mandated test mock target
