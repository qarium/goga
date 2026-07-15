"""The ``FlowStage`` dataclass — one stage of an output afm flow-file.

A flow-file has a ``stages`` list; each item is a single ``FlowStage`` carrying
its ``id`` (the step identifier), ``name`` (the display label), ``depends_on``
(predecessor step ids or ``None``) and ``fields`` (extra step fields in
canonical key order). Both ``PhaseStep`` and ``StageStep`` converge into this
type during compilation.

``depends_on`` is tristate: ``None`` produces no depends_on key in output;
an empty list produces ``depends_on: []``. ``fields`` insertion order IS the
output order — the serializer iterates it as-is, so the compiler must build it
in canonical order.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(kw_only=True)
class FlowStage:
    """One stage of an output afm flow-file.

    Args:
        id: Step identifier (output as a dash-prefixed id item).
        name: Display label (output as the name field).
        depends_on: Predecessor step ids, or ``None`` when absent.
        fields: Extra step fields in canonical key order.
    """

    id: str
    name: str
    depends_on: list[str] | None
    fields: dict[str, Any]
