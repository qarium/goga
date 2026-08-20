"""The ``order_stages`` Routine — deterministic topological ordering of flow stages.

The pipeline card reports stages in execution order. Compilation emits them in
DSL declaration order, so the card layer orders them here by ``depends_on``:
a stage is ready once every declared dependency it names has been emitted.
The result is deterministic — among the ready stages the FIRST in declaration
order is emitted (declaration order is the tie-break), and when a dependency
cycle blocks all progress the remaining stages are appended in declaration
order (declaration order is the fallback) rather than raising.

Dangling references — a ``depends_on`` id that is not declared in the input —
count as satisfied. This mirrors the compiler's stance: validation of
dangling ids, cycles, and duplicate ids belongs to the compiler's strict
checks, not to this Routine, which only reads the fields it orders by.

The Routine is pure: the input list and its stage objects are never mutated,
``depends_on`` is never rewritten, and the result carries the SAME objects,
each exactly once. A quadratic worst case (a rescan per emission) is accepted
deliberately — stage counts are small and clarity wins.
"""

from __future__ import annotations

import logging

from .compiler import FlowStage

logger = logging.getLogger(__name__)


def order_stages(stages: list[FlowStage]) -> list[FlowStage]:
    """Order flow stages by ``depends_on`` into deterministic execution order.

    Readiness: a stage is ready when every id in its ``depends_on`` (an absent
    ``None`` counts as no references — always ready) has either been emitted
    already or is not declared in the input at all (dangling → satisfied).
    Among the ready stages the first in declaration order is emitted next.
    When a full pass makes no progress (a dependency cycle), the remaining
    stages are appended in declaration order and the routine returns.

    Requirements:
        - Deterministic: declaration order is the tie-break among ready stages
          and the fallback order on a cycle.
        - Complete: the result contains every input stage exactly once.
        - Pure: neither the input list nor its stage objects are mutated;
          ``depends_on`` is never rewritten.
        - No validation: dangling ids, cycles, and duplicate ids are the
          compiler's concern and pass through unjudged here.

    Args:
        stages: Compiled flow stages; read-only access to ``id`` and
            ``depends_on``.

    Returns:
        A new list holding the SAME stage objects in execution order.
    """
    # Step 1 — the set of declared ids. Duplicated ids are not validated
    # here (the compiler's strict checks own that); membership is all this
    # routine needs — tie-breaking among ready stages is the in-order scan
    # of ``remaining`` below.
    declared_ids = {stage.id for stage in stages}

    result: list[FlowStage] = []
    emitted: set[str] = set()
    remaining = list(stages)

    # Step 2 — emit ready stages, first-declared first, until none remain or a
    # full pass makes no progress.
    while remaining:
        next_stage: FlowStage | None = None
        for candidate in remaining:
            dependencies = candidate.depends_on or []
            if all(dep in emitted or dep not in declared_ids for dep in dependencies):
                next_stage = candidate
                break

        if next_stage is None:
            # Step 3 — a dependency cycle blocks every remaining stage: append
            # them in declaration order and stop (no error, no reordering).
            logger.debug(
                "dependency cycle among %d stage(s); appending in declaration order",
                len(remaining),
            )
            result.extend(remaining)
            break

        result.append(next_stage)
        emitted.add(next_stage.id)
        remaining.remove(next_stage)

    logger.debug("stages ordered: %d emitted", len(result))
    return result
