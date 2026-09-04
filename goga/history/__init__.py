"""History domain cell — the single owner of the ``.goga/history/`` tree.

Topic identity (the slug grammar and the current year), topic addressing
(directory and artifact file paths, existence, creation, and removal), the
topic status listing, tree traversal, and orphan cleanup. The git branch
reader and the branch inventory live in the nested leaf cell
``goga.history.git`` and the status scale in the ``goga.history.statuses``
subcell — both re-exported on this facade, the embeddings declared in
``goga/history/CODEMANIFEST``.
"""

from .git import BranchRef, list_branch_refs, resolve_current_branch_name
from .naming import current_year, normalize_topic_slug
from .paths import (
    ensure_topic_dir,
    remove_topic_dir,
    resolve_history_root,
    resolve_topic_dir,
    resolve_topic_file,
    topic_exists,
)
from .prune import prune_topics
from .status import TopicRecord, collect_topic_statuses, resolve_topic_status
from .statuses import Stage, StatusRegistry, StatusScale, assemble_status_scale
from .tree import HistoryYear, collect_history_tree

__all__: list[str] = [
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
