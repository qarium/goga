"""Destructive cleanup of the ``.goga/usages/`` directory for force-sync."""

import shutil
from pathlib import Path


def clean_usages_dir(usages_root: Path) -> int:
    """Remove every subdirectory of ``usages_root`` except ``cooks``.

    Used by ``sync`` in force mode to clear previously synchronized usages before
    re-deploying them. The ``cooks`` directory and every file placed directly in
    ``usages_root`` are preserved verbatim; only subdirectories (other than
    ``cooks``) are removed. The routine is idempotent: a missing root is created
    empty and reports zero removals.

    Args:
        usages_root: Path to the ``.goga/usages/`` directory (relative to CWD).

    Returns:
        The number of subdirectories removed.
    """
    if not usages_root.exists():
        usages_root.mkdir(parents=True, exist_ok=True)

        return 0

    removed = 0
    for entry in usages_root.iterdir():
        if entry.name == "cooks":
            continue

        if entry.is_dir():
            shutil.rmtree(entry, ignore_errors=True)
            removed += 1

    return removed
