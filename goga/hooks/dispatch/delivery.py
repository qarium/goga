"""The context mediation of the hooks platform — reads pass through, writes stay closed."""

from __future__ import annotations

import inspect
from collections.abc import Callable

from ..registry import ToolContext

_KEYWORD_CAPABLE = frozenset(
    {
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    }
)
"""The parameter kinds a call may fill by name — the injection surface."""


def wrap_context(target: object) -> object:
    """Wrap an emitted domain object for delivery to a hook.

    Args:
        target: The object the emitting checkpoint hands over.

    Returns:
        The delivery view of ``target`` — reads resolve on ``target``, writes
        raise a clean error, and ``target`` stays hidden with no type to
        introspect.
    """

    class _DeliveryProxy:
        """The delivery view of one emitted object — reads pass, writes do not."""

        __slots__ = ()  # no instance dict — nowhere to keep or find the target

        def __getattr__(self, name: str) -> object:
            if name.startswith("__") and name.endswith("__"):
                raise AttributeError(name)  # a dunder: the language default, never target

            return getattr(target, name)

        def __setattr__(self, name: str, value: object) -> None:
            raise AttributeError("the delivered context is read-only: attribute assignment is blocked")

        def __delattr__(self, name: str) -> None:
            raise AttributeError("the delivered context is read-only: attribute deletion is blocked")

    return _DeliveryProxy()


def build_hook_arguments(
    hook: Callable[..., object],
    context: object,
    self_context: ToolContext,
) -> dict[str, object]:
    """Project a hook signature against the offered injection names.

    Args:
        hook: The registered callable.
        context: The delivery view of the emitted object.
        self_context: The isolated context of the hook's own tool.

    Returns:
        The keyword arguments to call ``hook`` with — only declared,
        keyword-capable parameter names; values land by name.
    """
    offered = {"context": context, "self": self_context}
    arguments: dict[str, object] = {}

    for parameter in inspect.signature(hook).parameters.values():
        if parameter.kind in _KEYWORD_CAPABLE and parameter.name in offered:
            arguments[parameter.name] = offered[parameter.name]

    return arguments
