"""Destructive cleanup of the ``.goga/usages/`` directory for force-sync."""

import shutil
from pathlib import Path


def clean_usages_dir(usages_root: Path, group: str | None = None, dep: str | None = None) -> int:
    """Remove synced subtrees of ``usages_root``, scoped by the given filters.

    Used by ``sync`` in force mode to clear previously synchronized usages
    before re-deploying them. Without filters every subdirectory of
    ``usages_root`` except ``cooks`` is removed; ``group``/``dep`` narrow the
    removal to the matching subtrees only. The ``cooks`` directory and every
    file placed directly in ``usages_root`` are preserved verbatim in every
    mode. The routine is idempotent: a missing root is created empty and
    reports zero removals, and a missing filtered target is a no-op.

    Args:
        usages_root: Path to the ``.goga/usages/`` directory (relative to CWD).
        group: When set, limit removal to this group's subtree — the whole
            group directory, or the single ``dep`` inside it.
        dep: When set, limit removal to this dep name; without ``group`` the
            dep subtree is removed under every existing group directory.

    Returns:
        The number of directories removed.
    """
    if not usages_root.exists():
        usages_root.mkdir(parents=True, exist_ok=True)

        return 0

    if group is None and dep is None:
        return _clean_all(usages_root)

    if group is None:
        return _clean_dep_everywhere(usages_root, dep)

    return _clean_group_target(usages_root, group, dep)


def _clean_all(usages_root: Path) -> int:
    """Remove every subdirectory of ``usages_root`` except ``cooks``."""
    removed = 0
    for entry in usages_root.iterdir():
        if entry.name == "cooks":
            continue

        if entry.is_dir():
            shutil.rmtree(entry, ignore_errors=True)
            removed += 1

    return removed


def _clean_group_target(usages_root: Path, group: str, dep: str | None) -> int:
    """Remove one group subtree — the whole group, or the single dep inside it."""
    if group == "cooks":
        return 0

    target = usages_root / group if dep is None else usages_root / group / dep

    return _remove_dir(target)


def _clean_dep_everywhere(usages_root: Path, dep: str) -> int:
    """Remove the dep subtree under every group directory except ``cooks``."""
    removed = 0
    for entry in usages_root.iterdir():
        if entry.name == "cooks" or not entry.is_dir():
            continue

        removed += _remove_dir(entry / dep)

    return removed


def _remove_dir(target: Path) -> int:
    """Remove ``target`` when it is an existing directory; return 1 or 0."""
    if target.is_dir():
        shutil.rmtree(target, ignore_errors=True)

        return 1

    return 0
