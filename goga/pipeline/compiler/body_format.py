"""The ``BodyFormat`` enum — the two legal shapes a pipeline-file body can take.

A goga DSL pipeline-file has a header (name + description) followed by a
``---`` separator and a body. The body is either a YAML list (a sequence of
phases executed in order) or a YAML mapping of named stages with explicit
dependencies. ``BodyFormat`` records which of those two shapes a parsed body
has so the rest of the compiler can apply format-specific rules.
"""

from __future__ import annotations

from enum import Enum


class BodyFormat(str, Enum):
    """The two supported pipeline-body shapes.

    Subclasses ``str`` so each member serializes as its plain string value
    when emitted into an afm flow-file.
    """

    PHASES = "phases"
    """Body is an ordered list of steps — ``compile_flow`` derives each step's ``depends_on`` from position."""

    STAGES = "stages"
    """Body is a mapping of named stages with explicitly authored ``depends_on`` values."""
