"""The ``StageStep`` dataclass — one entry of a stages-DSL body."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .pipeline_assistant import PipelineAssistant


@dataclass(kw_only=True)
class StageStep:
    """One entry of a stages-DSL body.

    Args:
        name: Step id (the map key).
        title: Display label (the value of title inside the value).
        depends_on: List of predecessor step ids. Tristate — ``None`` means
            "no ``depends_on`` key written", an empty list means "explicit
            empty dependency" (written as ``depends_on: []``).
        body: Verbatim copy of every other field in the value, excluding
            title, depends_on, and the extracted assistants key.
        assistants: The step's pipeline assistant declarations keyed by
            assistant name, in authored order — ``None`` when the source body
            carries no assistants key or an empty map.
    """

    name: str
    title: str
    depends_on: list[str] | None
    body: dict[str, Any]
    assistants: dict[str, PipelineAssistant] | None = None
