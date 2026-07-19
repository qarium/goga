"""The ``PhaseStep`` dataclass — one element of a phases-DSL body.

A phases-DSL body is a YAML list; each item is a single ``PhaseStep`` carrying
its ``name`` (the step id), ``title`` (the display label) and a verbatim
``body`` dict of every other field in the item (agents, prompt, skills,
interactive, and any extra fields) excluding name and title.

``PhaseStep`` does NOT carry ``depends_on`` — the compiler derives it from list
position when building a ``FlowStage``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(kw_only=True)
class PhaseStep:
    """One element of a phases-DSL body.

    Args:
        name: Step id (the value of the name field inside the list item).
        title: Display label (the value of title inside the item).
        body: Verbatim copy of every other field in the item, excluding name
            and title.
    """

    name: str
    title: str
    body: dict[str, Any]
