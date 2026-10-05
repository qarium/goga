"""Topics domain cell — the work-tracker view of the history tree."""

from .board import (
    BoardEntry,
    BoardRecord,
    aggregate_topic_board,
    collect_topic_board,
    resolve_divergence,
)
from .creation import (
    check_branch_occupancy,
    check_slug_occupancy,
    create_topic,
    enter_topic_todo,
)
from .deletion import DeleteTarget, delete_topics, resolve_clear_targets, resolve_delete_targets
from .ensuring import ensure_topic
from .exchange import (
    ExchangeBase,
    ExchangeTarget,
    render_commit_template,
    resolve_exchange_base,
    resolve_exchange_target,
)
from .propagating import PropagationPlan, execute_propagation, resolve_propagation
from .publishing import publish_existing_topic, publish_topic, resolve_publication_outcome
from .switching import (
    SwitchCandidate,
    resolve_switch_candidates,
    switch_topic,
)
from .updating import update_topic

__all__: list[str] = [
    "BoardEntry",
    "BoardRecord",
    "DeleteTarget",
    "ExchangeBase",
    "ExchangeTarget",
    "PropagationPlan",
    "SwitchCandidate",
    "aggregate_topic_board",
    "check_branch_occupancy",
    "check_slug_occupancy",
    "collect_topic_board",
    "create_topic",
    "delete_topics",
    "ensure_topic",
    "enter_topic_todo",
    "execute_propagation",
    "publish_existing_topic",
    "publish_topic",
    "render_commit_template",
    "resolve_clear_targets",
    "resolve_delete_targets",
    "resolve_divergence",
    "resolve_exchange_base",
    "resolve_exchange_target",
    "resolve_propagation",
    "resolve_publication_outcome",
    "resolve_switch_candidates",
    "switch_topic",
    "update_topic",
]
