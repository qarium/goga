"""The ``PhasesBody`` dataclass — body of a phases-DSL pipeline-file."""

from __future__ import annotations

from dataclasses import dataclass

from .phase_step import PhaseStep


@dataclass(kw_only=True)
class PhasesBody:
    """Body of a phases-DSL pipeline-file.

    Args:
        steps: Ordered list of phase steps in source order — the compiler
            derives each step's ``depends_on`` from list position.
    """

    steps: list[PhaseStep]
