"""Hooks platform facade — the extension surface of the goga domains.

The single consumer entry point of the platform for installed tool packages
and for the domains: it re-exports the declared action catalog, the run
registry with its per-tool inspection view, and the emission of an action at
a domain checkpoint — the emission assembles the registry on first use. The
facade declares no type of its own. Importing the package imports no tool
package and enumerates nothing.
"""

from .catalog import declared_actions
from .dispatch import emit_hook_event
from .registry import HookRegistry, ToolHooks

__all__: list[str] = [
    "HookRegistry",
    "ToolHooks",
    "declared_actions",
    "emit_hook_event",
]
