"""The ``PhasesBody`` dataclass — body of a phases-DSL pipeline-file.

A phases-DSL body is an ordered list of ``PhaseStep`` items, in the source
order. The order carries semantic meaning: the compiler auto-generates
``depends_on`` from list position (the first step gets none, each subsequent
step depends on the previous one).
"""

from __future__ import annotations

from dataclasses import dataclass

from .phase_step import PhaseStep


@dataclass(kw_only=True)
class PhasesBody:
    """Body of a phases-DSL pipeline-file.

    Args:
        steps: Ordered list of phase steps, in source order.
    """

    steps: list[PhaseStep]
