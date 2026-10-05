"""The ``PipelineHeader`` dataclass — name, description, and optional role overrides."""

from __future__ import annotations

from dataclasses import dataclass

from .pipeline_roles import PipelineRoles


@dataclass(kw_only=True)
class PipelineHeader:
    """Header of an input pipeline-file — name, description, optional role overrides.

    Args:
        name: Pipeline name (e.g. "Goga feature").
        description: Short pipeline description (e.g. "Feature implementation").
        roles: Optional inline prompt overrides (``PipelineRoles``) parsed from
            the header-level ``roles`` block. ``None`` when the block is absent
            or an empty mapping. Not carried into the ``FlowDocument``.
    """

    name: str
    description: str
    roles: PipelineRoles | None = None
