"""The ``ResolvedProfile`` dataclass — the active profile as a single value."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .profile_source import ProfileSource


@dataclass(frozen=True, kw_only=True)
class ResolvedProfile:
    """The active profile: its name, its whole content mapping, and where it was found.

    Args:
        name: the resolved profile name.
        data: the entire profile content — every top-level key becomes a
            template variable at rendering (the rendering context source).
        source: where the profile was found — a :class:`ProfileSource` value
            (project or home).
    """

    name: str
    data: dict[str, Any]
    source: ProfileSource
