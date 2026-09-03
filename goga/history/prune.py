"""Orphan-topic cleanup for the history domain.

The routine declared in the cell CODEMANIFEST with ``location: prune.py``:
the orphan computation and cleanup of one year of the history tree. This
module owns the orphan decision alone — the tree inventory comes from the
tree collector, the branch inventory from the nested git cell, and the
deletion itself from the directory remover. Filesystem-only: the single git
invocation of the flow is the read-only ref listing, and no branch, ref, or
index is mutated in any mode.
"""

from __future__ import annotations

from .git import list_branch_refs
from .naming import current_year, normalize_topic_slug
from .paths import remove_topic_dir
from .tree import collect_history_tree


def prune_topics(year: str | None = None, dry_run: bool = False) -> list[str]:
    """Delete the orphan topics of one year — the topics no branch of the repository inventory hosts.

    Args:
        year: Optional year as four digits — ``None`` and the empty string
            mean the current year.
        dry_run: ``True`` lists the orphan topics without deleting anything.

    Returns:
        The slugs of the orphan topics sorted alphabetically — the deleted
        ones, or the deletion candidates under ``dry_run``. The slugs come
        out normalized: a manually unnormalized directory name is listed
        yet not reachable for deletion.

    Algorithm:
        1. Resolve the year — ``year`` when given, otherwise the current year
        2. Take the topics of the resolved year from the tree collected via
           ``collect_history_tree`` — an absent year yields no topics
        3. Enumerate the repository branch inventory via ``list_branch_refs``
        4. Build the hosted slug set: every local branch name normalized via
           ``normalize_topic_slug``, and the short name of every
           remote-tracking ref — the part after the first ``/`` — normalized
           the same way
        5. The orphans are the year's topics whose slug is not in the hosted
           set
        6. ``dry_run`` False -> delete every orphan directory via
           ``remove_topic_dir``; True -> delete nothing
        7. Return the orphan slugs sorted alphabetically

    Requirements:
        A topic is protected when at least one branch of the inventory
        normalizes to its slug — the protection is year-independent, a
        branch protects same-named topics of every year.

        The branch inventory is queried even when the resolved year holds
        no topics; a git failure of the listing propagates to the caller.

        Deletion is unconditional — no status protects a topic.

        Only the resolved year is affected — no other year is touched.

        Filesystem-only — no branch, ref, or index of git is mutated in any
        mode.

        ``dry_run`` True mutates nothing at all.

        An empty result is an empty list — not an error.

    Constraints:
        Do not assemble the status scale — statuses take no part in the
        orphan decision.

        Do not spare topics by status or age.

        Do not print — output shaping belongs to the consumer.

    Raises:
        ValueError: a topic directory name normalizes to an empty slug —
            propagated from ``remove_topic_dir`` before the list is returned.
        subprocess.CalledProcessError: a git infrastructure failure of the
            ref listing (propagated — the caller wraps it).
        FileNotFoundError: a missing git binary of the ref listing
            (propagated — the caller wraps it).
        OSError: unexpected filesystem failures of the deletion (propagated
            — the caller wraps it).
    """
    resolved_year = year or current_year()
    tree = collect_history_tree(resolved_year)
    year_topics: list[str] = tree[0].topics if tree else []
    hosted = {
        normalize_topic_slug(ref.name.partition("/")[2] if ref.remote else ref.name) for ref in list_branch_refs()
    }
    orphans = sorted({normalize_topic_slug(topic) for topic in year_topics} - hosted)
    if not dry_run:
        for slug in orphans:
            remove_topic_dir(slug, resolved_year)
    return orphans
