"""The ``StagesBody`` dataclass — body of a stages-DSL pipeline-file.

A stages-DSL body is an ordered list of ``StageStep`` items, in the iteration
order of the source map (Python 3.7+ preserves dict insertion order). The
order carries no dependency meaning (``depends_on`` is user-supplied per step)
but determines the order of stages in the output flow-file.
"""

from __future__ import annotations

from dataclasses import dataclass

from .stage_step import StageStep


@dataclass(kw_only=True)
class StagesBody:
    """Body of a stages-DSL pipeline-file.

    Args:
        steps: Ordered list of stage steps, in source-map iteration order.
    """

    steps: list[StageStep]
