from __future__ import annotations

import logging
from pathlib import Path

from .hooks import RelocationOutcome

logger = logging.getLogger(__name__)


def move_completed_plan(plan: str, outcome: bool, dry_run: bool) -> RelocationOutcome:
    """Relocate a successfully completed plan to ``<plan_dir>/completed/`` — overwriting a same-name completed plan.

    Args:
        plan: Path of the plan file, absolute or relative to the container cwd.
        outcome: Success of the final pass — only True relocates.
        dry_run: Dry-run flag of the run; a dry run never relocates.

    Returns:
        The relocation outcome — moved with the destination, or not moved.

    Raises:
        OSError: Filesystem errors of the directory creation and the move,
            propagated to the caller.
    """
    if not outcome or dry_run:
        return RelocationOutcome(moved=False, destination=None)

    src = Path(plan)
    dest_dir = src.parent / "completed"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name

    src.replace(dest)
    logger.info("plan relocated", extra={"from": str(src), "to": str(dest)})

    return RelocationOutcome(moved=True, destination=str(dest))
