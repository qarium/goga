"""The ``FlowDocument`` dataclass — output afm flow-file model."""

from __future__ import annotations

from dataclasses import dataclass

from .flow_memory import FlowMemory
from .flow_stage import FlowStage


@dataclass(kw_only=True)
class FlowDocument:
    """Output afm flow-file — a flat document with up to six top-level keys.

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
            participate. Emitted between ``description`` and ``stages`` when
            not ``None``; omitted entirely when ``None`` — byte-identical
            output for memory-free workflows.
        stages: Ordered list of flow stages, output as the stages list.
    """

    prompt: str | None = None
    root_dir: str | None = None
    name: str
    description: str
    memory: FlowMemory | None = None
    stages: list[FlowStage]
