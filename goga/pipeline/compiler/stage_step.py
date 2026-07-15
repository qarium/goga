"""The ``StageStep`` dataclass — one entry of a stages-DSL body.

A stages-DSL body is a YAML mapping keyed by step id; each value is a single
``StageStep`` carrying its ``name`` (the map key), ``description`` (the display
label), ``depends_on`` (predecessor step ids or ``None`` when absent) and a
verbatim ``body`` dict of every other field (excluding description and
depends_on; name is the map key, also not part of the body).

``depends_on`` is tristate: ``None`` means "no depends_on written" (the
compiler writes no depends_on key), while an empty list means "explicit empty
dependency" (written as ``depends_on: []``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(kw_only=True)
class StageStep:
    """One entry of a stages-DSL body.

    Args:
        name: Step id (the map key).
        description: Display label (the value of description inside the value).
        depends_on: List of predecessor step ids, or ``None`` when the field is
            absent from the source value.
        body: Verbatim copy of every other field in the value, excluding
            description and depends_on.
    """

    name: str
    description: str
    depends_on: list[str] | None
    body: dict[str, Any]
