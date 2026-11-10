"""Goga — CLI and library for the CODEMANIFEST specification lifecycle."""

from importlib import import_module
from typing import Any

__all__ = ["AST", "app"]

# Both root re-exports carry the platform (the commands tree behind ``app``,
# the rules engine behind ``AST``); they resolve on first attribute access
# (PEP 562) so importing the package itself stays platform-free.
_LAZY_REEXPORTS: dict[str, str] = {
    "AST": ".ast",
    "app": ".cli",
}


def __getattr__(name: str) -> Any:
    """Resolve a lazy root re-export by importing its submodule (PEP 562).

    Args:
        name: The requested attribute name.

    Returns:
        The submodule's exported object, imported and bound on first
        access; the binding serves every later lookup.

    Raises:
        AttributeError: The name is not a lazy root re-export.
    """
    if name not in _LAZY_REEXPORTS:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    value = getattr(import_module(_LAZY_REEXPORTS[name], __name__), name)
    globals()[name] = value

    return value
