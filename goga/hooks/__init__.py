"""Hooks platform facade — the extension surface of the goga domains."""

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
