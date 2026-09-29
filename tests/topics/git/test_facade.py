"""Facade tests of the topics git cell — the assembled exchange surface.

``goga/topics/git/__init__.py`` re-exports exactly the twenty-eight contract
names of the cell: the fifteen pre-existing inventory/switch/publish names
plus the thirteen exchange routines — the seven checkout-free plumbing
calls of ``exchange`` (the version gate, containment, tree resolution,
merge-tree, commit-tree, the scripted replay, the single-ref plant), the
three in-place moves of ``switch`` (merge/rebase/fast-forward), and the
three network additions of ``publish`` (the targeted fetch, the lease
push, the write-through push). This suite pins the facade rule: the
alphabetical ``__all__`` list of twenty-eight names and each exchange
name resolving to the implementing function of its declaring module.
"""

from __future__ import annotations

import goga.topics.git as cell
from goga.topics.git import (
    create_commit_from_tree,
    fast_forward_current_branch,
    fetch_branch,
    is_ancestor,
    merge_into_current,
    merge_tree,
    point_branch_at_commit,
    push_branch_with_lease,
    push_revision_to_branch,
    rebase_current_onto,
    replay_commits,
    require_git_version,
    resolve_commit_tree,
)
from goga.topics.git.exchange import replay_commits as replay_commits_of_exchange
from goga.topics.git.publish import fetch_branch as fetch_branch_of_publish
from goga.topics.git.switch import merge_into_current as merge_into_current_of_switch

_EXCHANGE_IMPLEMENTING = {
    "require_git_version": require_git_version,
    "is_ancestor": is_ancestor,
    "resolve_commit_tree": resolve_commit_tree,
    "merge_tree": merge_tree,
    "create_commit_from_tree": create_commit_from_tree,
    "replay_commits": replay_commits,
    "point_branch_at_commit": point_branch_at_commit,
    "merge_into_current": merge_into_current,
    "rebase_current_onto": rebase_current_onto,
    "fast_forward_current_branch": fast_forward_current_branch,
    "fetch_branch": fetch_branch,
    "push_branch_with_lease": push_branch_with_lease,
    "push_revision_to_branch": push_revision_to_branch,
}
"""The thirteen exchange names mapped to the names imported from the facade."""


def test_topics_git_facade_exports_exchange_surface() -> None:
    """All thirteen exchange routines live on the twenty-eight-name facade.

    Every name imports from the package root, resolves to the implementing
    function of its declaring module, and appears in the alphabetical
    ``__all__`` list — the domain imports the exchange surface from the
    package root, never from the declaring modules.
    """
    assert cell.replay_commits is replay_commits_of_exchange
    assert cell.merge_into_current is merge_into_current_of_switch
    assert cell.fetch_branch is fetch_branch_of_publish

    for name, entity in _EXCHANGE_IMPLEMENTING.items():
        exported = getattr(cell, name)

        assert exported is entity
        assert callable(exported)
        assert name in cell.__all__

    assert len(cell.__all__) == 28
    assert cell.__all__ == sorted(cell.__all__)
