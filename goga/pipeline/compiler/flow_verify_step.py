"""The ``FlowVerifyStep`` dataclass — one emitted verify step of a flow-file stage gate."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(kw_only=True)
class FlowVerifyStep:
    """One emitted verify step — one check of a stage's completion gate, fields in key-emission order.

    Built by :func:`compile_flow` from one authored check step; consumed by
    :func:`serialize_flow`. The step form mirrors the authored exclusivity:
    exactly one of ``run``/``command`` is not ``None`` — a shell step carries
    ``run``, an AI step carries ``command``. The cell materializes no timeout
    rule (:func:`compile_flow` applies the shell-step default when building)
    and interprets nothing — execution semantics belong to the engine.

    Args:
        name: The check's dashboard label — the authored name verbatim.
        run: The shell command of a shell step (from the authored script),
            or ``None`` on an AI step.
        command: The launch command of an AI step — the authored agent name
            composed into the in-container wrapper path — or ``None`` on a
            shell step.
        timeout: The step timeout — the authored value verbatim, or the
            materialized ``"1h"`` on a shell step without an authored
            timeout; ``None`` on an AI step without one.
        prompt: The AI step's review instruction, carried verbatim, or
            ``None`` on a shell step.
    """

    name: str
    run: str | None = None
    command: str | None = None
    timeout: str | None = None
    prompt: str | None = None
