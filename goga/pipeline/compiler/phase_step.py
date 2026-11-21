"""The ``PhaseStep`` dataclass — one element of a phases-DSL body."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .pipeline_assistant import PipelineAssistant


@dataclass(kw_only=True)
class PhaseStep:
    """One element of a phases-DSL body; carries no ``depends_on`` — the compiler derives it from list position.

    Args:
        name: Step id (the value of the name field inside the list item).
        title: Display label (the value of title inside the item).
        body: Verbatim copy of every other field in the item, excluding name,
            title, and the extracted assistants key.
        assistants: The step's pipeline assistant declarations keyed by
            assistant name, in authored order — ``None`` when the source body
            carries no assistants key or an empty map.
    """

    name: str
    title: str
    body: dict[str, Any]
    assistants: dict[str, PipelineAssistant] | None = None
