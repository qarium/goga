"""The context mediation of the hooks platform.

The entities declared in the cell CODEMANIFEST with ``location: delivery.py``:
the delivery view ``wrap_context`` and the fixed-name injection
``build_hook_arguments``. Mediation is transparent for reads and calls — a
hook works with the emitted object as if it held it — and closed for writes:
the delivered context is read-only, and the only state a hook may write is
its own tool context, delivered separately under the declared name ``self``.
Nothing here calls a hook; the call belongs to the emission.
"""

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

    The proxy resolves every attribute read on ``target`` — plain
    attributes, properties, bound methods — so a hook sees the emitted
    object itself and nothing else. Writes are closed: attribute assignment
    and deletion raise a clean error and ``target`` stays untouched.

    The proxy hides ``target`` completely. The proxy class is created in the
    closure of this call — a fresh class per delivery, so no type to
    introspect — its instances carry no ``__dict__`` (``__slots__ = ()``),
    and a dunder lookup on the proxy follows the language default instead of
    reaching ``target``.

    Args:
        target: The object the emitting checkpoint hands over.

    Returns:
        The delivery view of ``target``.
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

    The offered-name set is the single source of the opt-in: a declared
    ``context`` parameter receives the delivery view of the emitted object, a
    declared ``self`` parameter receives the isolated context of the hook's
    own tool, and any other declared name receives nothing. Only
    keyword-capable parameters participate — a positional-only ``context``
    declares no injection. The declaration order does not matter: values
    land by name. The hook is not called here; the call belongs to the
    emission.

    Args:
        hook: The registered callable.
        context: The delivery view of the emitted object.
        self_context: The isolated context of the hook's own tool.

    Returns:
        The keyword arguments to call ``hook`` with — never a value the hook
        did not declare.
    """
    offered = {"context": context, "self": self_context}
    arguments: dict[str, object] = {}

    for parameter in inspect.signature(hook).parameters.values():
        if parameter.kind in _KEYWORD_CAPABLE and parameter.name in offered:
            arguments[parameter.name] = offered[parameter.name]

    return arguments
