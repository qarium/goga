"""Facade contract test for the ``goga/history`` domain cell.

The cell CODEMANIFEST declares twenty-one facade names: the domain types and
routines of the ``naming``/``paths``/``status``/``tree``/``prune`` modules
(topic addressing including the idempotent directory remover, and the orphan
cleanup), the git branch reader and the branch inventory embedded from the
nested ``goga.history.git`` leaf cell, and the four status scale names
embedded from the ``goga.history.statuses`` subcell (the ``->``
re-exports). The former single-status enum ``TopicStatus`` is deleted by the
contract — the multi-status scale replaces it.
"""

from __future__ import annotations

import goga.history

_HISTORY_FACADE_ALL = [
    "BranchRef",
    "HistoryYear",
    "Stage",
    "StatusRegistry",
    "StatusScale",
    "TopicRecord",
    "assemble_status_scale",
    "collect_history_tree",
    "collect_topic_statuses",
    "current_year",
    "ensure_topic_dir",
    "list_branch_refs",
    "normalize_topic_slug",
    "prune_topics",
    "remove_topic_dir",
    "resolve_current_branch_name",
    "resolve_history_root",
    "resolve_topic_dir",
    "resolve_topic_file",
    "resolve_topic_status",
    "topic_exists",
]


class TestHistoryFacade:
    def test_history_facade_exports_twenty_one_names(self) -> None:
        """The facade ``__all__`` is exactly the twenty-one contract names, alphabetical."""
        assert goga.history.__all__ == _HISTORY_FACADE_ALL
        assert len(goga.history.__all__) == 21
        for name in _HISTORY_FACADE_ALL:
            assert hasattr(goga.history, name), f"{name} is not defined on goga.history"

    def test_history_facade_embeds_the_git_branch_reader(self) -> None:
        """The embedded routine is the git leaf cell's object, not a copy."""
        assert goga.history.resolve_current_branch_name is goga.history.git.resolve_current_branch_name

    def test_history_facade_embeds_the_git_branch_inventory(self) -> None:
        """The embedded inventory names are the git leaf cell's objects, not copies."""
        assert goga.history.BranchRef is goga.history.git.BranchRef
        assert goga.history.list_branch_refs is goga.history.git.list_branch_refs

    def test_history_facade_embeds_the_status_scale(self) -> None:
        """The embedded scale names are the statuses subcell's objects, not copies."""
        assert goga.history.StatusScale is goga.history.statuses.StatusScale
        assert goga.history.Stage is goga.history.statuses.Stage
        assert goga.history.StatusRegistry is goga.history.statuses.StatusRegistry
        assert goga.history.assemble_status_scale is goga.history.statuses.assemble_status_scale

    def test_history_facade_dropped_the_single_status_enum(self) -> None:
        """``TopicStatus`` is deleted from the facade — the scale replaces it."""
        assert "TopicStatus" not in goga.history.__all__
        assert not hasattr(goga.history, "TopicStatus")
