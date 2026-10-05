"""The action catalog of the hooks platform — the single source of known subscription addresses."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, kw_only=True)
class Action:
    """One catalog record — a named subscription address with its error class.

    Attributes:
        domain: The semantic owner domain of the action — the domain whose
            checkpoint emits the event.
        name: The action name within its domain.
        error_class: The failure treatment of the action's hooks — soft or
            hard.

    Requirements:
        ``domain`` and ``name`` are non-empty; the pair is unique in the
        catalog; ``error_class`` is exactly soft or hard.
    """

    domain: str
    name: str
    error_class: str


_DECLARED_ACTIONS: list[Action] = [  # supported data, not discovery
    Action(domain="onboarding", name="amend_config", error_class="soft"),
    Action(domain="onboarding", name="declare_session", error_class="soft"),
    Action(domain="pipeline", name="amend_workflow", error_class="hard"),
    Action(domain="pipeline", name="run_created", error_class="soft"),
    Action(domain="pipeline", name="run_completed", error_class="soft"),
    Action(domain="statuses", name="register_statuses", error_class="soft"),
    Action(domain="topics", name="amend_creation", error_class="soft"),
    Action(domain="topics", name="amend_todo_entry", error_class="soft"),
    Action(domain="topics", name="topic_created", error_class="soft"),
    Action(domain="topics", name="topic_deleted", error_class="soft"),
    Action(domain="topics", name="topic_propagated", error_class="soft"),
    Action(domain="topics", name="topic_published", error_class="soft"),
    Action(domain="topics", name="topic_switched", error_class="soft"),
    Action(domain="topics", name="topic_todo_entered", error_class="soft"),
    Action(domain="topics", name="topic_updated", error_class="soft"),
    Action(domain="build", name="validate_build", error_class="hard"),
    Action(domain="build", name="build_started", error_class="soft"),
    Action(domain="build", name="pass_started", error_class="soft"),
    Action(domain="build", name="pass_completed", error_class="soft"),
    Action(domain="build", name="build_completed", error_class="soft"),
    Action(domain="config", name="amend_config", error_class="hard"),
    Action(domain="schema", name="amend_cell", error_class="hard"),
    Action(domain="schema", name="validate_schema", error_class="hard"),
    Action(domain="contract", name="amend_contract", error_class="hard"),
    Action(domain="usages", name="sync_started", error_class="soft"),
    Action(domain="usages", name="sync_completed", error_class="soft"),
    Action(domain="usages", name="status_started", error_class="soft"),
    Action(domain="usages", name="status_completed", error_class="soft"),
]


def declared_actions() -> list[Action]:
    """Return the declared action catalog — the single source of known addresses.

    Returns:
        Every declared record, complete and unfiltered, ordered by domain
        then by name; a new list on every call.
    """
    return sorted(_DECLARED_ACTIONS, key=lambda action: (action.domain, action.name))
