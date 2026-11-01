"""The ``FlowDocument`` dataclass — output afm flow-file model."""

from __future__ import annotations

from dataclasses import dataclass

from .flow_collaboration import FlowCollaboration
from .flow_memory import FlowMemory
from .flow_stage import FlowStage
from .flow_team_member import FlowTeamMember


@dataclass(kw_only=True)
class FlowDocument:
    """Output afm flow-file — a flat document with up to eight top-level keys.

    Args:
        prompt: Top-level flow prompt, or ``None`` when no workflow supplied
            one. Emitted as the first top-level key when not ``None``;
            omitted entirely when ``None``.
        root_dir: Top-level afm ``root_dir`` directive, or ``None`` when the
            caller did not supply one. Emitted immediately after ``prompt``
            (when present) and before ``name`` when not ``None``; omitted
            entirely when ``None``. Populated by the consumer (the
            ``run_pipeline`` routine in ``goga/pipeline``) from the
            in-container project root (``Path.cwd()`` resolves to
            ``/workspace`` inside the goga container); the compiler itself
            performs no environment-variable reads.
        name: Top-level flow name (carried 1:1 from PipelineHeader name).
        description: Top-level flow description (carried 1:1 from
            PipelineHeader description).
        memory: The compiled memory block, or ``None`` when memory does not
            participate. Emitted between ``description`` and
            ``collaboration`` when not ``None``; omitted entirely when
            ``None`` — byte-identical output for memory-free workflows.
        collaboration: The compiled collaboration block — constructed on
            every compilation (mode ``"assistants"`` in every compiled
            flow). Emitted between ``memory`` and ``team`` when not
            ``None``.
        team: The compiled team list — one ``FlowTeamMember`` per catalog
            entry in authored order; an empty list or ``None`` omits the
            key from the output entirely.
        stages: Ordered list of flow stages, output as the stages list.
    """

    prompt: str | None = None
    root_dir: str | None = None
    name: str
    description: str
    memory: FlowMemory | None = None
    collaboration: FlowCollaboration | None = None
    team: list[FlowTeamMember] | None = None
    stages: list[FlowStage]
