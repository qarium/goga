"""Hooks command cell — the CLI surface of the hooks inspection."""

from .hooks import hooks
from .render import render_hooks_tree

__all__: list[str] = ["hooks", "render_hooks_tree"]
