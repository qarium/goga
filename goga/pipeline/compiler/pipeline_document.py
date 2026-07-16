"""The ``PipelineDocument`` dataclass — aggregated representation of a pipeline-file.

A parsed pipeline-file combines three things: its header (``PipelineHeader``),
its detected body format (``BodyFormat``), and its typed body (``PhasesBody``
or ``StagesBody``). ``PipelineDocument`` aggregates these into a single value
so consumers (``run_pipeline``) can obtain the parsed representation — including
``header.agents`` — from a single return value without re-invoking
``parse_dsl``.

``compile_flow`` builds this dataclass from ``parse_dsl``'s 3-tuple output and
returns it as the first element of the documents tuple. It is a passive data
carrier — it performs no validation (the caller constructed it from
``parse_dsl``'s already-consistent output, per ``convention``).
"""

from __future__ import annotations

from dataclasses import dataclass

from .body_format import BodyFormat
from .phases_body import PhasesBody
from .pipeline_header import PipelineHeader
from .stages_body import StagesBody


@dataclass(kw_only=True)
class PipelineDocument:
    """Aggregated pipeline-file document — header, format, and body in one value.

    Built by ``compile_flow`` from ``parse_dsl``'s 3-tuple output and returned
    to consumers as the first element of the documents tuple. All three fields
    are required — a ``PipelineDocument`` is always complete.

    Args:
        header: Parsed pipeline-file header (name, description, optional agents).
        format: Detected body format — PHASES or STAGES.
        body: Parsed body. ``PhasesBody`` when format is PHASES,
            ``StagesBody`` when format is STAGES.
    """

    header: PipelineHeader
    format: BodyFormat
    body: PhasesBody | StagesBody
