"""The emission of the hooks platform.

The entity declared in the cell CODEMANIFEST with ``location: emit.py``:
``emit_hook_event`` — the emission of an action of a domain checkpoint to its
subscribed hooks under the action's error class. This is the only point where
the registry is assembled: the first emission of a run performs the single
build, and no emission of the same run rebuilds it. Delivery is
fire-and-forget — nothing is returned and nothing is collected after the
event; the single channel a tool has towards the emitting domain is calling
members of the delivered object. Every diagnostic names the tool, the action,
and the reason.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from ..catalog import declared_actions
from ..registry import HookRegistry
from .delivery import build_hook_arguments, wrap_context

logger = logging.getLogger(__name__)


def emit_hook_event(
    registry: HookRegistry,
    domain: str,
    action: str,
    context_for: Callable[[str], object],
) -> None:
    """Emit an action of a domain checkpoint to its subscribed hooks.

    Args:
        registry: The run registry — assembled on first use, never rebuilt.
        domain: The emitting domain — the semantic owner of the action.
        action: The action name within its domain.
        context_for: Builds the context view of one receiving tool — takes the
            tool identity, returns the object that tool's hooks receive.

    Algorithm:
        1. Assemble the registry via ``build_once`` — the first emission of a
           run performs the single build
        2. Resolve ``domain`` and ``action`` against ``declared_actions`` — an
           unknown address is a clean error of the emitting side
        3. Take the subscriptions of the address in enumeration order; for
           each, build the receiving tool's context view via ``context_for``
           — one view per distinct tool of the address, built at the tool's
           first subscription and reused by its remaining subscriptions
        4. Wrap the view via ``wrap_context``, project the call arguments via
           ``build_hook_arguments`` with the tool's own context from the
           registry, and call the hook
        5. Treat a failure per the action's error class: soft — a warning in
           the log naming the tool, the action, and the reason, the hook is
           skipped, the sequence continues; hard — a clean error naming the
           tool and the reason, the sequence stops at the first failure

    Requirements:
        An address without subscriptions emits nothing. A failure of
        ``context_for`` is a clean error of the emitting side — never treated
        as a hook failure — so it is raised outside the failure intercept
        below, which covers the wrapping, the projection, and the call as one
        interceptable space and catches ``Exception`` only: a
        ``BaseException`` such as ``KeyboardInterrupt`` passes through.

    Raises:
        ValueError: The address is not declared, or a hook of a hard action
            failed — the message names the hook, the tool, and the reason.
    """
    registry.build_once()

    record = next(
        (entry for entry in declared_actions() if entry.domain == domain and entry.name == action),
        None,
    )
    if record is None:
        raise ValueError(f"unknown hook action: {domain}.{action}")

    views: dict[str, object] = {}

    for subscription in registry.subscriptions_for(domain, action):
        if subscription.tool not in views:
            # Outside the intercept below: a crashing view builder is a clean
            # error of the emitting side, never a hook failure.
            views[subscription.tool] = context_for(subscription.tool)

        try:
            view = wrap_context(views[subscription.tool])
            arguments = build_hook_arguments(
                subscription.hook,
                view,
                registry.self_context(subscription.tool),
            )
            subscription.hook(**arguments)
        except Exception as exc:
            if record.error_class == "hard":
                raise ValueError(
                    f"hook {subscription.name} of tool {subscription.tool} failed on {domain}.{action}: {exc}"
                ) from exc

            logger.warning(
                "hook %s of tool %s failed on %s.%s: %s",
                subscription.name,
                subscription.tool,
                domain,
                action,
                exc,
            )
