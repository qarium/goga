"""The ``PipelineHeader`` dataclass — name and description of an input pipeline-file.

A goga DSL pipeline-file has a header (name + description) followed by a
``---`` separator and a body. ``PipelineHeader`` carries the two header fields
parsed from the segment before the separator. ``compile_flow`` carries them
1:1 into the ``FlowDocument`` (its name and description fields).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class PipelineHeader:
    """Header of an input pipeline-file — name and description.

    Args:
        name: Pipeline name (e.g. "Goga feature").
        description: Short pipeline description (e.g. "Feature implementation").
    """

    name: str
    description: str
