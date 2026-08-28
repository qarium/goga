"""History domain cell — the owner of the ``.goga/history/`` tree.

The package facade is assembled incrementally per module (the naming, paths,
status, and tree modules here; the git leaf cell ``goga.history.git`` is
physically nested inside this directory and re-exported later). The full
13-name contract surface of these modules plus the embedded git routine is
finalized by the dedicated facade task.
"""

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
    "resolve_topic_dir",
    "resolve_topic_file",
    "resolve_topic_status",
    "topic_exists",
]
