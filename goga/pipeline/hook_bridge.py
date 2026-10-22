"""The afm lifecycle-hook bridge — one curated afm event, one soft pipeline emission."""

from __future__ import annotations

# ruff: noqa: PLC0415 — function-local goga imports are the D1 fast-path contract
import json
import os
import sys
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # the bridged context types exist for the type checker only
    from .hooks.contexts import RunEvent, RunIdentity, StageEvent, StageTransition

_EVENT_ACTION_MAP: dict[str, str] = {
    "flow_resumed": "run_resumed",
    "flow_interrupted": "run_interrupted",
    "stage_planning_started": "stage_planning_started",
    "stage_plan_ready": "stage_plan_ready",
    "stage_approved": "stage_approved",
    "stage_revision_started": "stage_revision_started",
    "stage_execution_started": "stage_execution_started",
    "stage_question_asked": "stage_question_asked",
    "stage_question_answered": "stage_question_answered",
    "stage_retry_scheduled": "stage_retry_scheduled",
    "stage_retry_started": "stage_retry_started",
    "stage_paused": "stage_paused",
    "stage_resumed": "stage_resumed",
    "stage_finished": "stage_finished",
    "stage_failed": "stage_failed",
}

_RUN_LEVEL_ACTIONS: frozenset[str] = frozenset({"run_resumed", "run_interrupted"})


def _required_fact(mapping: dict[str, Any], key: str, owner: str) -> Any:
    """Read one required fact of the payload or one of its blocks.

    Args:
        mapping: The payload or payload block carrying the fact.
        key: The fact's key.
        owner: The owner named in the error — the payload or its block.

    Returns:
        The fact's value, carried verbatim.

    Raises:
        ValueError: The fact is absent — the message names it.
    """
    if key not in mapping:
        raise ValueError(f"{owner} carries no {key} fact")

    return mapping[key]


def _flow_block(payload: dict[str, Any]) -> dict[str, Any]:
    """Read the flow block of a lifecycle event payload.

    Args:
        payload: The parsed afm lifecycle event payload.

    Returns:
        The flow block — the run facts every bridged event carries.

    Raises:
        ValueError: The payload carries no flow block — the key is
            absent or not a JSON object.
    """
    flow = payload.get("flow")

    if not isinstance(flow, dict):
        raise ValueError("lifecycle event payload carries no flow block")

    return flow


def _run_identity(flow: dict[str, Any]) -> RunIdentity:
    """Compose the run identity from the flow block.

    Args:
        flow: The flow block of the event payload.

    Returns:
        The run identity of the flow the event belongs to.

    Raises:
        ValueError: The flow block lacks a required fact — the message
            names it.
    """
    from .hooks.contexts import RunIdentity

    return RunIdentity(
        run_id=_required_fact(flow, "run_id", "flow block"),
        run_dir=_required_fact(flow, "run_dir", "flow block"),
        root_dir=_required_fact(flow, "root_dir", "flow block"),
        resumed=_required_fact(flow, "resumed", "flow block"),
    )


def _event_facts(payload: dict[str, Any]) -> dict[str, Any]:
    """Read the event facts both bridged context levels share.

    Args:
        payload: The parsed afm lifecycle event payload.

    Returns:
        The event id, the event moment, and the reason — the reason
        lands ``""`` when afm provides none or a JSON ``null``.

    Raises:
        ValueError: A required event fact is absent — the message
            names it.
    """
    facts: dict[str, Any] = {
        "event_id": _required_fact(payload, "event_id", "lifecycle event payload"),
        "occurred_at": _required_fact(payload, "occurred_at", "lifecycle event payload"),
        "reason": payload.get("reason") or "",
    }

    return facts


def _stage_block(payload: dict[str, Any]) -> StageTransition:
    """Compose the stage transition from the stage block.

    Args:
        payload: The parsed afm lifecycle event payload.

    Returns:
        The stage transition the event describes — the raw ``from`` /
        ``to`` payload keywords under their idiomatic attribute names,
        and the phase, which lands ``""`` when afm provides none (the
        live binary omits it on the start/retry transitions and carries
        it on the terminal ones).

    Raises:
        ValueError: The payload carries no stage block — the key is
            absent or not a JSON object — or the block lacks a
            required fact; the message names it.
    """
    from .hooks.contexts import StageTransition

    stage = payload.get("stage")

    if not isinstance(stage, dict):
        raise ValueError("stage-level lifecycle event payload carries no stage block")

    return StageTransition(
        id=_required_fact(stage, "id", "stage block"),
        name=_required_fact(stage, "name", "stage block"),
        from_status=_required_fact(stage, "from", "stage block"),
        to_status=_required_fact(stage, "to", "stage block"),
        phase=stage.get("phase") or "",
    )


def map_event_action(event: str) -> str | None:
    """Resolve one afm lifecycle event name to its bridged pipeline action.

    Args:
        event: The raw ``AFM_HOOK_EVENT`` value — the afm event name.

    Returns:
        The pipeline action the event bridges onto — the thirteen stage
        names verbatim, ``flow_resumed`` normalized to ``run_resumed``,
        ``flow_interrupted`` normalized to ``run_interrupted`` — or
        ``None`` outside the curated vocabulary: afm's flow boundaries,
        the script events, the internal names, and unknown names stay
        unbridged.
    """
    return _EVENT_ACTION_MAP.get(event)


def build_run_event(payload: dict[str, Any]) -> RunEvent:
    """Compose the run-level context of one curated lifecycle event.

    Args:
        payload: The parsed afm lifecycle event payload.

    Returns:
        The run-level event context — the flow facts and the event
        facts carried verbatim under their idiomatic names; the raw
        payload never attaches to the context.

    Raises:
        ValueError: The payload carries no flow block or lacks a
            required event fact — the message names it.
    """
    from .hooks.contexts import RunEvent

    flow = _flow_block(payload)
    identity = _run_identity(flow)

    facts = _event_facts(payload)

    return RunEvent(pipeline=_required_fact(flow, "name", "flow block"), run=identity, **facts)


def build_stage_event(payload: dict[str, Any]) -> StageEvent:
    """Compose the stage-level context of one curated lifecycle event.

    Args:
        payload: The parsed afm lifecycle event payload.

    Returns:
        The stage-level event context — the flow facts, the stage
        transition, and the event facts carried verbatim; the raw
        ``from`` / ``to`` payload keywords land under their idiomatic
        ``from_status`` / ``to_status`` names, and the phase lands
        ``""`` when afm provides none (the start/retry transitions of
        the live binary carry no phase fact).

    Raises:
        ValueError: The payload carries no flow block or no stage
            block, or lacks a required event fact — the message names
            it.
    """
    from .hooks.contexts import StageEvent

    flow = _flow_block(payload)
    identity = _run_identity(flow)

    facts = _event_facts(payload)

    return StageEvent(
        pipeline=_required_fact(flow, "name", "flow block"),
        run=identity,
        stage=_stage_block(payload),
        **facts,
    )


def run_hook() -> int:
    """Bridge one afm lifecycle event onto the pipeline hooks platform.

    The process entry behind ``python3 -m goga.pipeline hook``. The
    curated filter runs first — a non-curated event returns zero before
    any platform import and without reading stdin. A curated event
    parses the JSON payload from stdin, composes the bridged context,
    and emits it as one shared read-only delivery; subscriber failures
    warn inside the platform and never change the exit code.

    Returns:
        The process exit code — zero on success, on ignored events, and
        on subscriber soft failures; one on a bridge-internal failure,
        with the reason rendered to stderr for the afm per-hook log.
    """
    action = map_event_action(os.environ.get("AFM_HOOK_EVENT", ""))

    if action is None:
        return 0

    try:
        payload = json.loads(sys.stdin.read())

        if not isinstance(payload, dict):
            raise ValueError("lifecycle event payload is not a JSON object")

        context = build_stage_event(payload) if action not in _RUN_LEVEL_ACTIONS else build_run_event(payload)

        from .hooks import PipelineHooks  # function-local: after the curated filter (the D1 fast-path discipline)

        hooks = PipelineHooks()

        if action in _RUN_LEVEL_ACTIONS:
            hooks.emit_run_event(action, context)
        else:
            hooks.emit_stage_event(action, context)

        return 0
    except (ValueError, ImportError, OSError) as reason:
        print(f"Error: {reason}", file=sys.stderr)

        return 1
