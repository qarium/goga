"""The ``WorkflowBuild`` dataclass — the top-level workflow build block."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class WorkflowBuild:
    """The strict six-field build block of a workflow-file — build-pass settings the workflow may provide.

    All fields default to ``None`` (absent); an absent field never overrides
    the configuration. Built only by ``parse_workflow`` from the validated
    block; the build path owns the layering.

    Args:
        agent: tasks-pass agent override, or ``None`` when absent.
        env: tasks-pass env overlay (string map), or ``None`` when absent.
        review_agent: review-pass agent override, or ``None`` when absent.
        review_env: review-pass env overlay, or ``None`` when absent.
        review_additional_agent: external-review agent override, or ``None``
            when absent.
        review_additional_env: external-review env overlay, or ``None`` when
            absent.
    """

    agent: str | None = None
    env: dict[str, str] | None = None
    review_agent: str | None = None
    review_env: dict[str, str] | None = None
    review_additional_agent: str | None = None
    review_additional_env: dict[str, str] | None = None
