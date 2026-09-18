"""Hooks platform facade — the extension surface of the goga domains.

The single consumer entry point of the platform for installed tool packages
and for the domains: it re-exports the declared action catalog, the run
registry with its per-tool inspection view, and the emission of an action at
a domain checkpoint — the emission assembles the registry on first use. It
additionally re-exports the delivery primitives and the installed-package
enumeration — for domains that orchestrate per-tool delivery themselves and
need each hook's outcome or the installed identities. The facade declares no
type of its own. Importing the package imports no tool package and
enumerates nothing.
"""

from .catalog import declared_actions
from .dispatch import build_hook_arguments, emit_hook_event, wrap_context
from .registry import HookRegistry, ToolHooks
from .tools import enumerate_tool_packages

__all__: list[str] = [
    "HookRegistry",
    "ToolHooks",
    "build_hook_arguments",
    "declared_actions",
    "emit_hook_event",
    "enumerate_tool_packages",
    "wrap_context",
]
