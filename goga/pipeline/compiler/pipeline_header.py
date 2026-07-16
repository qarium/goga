"""The ``PipelineHeader`` dataclass — name, description, and optional agent overrides.

A goga DSL pipeline-file has a header (name + description) followed by a
``---`` separator and a body. ``PipelineHeader`` carries the header fields
parsed from the segment before the separator. ``compile_flow`` carries name and
description 1:1 into the ``FlowDocument`` (its name and description fields).

The optional ``agents`` field carries inline prompt overrides parsed from the
header-level ``agents`` block (four fixed keys: planning, implementation,
review, summary). It is ``None`` when the block is absent or an empty mapping;
it is surfaced to the consumer through ``PipelineDocument`` and is intentionally
NOT carried into the compiled ``FlowDocument`` (it is a goga-side artifact).
"""

from __future__ import annotations

from dataclasses import dataclass

from .pipeline_agents import PipelineAgents


@dataclass(kw_only=True)
class PipelineHeader:
    """Header of an input pipeline-file — name, description, optional agent overrides.

    Args:
        name: Pipeline name (e.g. "Goga feature").
        description: Short pipeline description (e.g. "Feature implementation").
        agents: Optional inline prompt overrides (``PipelineAgents``) parsed from
            the header-level ``agents`` block. ``None`` when the block is absent
            or an empty mapping. Not carried into the ``FlowDocument``.
    """

    name: str
    description: str
    agents: PipelineAgents | None = None
