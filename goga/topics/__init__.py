"""Topics domain cell — the work-tracker view of the history tree.

The cross-branch topic inventory of one year with per-topic statuses, the
switch-identifier resolution and switching orchestration, the fresh-work
creation procedure, and the combined ensure orchestration that switches
onto hosted work and creates it when nothing hosts the identifier. Topic
identity, addressing, and statuses belong to the history facade; git
access belongs to the nested leaf cell ``goga.topics.git``. Mutations are
local-only and happen strictly after every decision is made.
"""

from .board import BoardRecord, collect_topic_board
from .creation import check_branch_occupancy, create_topic
from .ensuring import ensure_topic
from .switching import (
    SwitchCandidate,
    resolve_switch_candidates,
    switch_topic,
)

__all__: list[str] = [
    "BoardRecord",
    "SwitchCandidate",
    "check_branch_occupancy",
    "collect_topic_board",
    "create_topic",
    "ensure_topic",
    "resolve_switch_candidates",
    "switch_topic",
]
