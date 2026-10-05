"""Deterministic topological stage ordering — declaration order breaks ties and ends cycles."""

from __future__ import annotations

import logging

from .compiler import FlowStage

logger = logging.getLogger(__name__)


def order_stages(stages: list[FlowStage]) -> list[FlowStage]:
    """Order flow stages by ``depends_on`` into deterministic execution order.

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
        A new list holding the SAME stage objects in execution order; a
        dangling ``depends_on`` id (not declared in the input) counts as
        satisfied — always ready.
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
                "dependency cycle; appending in declaration order",
                extra={"stages": len(remaining)},
            )
            result.extend(remaining)
            break

        result.append(next_stage)
        emitted.add(next_stage.id)
        remaining.remove(next_stage)

    logger.debug("stages ordered", extra={"count": len(result)})
    return result
