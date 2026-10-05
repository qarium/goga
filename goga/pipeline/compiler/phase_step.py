"""The ``PhaseStep`` dataclass — one element of a phases-DSL body."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(kw_only=True)
class PhaseStep:
    """One element of a phases-DSL body; carries no ``depends_on`` — the compiler derives it from list position.

    Args:
        name: Step id (the value of the name field inside the list item).
        title: Display label (the value of title inside the item).
        body: Verbatim copy of every other field in the item, excluding name
            and title.
    """

    name: str
    title: str
    body: dict[str, Any]
