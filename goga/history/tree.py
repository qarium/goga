"""History tree inventory for the history domain.

The entities declared in the cell CODEMANIFEST with ``location: tree.py``:
the per-year record of the tree listing and the tree collector — the full
tree or one selected year. The collector is read-only and carries names
only — statuses belong to the status module, filtering and rendering to the
consumer.
"""

from __future__ import annotations

from dataclasses import dataclass

from .paths import _history_root

_YEAR_NAME_LENGTH = 4


@dataclass(frozen=True, kw_only=True)
class HistoryYear:
    """One year of the history tree paired with its topic names.

    Attributes:
        year: The year as four digits — the directory name of the year.
        topics: The topic slugs found under the year, sorted alphabetically.
    """

    year: str
    topics: list[str]


def collect_history_tree(year: str | None = None) -> list[HistoryYear]:
    """Collect the history tree — every year with its topics, or the one named year alone.

    A year directory is a directory named with exactly four ASCII digits —
    anything else in the history root is ignored (the ASCII filter matters:
    some non-ASCII digit strings still satisfy ``str.isdigit()``). Only
    directories count as topics; stray files are ignored on both levels.

    Args:
        year: Optional year as four digits; ``None`` and the empty string
            mean no year selection — the full tree; a year missing from the
            tree yields an empty list — not an error.

    Returns:
        One ``HistoryYear`` per selected year — years sorted ascending,
        topics within a year sorted alphabetically. An absent history root
        yields an empty list, not an error. Read-only — nothing is created,
        and no status is computed: the tree carries topic names only.
    """
    root = _history_root()
    if not root.is_dir():
        return []
    selected = year or None
    years = sorted(
        path.name
        for path in root.iterdir()
        if path.is_dir()
        and len(path.name) == _YEAR_NAME_LENGTH
        and path.name.isascii()
        and path.name.isdigit()
        and (selected is None or path.name == selected)
    )
    return [
        HistoryYear(
            year=year_name,
            topics=sorted(entry.name for entry in (root / year_name).iterdir() if entry.is_dir()),
        )
        for year_name in years
    ]
