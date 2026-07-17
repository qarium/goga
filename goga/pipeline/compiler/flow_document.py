"""The ``FlowDocument`` dataclass — output afm flow-file model.

An afm flow-file is a single flat YAML document with up to four top-level keys
(prompt (when present), name, description, stages) — no segmentation, no header
sub-object. ``FlowDocument`` mirrors that flatness: it carries the optional
top-level ``prompt`` (populated from a workflow's prompt when one is supplied,
``None`` otherwise), the carried 1:1 ``name`` and ``description`` from
``PipelineHeader``, and the ordered list of ``FlowStage`` items. It is the only
object ``serialize_flow`` accepts as input.
"""

from __future__ import annotations

from dataclasses import dataclass

from .flow_stage import FlowStage


@dataclass(kw_only=True)
class FlowDocument:
    """Output afm flow-file — a flat document with up to four top-level keys.

    Args:
        prompt: Top-level flow prompt, or ``None`` when no workflow supplied
            one. Emitted as the first top-level key when not ``None``;
            omitted entirely when ``None``.
        name: Top-level flow name (carried 1:1 from PipelineHeader name).
        description: Top-level flow description (carried 1:1 from
            PipelineHeader description).
        stages: Ordered list of flow stages, output as the stages list.
    """

    prompt: str | None = None
    name: str
    description: str
    stages: list[FlowStage]
