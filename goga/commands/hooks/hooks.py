"""The ``goga hooks`` command — the inspection of the registered hooks.

The entity declared in the cell CODEMANIFEST with ``location: hooks.py``: the
``hooks`` click command. It is a thin inspection wrapper — it creates the run
registry, assembles it once, applies the ``--tool`` slice, and hands the view
to the renderer. No registry computation, no delivery, and no action emission
live here: the command reads the registry and states the fact of registration,
never the application of a hook in some command. A broken package import
surfaces as a clean CLI error — stderr, exit 1, no traceback.
"""

from __future__ import annotations

import click

from ...hooks import HookRegistry, ToolHooks
from .render import render_hooks_tree


def _slice_view(view: list[ToolHooks], tools: tuple[str, ...]) -> list[ToolHooks]:
    """Narrow the per-tool view to the requested tools.

    Args:
        view: The per-tool entries of the registry, alphabetical by tool.
        tools: The requested tool names — the identities without the package
            prefix; empty means every tool.

    Returns:
        The entries of the requested tools in view order, followed by one
        empty entry per requested name without registrations, in request
        order. A repeated request yields one entry; an unknown name is not an
        error.
    """
    requested = list(dict.fromkeys(tools))
    known = {entry.tool for entry in view}
    selected = [entry for entry in view if entry.tool in known & set(requested)]
    missing = [ToolHooks(tool=name, subscriptions=[], rejections=[]) for name in requested if name not in known]
    return selected + missing


@click.command()
@click.option("--tool", "-t", "tools", multiple=True, help="Narrow the tree to the named tools (repeatable).")
@click.pass_context
def hooks(ctx: click.Context, tools: tuple[str, ...] = ()) -> None:
    """Inspect the hooks registered by the installed tool packages.

    The registry assembles once and prints as a tree: tool, then domain, then
    action, with every refused registration and its reason. A tool with no
    subscriptions and no refusals prints its line alone; an empty registry
    prints nothing and exits 0. -t/--tool narrows the tree to the named tools
    — the tool identity, without the package prefix, as the tool line shows
    it; the option is repeatable, and a requested name without registrations
    keeps an empty entry, not an error. A broken package import fails the
    command with a clean error naming the package.
    \f
    The ``exit_code`` contract follows the ``goga/commands/history``
    precedent: the callback is annotated ``-> None``, returns nothing, and
    exits through ``ctx.exit(0)`` — errors propagate as
    ``click.ClickException`` (stderr, exit 1, no traceback). The command
    emits no action; only the hook checkpoints of the domains do.
    """
    try:
        registry = HookRegistry()
        registry.build_once()
    except ImportError as exc:
        raise click.ClickException(str(exc)) from exc

    view = registry.by_tool()
    if tools:
        view = _slice_view(view, tools)
    render_hooks_tree(view)
    ctx.exit(0)
