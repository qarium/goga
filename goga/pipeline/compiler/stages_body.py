"""The ``StagesBody`` dataclass — body of a stages-DSL pipeline-file."""

from __future__ import annotations

from dataclasses import dataclass

from .stage_step import StageStep


@dataclass(kw_only=True)
class StagesBody:
    """Body of a stages-DSL pipeline-file.

    Args:
        steps: Ordered list of stage steps in source-map iteration order — it
            sets the output stage order; dependencies come from each step's
            authored ``depends_on``.
    """

    steps: list[StageStep]
