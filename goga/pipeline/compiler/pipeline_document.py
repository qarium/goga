"""The ``PipelineDocument`` dataclass — aggregated representation of a pipeline-file."""

from __future__ import annotations

from dataclasses import dataclass

from .body_format import BodyFormat
from .phases_body import PhasesBody
from .pipeline_header import PipelineHeader
from .stages_body import StagesBody


@dataclass(kw_only=True)
class PipelineDocument:
    """Aggregated pipeline-file document — header, format, and body in one value.

    Args:
        header: Parsed pipeline-file header (name, description, optional roles).
        format: Detected body format — PHASES or STAGES.
        body: Parsed body. ``PhasesBody`` when format is PHASES,
            ``StagesBody`` when format is STAGES.
    """

    header: PipelineHeader
    format: BodyFormat
    body: PhasesBody | StagesBody
