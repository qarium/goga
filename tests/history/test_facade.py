"""Facade contract test for the ``goga/history`` domain cell.

The cell CODEMANIFEST declares thirteen facade names: the twelve domain types
and routines of the ``naming``/``paths``/``status``/``tree`` modules plus the
git branch reader embedded from the nested ``goga.history.git`` leaf cell (the
``->resolve_current_branch_name: {}`` re-export).
"""

from __future__ import annotations

import goga.history

_HISTORY_FACADE_ALL = [
    "HistoryYear",
    "TopicRecord",
    "TopicStatus",
    "collect_history_tree",
    "collect_topic_statuses",
    "current_year",
    "ensure_topic_dir",
    "normalize_topic_slug",
    "resolve_current_branch_name",
    "resolve_topic_dir",
    "resolve_topic_file",
    "resolve_topic_status",
    "topic_exists",
]


class TestHistoryFacade:
    def test_history_facade_exports_thirteen_names(self) -> None:
        """The facade ``__all__`` is exactly the thirteen contract names, alphabetical."""
        assert goga.history.__all__ == _HISTORY_FACADE_ALL
        for name in _HISTORY_FACADE_ALL:
            assert hasattr(goga.history, name), f"{name} is not defined on goga.history"

    def test_history_facade_embeds_the_git_branch_reader(self) -> None:
        """The embedded routine is the git leaf cell's object, not a copy."""
        assert (
            goga.history.resolve_current_branch_name
            is goga.history.git.resolve_current_branch_name
        )
