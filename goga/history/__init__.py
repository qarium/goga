"""History domain cell — the owner of the ``.goga/history/`` tree.

The package facade is assembled incrementally per module (the naming and
paths modules here; the git leaf cell ``goga.history.git`` is physically
nested inside this directory and re-exported later). The full 13-name
contract surface of the naming, paths, status, and tree modules plus the
embedded git routine is finalized by the dedicated facade task.
"""

from .naming import current_year, normalize_topic_slug
from .paths import ensure_topic_dir, resolve_topic_dir, resolve_topic_file, topic_exists

__all__: list[str] = [
    "current_year",
    "ensure_topic_dir",
    "normalize_topic_slug",
    "resolve_topic_dir",
    "resolve_topic_file",
    "topic_exists",
]
