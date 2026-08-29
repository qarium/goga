"""Topics domain cell — the work-tracker view of the history tree.

The cross-branch topic inventory of one year with per-topic statuses, the
switch-identifier resolution and switching orchestration, and the
fresh-work creation procedure. Topic identity, addressing, and statuses
belong to the history facade; git access belongs to the nested leaf cell
``goga.topics.git``. Mutations are local-only and happen strictly after
every decision is made.
"""

from .board import BoardRecord, collect_topic_board
from .switching import SwitchCandidate, resolve_switch_candidates, switch_topic

__all__: list[str] = [
    "BoardRecord",
    "SwitchCandidate",
    "collect_topic_board",
    "resolve_switch_candidates",
    "switch_topic",
]
