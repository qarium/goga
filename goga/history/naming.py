"""Naming and time primitives for the history domain.

The two routines declared in the cell CODEMANIFEST with ``location:
naming.py``: the pure slug transformer — the single owner of the topic slug
grammar — and the single current-year point shared by every history
consumer. Both are pure — no git, no filesystem, no caching.
"""

from __future__ import annotations

import re
from datetime import datetime


def normalize_topic_slug(name: str) -> str:
    """Normalize a branch name into the history topic slug.

    Deterministic pure string transformation: lowercase the name, drop every
    non-ASCII character (no transliteration), replace each remaining character
    outside ``[a-z0-9]`` with a hyphen, collapse repeat hyphens into one, and
    trim leading and trailing hyphens. Lowercasing happens BEFORE the ASCII
    filter, so a name like ``"aБb"`` yields ``"ab"`` and the Turkish dotted
    capital ``"İ"`` lowercases to ``"i"`` plus a combining dot that the filter
    drops.

    A fully non-ASCII or all-separator name yields the empty string — a valid
    output. No fallback is returned for an empty result; the caller owns the
    empty-slug decision.

    Args:
        name: Branch name as entered by the user.

    Returns:
        The history topic slug (possibly empty). No git, no filesystem, no
        side effects.
    """
    lowered = name.lower()
    ascii_only = "".join(character for character in lowered if character.isascii())
    hyphened = re.sub(r"[^a-z0-9]", "-", ascii_only)
    collapsed = re.sub(r"-{2,}", "-", hyphened)
    return collapsed.strip("-")


def current_year() -> str:
    """Return the current local calendar year as a 4-digit string.

    The single time point for every history consumer: naive local time — the
    history tree is organized by the host's calendar year — with no timezone
    and no override. Pure and uncached: evaluated anew on each call.
    """
    return f"{datetime.now().year:04d}"  # noqa: DTZ005 — bare now() is the mandated test mock target
