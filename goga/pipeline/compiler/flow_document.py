"""The ``FlowDocument`` dataclass — output afm flow-file model.

An afm flow-file is a single flat YAML document with three top-level keys
(name, description, stages) — no segmentation, no header sub-object.
``FlowDocument`` mirrors that flatness: it carries the carried 1:1 ``name`` and
``description`` from ``PipelineHeader`` and the ordered list of ``FlowStage``
items. It is the only object ``serialize_flow`` accepts as input.
"""

from __future__ import annotations

from dataclasses import dataclass

from .flow_stage import FlowStage


@dataclass(kw_only=True)
class FlowDocument:
    """Output afm flow-file — a flat document with three top-level keys.

    Args:
        name: Top-level flow name (carried 1:1 from PipelineHeader name).
        description: Top-level flow description (carried 1:1 from
            PipelineHeader description).
        stages: Ordered list of flow stages, output as the stages list.
    """

    name: str
    description: str
    stages: list[FlowStage]
