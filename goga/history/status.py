"""Topic status listing for the history domain.

The entities declared in the cell CODEMANIFEST with ``location: status.py``:
the per-topic record of the status listing and the two read-only resolvers
that walk a topic directory and a whole year against the caller's assembled
status scale. Both routines only probe — nothing is created or changed; the
scale itself belongs to the statuses subcell and is assembled once per
command run, never per topic. Filtering and rendering belong to the consumer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .naming import current_year
from .paths import _history_root
from .statuses import StatusScale, assemble_status_scale


@dataclass(frozen=True, kw_only=True)
class TopicRecord:
    """One topic of a year paired with its maximal present statuses.

    Attributes:
        topic: The topic slug — the directory name of the topic.
        statuses: The qualified names of the maximal present statuses, in
            scale order.
    """

    topic: str
    statuses: list[str]


def resolve_topic_status(topic_dir: Path, scale: StatusScale) -> list[str]:
    """Resolve the maximal present statuses of one topic from its directory content.

    Args:
        topic_dir: The topic directory path.
        scale: The assembled status scale.

    Returns:
        The qualified names of the maximal present statuses, in scale order.
        Read-only — the directory content is read, never changed. A topic
        with no artifact present yields the single built-in name ``empty``.

    Algorithm:
        1. List the artifact paths present in the directory, relative to it
        2. Compute the maximal present statuses via ``scale``
        3. No artifact present yields the single built-in name empty

    Requirements:
        Nested artifact paths are honored — a status artifact may sit in a
        subdirectory of the topic directory.

    Constraints:
        Do not assemble the scale here — the caller owns the single assembly
        per command run.
        Do not consider files outside the scale.
    """
    paths = [
        path.relative_to(topic_dir).as_posix()
        for path in topic_dir.rglob("*")
        if path.is_file()
    ]
    return scale.maximal_present(paths)


def collect_topic_statuses(
    year: str | None = None, scale: StatusScale | None = None
) -> list[TopicRecord]:
    """Collect every topic of one year with its maximal present statuses.

    Args:
        year: Optional year as four digits; ``None`` and the empty string
            mean the current year.
        scale: Optional assembled status scale; ``None`` assembles it once
            here.

    Returns:
        One ``TopicRecord`` per topic, sorted alphabetically by topic — the
        full year, unfiltered. An absent year yields an empty list, not an
        error; stray files in the year directory are not topics.

    Algorithm:
        1. Resolve the year — ``year`` when given, otherwise the current year
        2. Resolve the scale — ``scale`` when given, otherwise assemble it
           once
        3. List the topic directories of that year; an absent year yields no
           records
        4. Resolve the statuses of each topic via ``resolve_topic_status``
        5. Assemble the records sorted alphabetically by topic and return
           them

    Constraints:
        Do not filter — filtering belongs to the consumer.
        Do not render — output shaping belongs to the consumer.
    """
    resolved_scale = scale or assemble_status_scale()
    resolved_year = year or current_year()
    year_dir = _history_root() / resolved_year
    if not year_dir.is_dir():
        return []
    topics = sorted(path.name for path in year_dir.iterdir() if path.is_dir())
    return [
        TopicRecord(topic=topic, statuses=resolve_topic_status(year_dir / topic, resolved_scale))
        for topic in topics
    ]
