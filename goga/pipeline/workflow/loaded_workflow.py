"""The ``LoadedWorkflow`` dataclass — the result of the workflow loading chain."""

from __future__ import annotations

from dataclasses import dataclass

from .resolved_profile import ResolvedProfile
from .workflow_document import WorkflowDocument


@dataclass(frozen=True, kw_only=True)
class LoadedWorkflow:
    """A workflow-file loaded under an activation context: document plus active profile.

    Args:
        document: the parsed :class:`WorkflowDocument` (of the rendered text).
        profile: the :class:`ResolvedProfile` active at rendering, or ``None``
            when the render ran with an empty context.
    """

    document: WorkflowDocument
    profile: ResolvedProfile | None
