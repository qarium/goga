"""The ``FlowStage`` dataclass — one stage of an output afm flow-file.

A flow-file has a ``stages`` list; each item is a single ``FlowStage`` carrying
its ``id`` (the step identifier), ``name`` (the display label), ``depends_on``
(predecessor step ids or ``None``) and ``fields`` (extra step fields in
canonical key order). Both ``PhaseStep`` and ``StageStep`` converge into this
type during compilation.

``depends_on`` is tristate: ``None`` produces no depends_on key in output;
an empty list produces ``depends_on: []``. ``fields`` insertion order IS the
output order — the serializer iterates it as-is, so the compiler must build it
in canonical order: ``interactive``, ``auto_approve``, ``auto_run``, ``command``,
``prompt``, ``description``, ``buttons``, ``agents``, ``supervisor``,
``supervisor_prompt``,
``skills``, ``script_before``, ``script``, ``script_after``, ``script_timeout``,
``reflect``, ``memory_use``, then any unknown
keys alphabetically. ``auto_run`` (bool) is present only when the stage's
effective trigger is ``manual`` — the value is always ``False``;
``auto_run: true`` is never assembled. ``buttons`` (map of str→str) is present
only when the workflow supplied a non-empty notes instruction for the stage —
the map passes through verbatim. ``reflect`` (map of file + mode) is present
only when the memory block is emitted and the stage's reflect instruction is
effective — the authored file verbatim, the materialized mode; uniform across
every loop-expanded copy. ``memory_use`` (bool) is present only when the memory
block is emitted under the alignment method — ``True`` on a participating
stage, an explicit ``False`` on every non-participating one. Both occupy the
canonical slots immediately after ``script_timeout``. A stage of a memory-free
workflow carries neither key.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(kw_only=True)
class FlowStage:
    """One stage of an output afm flow-file.

    Args:
        id: Step identifier (output as a dash-prefixed id item).
        name: Display label (output as the name field).
        depends_on: Predecessor step ids, or ``None`` when absent.
        fields: Extra step fields in canonical key order
            (``interactive``, ``auto_approve``, ``auto_run``, ``command``,
            ``prompt``, ``description``, ``buttons``, ``agents``,
            ``supervisor``, ``supervisor_prompt``, ``skills``,
            ``script_before``, ``script``,
            ``script_after``, ``script_timeout``, ``reflect``, ``memory_use``,
            then unknown keys
            alphabetically). ``auto_run``
            (bool) is present only when the stage's effective trigger is
            ``manual`` — the value is always ``False``; ``auto_run: true`` is
            never assembled. ``buttons`` (map of str→str) is present only when
            the workflow supplied a non-empty notes instruction for the stage
            — the map passes through verbatim. ``reflect`` (map of file +
            mode) is present only when the memory block is emitted and the
            stage's reflect instruction is effective — the authored file
            verbatim, the materialized mode; uniform across every
            loop-expanded copy. ``memory_use`` (bool) is present only when the
            memory block is emitted under the alignment method — ``True`` on a
            participating stage, an explicit ``False`` on every
            non-participating one. Both occupy the canonical slots immediately
            after ``script_timeout``; a stage of a memory-free workflow
            carries neither key.
    """

    id: str
    name: str
    depends_on: list[str] | None
    fields: dict[str, Any]
