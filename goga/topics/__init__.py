"""Topics domain cell — the work-tracker view of the history tree.

The cross-branch topic inventory of one year with per-topic statuses, the
switch-identifier resolution and switching orchestration, the fresh-work
creation procedure off an explicit base with its editor-sourced todo, the
todo entry of an existing topic, the fast creation-and-publication cycle
that builds a one-commit branch off an explicit base through quarantined
git plumbing and pushes it to origin while the caller stays on their
branch, the combined ensure orchestration that switches onto hosted work
and creates it when nothing hosts the identifier, and the
identified-topic deletion — the read-only target resolution and the
confirmed removal of the local branch, the origin twin, and the topic
directory. Topic identity, addressing, and statuses belong to the
history facade; git access belongs to the nested leaf cell
``goga.topics.git``; the interactive text entry — the external-editor
session every todo flows through — belongs to the nested leaf cell
``goga.topics.editor``. Mutations are local-only and happen strictly
after every decision is made — the publication push of the fast cycle
and the deletion push of the removal are the two network exceptions.
"""

from .board import BoardRecord, collect_topic_board
from .creation import (
    check_branch_occupancy,
    check_slug_occupancy,
    create_topic,
    enter_topic_todo,
)
from .deletion import DeleteTarget, delete_topics, resolve_delete_targets
from .ensuring import ensure_topic
from .publishing import publish_topic
from .switching import (
    SwitchCandidate,
    resolve_switch_candidates,
    switch_topic,
)

__all__: list[str] = [
    "BoardRecord",
    "DeleteTarget",
    "SwitchCandidate",
    "check_branch_occupancy",
    "check_slug_occupancy",
    "collect_topic_board",
    "create_topic",
    "delete_topics",
    "ensure_topic",
    "enter_topic_todo",
    "publish_topic",
    "resolve_delete_targets",
    "resolve_switch_candidates",
    "switch_topic",
]
