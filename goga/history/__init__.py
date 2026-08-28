"""History domain cell — the single owner of the ``.goga/history/`` tree.

Topic identity (the slug grammar and the current year), topic addressing
(directory and artifact file paths, existence, creation), the topic status
model, and tree traversal. The git branch reader lives in the nested leaf cell
``goga.history.git`` and is re-exported on this facade — the embedding
declared in ``goga/history/CODEMANIFEST``.
"""

from .git import resolve_current_branch_name
from .naming import current_year, normalize_topic_slug
from .paths import ensure_topic_dir, resolve_topic_dir, resolve_topic_file, topic_exists
from .status import TopicRecord, TopicStatus, collect_topic_statuses, resolve_topic_status
from .tree import HistoryYear, collect_history_tree

__all__: list[str] = [
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
