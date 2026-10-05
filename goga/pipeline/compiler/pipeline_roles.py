"""The ``PipelineRoles`` dataclass — data model of the header-level ``roles`` directive."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class PipelineRoles:
    """Data model of the header-level ``roles`` directive — three optional inline prompt overrides.

    Args:
        planner: Inline prompt text that fully replaces (no merging) the
            default ``planning.md`` prompt during pipeline-run materialization,
            or ``None``.
        executor: Inline prompt text that fully replaces (no merging) the
            default ``implementation.md`` prompt, or ``None``.
        reviewer: Inline prompt text that fully replaces (no merging) the
            default ``review.md`` prompt, or ``None``.
    """

    planner: str | None = None
    executor: str | None = None
    reviewer: str | None = None
