"""Topic status model for the history domain.

The entities declared in the cell CODEMANIFEST with ``location: status.py``:
the fixed eight-member status value set, the per-topic record of the status
listing, the read-only resolver that walks the artifact progression, and the
year collector. Both filesystem routines only probe — nothing is created or
changed; filtering and rendering belong to the consumer.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from .naming import current_year
from .paths import _history_root


class TopicStatus(Enum):
    """Fixed value set of a history topic status.

    Each member names the process stage reached by the topic's deepest
    present artifact; ``value`` is the display string consumers filter and
    render by.
    """

    empty = "empty"
    defined = "defined"
    discovered = "discovered"
    backlog = "backlog"
    designed = "designed"
    specified = "specified"
    planned = "planned"
    done = "done"


@dataclass(frozen=True, kw_only=True)
class TopicRecord:
    """One topic of a year paired with its resolved status.

    Attributes:
        topic: The topic slug — the directory name of the topic.
        status: The status resolved for the topic.
    """

    topic: str
    status: TopicStatus


# Defined after TopicStatus — each row pairs a progression artifact with the
# status its presence reports; the deepening order is the contract.
_ARTIFACT_PROGRESSION: list[tuple[str, TopicStatus]] = [
    ("prd.md", TopicStatus.defined),
    ("adr.md", TopicStatus.discovered),
    ("task.md", TopicStatus.backlog),
    ("arch.md", TopicStatus.designed),
    ("design.md", TopicStatus.specified),
    ("plan.md", TopicStatus.planned),
    ("completed/plan.md", TopicStatus.done),
]


def resolve_topic_status(topic_dir: Path) -> TopicStatus:
    """Resolve the status of one topic from its directory content.

    The artifacts of the progression are probed in deepening order and the
    deepest present one wins — ``completed/plan.md`` is last in the list, so
    its presence outranks every flat artifact. Files outside the progression
    are ignored; an empty or missing directory resolves to ``empty``.

    Args:
        topic_dir: The topic directory path.

    Returns:
        The status of the topic. Read-only — the directory content is probed,
        never changed.
    """
    resolved = TopicStatus.empty
    for artifact, artifact_status in _ARTIFACT_PROGRESSION:
        if (topic_dir / artifact).is_file():
            resolved = artifact_status
    return resolved


def collect_topic_statuses(year: str | None = None) -> list[TopicRecord]:
    """Collect every topic of one year with its resolved status.

    Args:
        year: Optional year as four digits; ``None`` (or the empty string an
            empty CLI value produces) means the current year.

    Returns:
        One ``TopicRecord`` per topic, sorted alphabetically by topic — the
        full year, unfiltered. An absent year yields an empty list, not an
        error; stray files in the year directory are not topics.
    """
    resolved_year = year or current_year()
    year_dir = _history_root() / resolved_year
    if not year_dir.is_dir():
        return []
    topics = sorted(path.name for path in year_dir.iterdir() if path.is_dir())
    return [TopicRecord(topic=topic, status=resolve_topic_status(year_dir / topic)) for topic in topics]
