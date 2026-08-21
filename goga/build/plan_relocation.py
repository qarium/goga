from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def move_completed_plan(plan: str, outcome: bool, dry_run: bool) -> None:
    """Relocate a successfully completed plan to `<plan_dir>/completed/`.

    Called by the orchestrator after the final build pass: `outcome` is the
    success of that pass, so a failed run keeps the plan in place for ralphex
    to resume at its first unchecked checkbox, and a dry run — where nothing
    executed — moves nothing either.

    The `completed/` directory is created next to the plan when missing and
    follows the plan's own location (`docs/plans/` is never hardcoded). The
    move is an atomic `Path.replace` within one filesystem; re-running a plan
    that already completed under the same name overwrites it, which keeps the
    relocation idempotent by name. Filesystem errors propagate to the caller.

    Args:
        plan: Path of the plan file, absolute or relative to the container cwd.
        outcome: Success of the final pass — only True relocates.
        dry_run: Dry-run flag of the run; a dry run never relocates.
    """
    if not outcome or dry_run:
        return

    src = Path(plan)
    dest_dir = src.parent / "completed"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / src.name

    src.replace(dest)
    logger.info("plan relocated", extra={"from": str(src), "to": str(dest)})
