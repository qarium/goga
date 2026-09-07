"""Console rendering for the ``goga hooks`` command.

The entity declared in the cell CODEMANIFEST with ``location: render.py``:
the tree renderer of the per-tool registry view. It is pure output — the view
prints as given, never mutated and never re-sorted; the caller owns the
collection and the slice. Only the domain lines of one tool are ordered,
alphabetically, as the documented tree fixes it.
"""

from __future__ import annotations

import click

from ...hooks import ToolHooks


def render_hooks_tree(view: list[ToolHooks]) -> None:
    """Render the registry view as the tool tree.

    One tool line per entry — the tools are the top level, there is no root
    line. Under a tool, one domain line per distinct domain of its
    subscriptions, ordered alphabetically; under a domain, one action line per
    subscription of that domain — the action name, two spaces, the bare hook
    name. Every refused registration of the tool prints after the domains with
    its reason, the attempted name in double quotes. A tool without
    subscriptions and without refusals prints its line alone; an empty view
    prints nothing.

    Args:
        view: The per-tool entries — already sliced by the caller.
    """
    for entry in view:
        click.echo(entry.tool)
        for domain in sorted({subscription.domain for subscription in entry.subscriptions}):
            click.echo(f"  {domain}")
            for subscription in entry.subscriptions:
                if subscription.domain == domain:
                    click.echo(f"    {subscription.action}  {subscription.name}")
        for rejection in entry.rejections:
            click.echo(f'  rejected {rejection.domain}/{rejection.action} "{rejection.name}": {rejection.reason}')
