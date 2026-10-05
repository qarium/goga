"""The ``BodyFormat`` enum — the two legal shapes a pipeline-file body can take."""

from __future__ import annotations

from enum import Enum


class BodyFormat(str, Enum):
    """The two supported pipeline-body shapes; ``str``-based so each member serializes as its plain value."""

    PHASES = "phases"
    """Body is an ordered list of steps — ``compile_flow`` derives each step's ``depends_on`` from position."""

    STAGES = "stages"
    """Body is a mapping of named stages with explicitly authored ``depends_on`` values."""
