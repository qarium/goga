"""goga usages command group.

The ``usages`` group is a ``click.Group`` container for usages subcommands
registered on the root ``app`` in ``goga/cli.py``. The ``sync`` subcommand
synchronizes cell-level usages from declared git dependencies, and the
``status`` subcommand checks already-synchronized usages against the current
remote git state.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import click
import yaml

from ...usages import DepStatus, EntryChange, EntryKind, EntryStatus, UsageState, UsageStatusReport
from ...usages import status as status_logic
from ...usages import sync as sync_logic

# Per-node diff verdict -> the bracketed marker the tree prints.
_CHANGE_MARKER: dict[EntryChange, str] = {
    EntryChange.unchanged: "[ ]",
    EntryChange.modified: "[*]",
    EntryChange.added: "[+]",
    EntryChange.removed: "[-]",
}

# Marker -> click foreground color. Only the *changed* markers are colored; the
# unchanged ``"[ ]"`` marker (and the plain tree skeleton) stays uncolored so the
# eye is drawn to drift. ``"[!]"`` (error) has no EntryChange backing — it is a
# dep-only marker colored here alongside the others.
_MARKER_COLOR: dict[str, str] = {
    "[*]": "yellow",  # modified / out of date
    "[+]": "green",  # added / new
    "[-]": "red",  # removed / deleted
    "[!]": "magenta",  # error
}

# Dep-level UsageState -> per-node marker (the dep is rendered as the tree root
# of its entries). ``error`` is special-cased to ``"[!]"`` in the renderer.
_DEP_CHANGE: dict[UsageState, EntryChange] = {
    UsageState.new: EntryChange.added,
    UsageState.up_to_date: EntryChange.unchanged,
    UsageState.out_of_date: EntryChange.modified,
}


@dataclass(kw_only=True)
class _Node:
    """One node of the rendered entry tree (a file or a directory)."""

    name: str
    kind: EntryKind
    change: EntryChange
    children: dict[str, _Node] = field(default_factory=dict)


@click.group()
def usages() -> None:
    """Manage cell-level usages synchronized from git dependencies."""


@usages.command("sync")
@click.option("--force", "-f", is_flag=True, default=False, help="Clean .goga/usages/ then re-sync all deps.")
@click.pass_context
def sync(ctx: click.Context, force: bool) -> None:
    """Synchronize cell-level usages from declared git dependencies.

    Reads the ``usages`` section of ``.goga/config.yml`` and, for each declared
    ``<group>/<dep>`` git dependency, clones the repository and deploys its
    cell-level usages into ``.goga/usages/<group>/<dep>/``.

    Args:
        ctx: Click execution context used to control process exit codes.
        force: When set, clear ``.goga/usages/`` (except ``cooks`` and root
            files) and re-sync every dep; otherwise sync incrementally, skipping
            deps whose target directory already exists.

    Raises:
        click.ClickException: When the configuration file cannot be loaded or
            parsed (FileNotFoundError, KeyError, ValueError, yaml.YAMLError
            propagated from ``sync_logic``).
    """
    try:
        exit_code = sync_logic(force)
    except (FileNotFoundError, KeyError, ValueError, yaml.YAMLError) as exc:
        raise click.ClickException(str(exc)) from exc

    ctx.exit(exit_code)


@usages.command("status")
@click.option("--info", "-i", is_flag=True, default=False, help="Expand each dep into its per-node entry tree.")
@click.option("--group", "-g", default=None, help="Limit the check to one group.")
@click.option("--dep", "-d", default=None, help="Limit the check to one dep name.")
@click.pass_context
def status(ctx: click.Context, info: bool, group: str | None, dep: str | None) -> None:
    """Check synchronized usages against the current remote git state.

    Reads the ``usages`` section of ``.goga/config.yml`` and, for each declared
    ``<group>/<dep>`` git dependency, compares the already-synchronized tree
    under ``.goga/usages/<group>/<dep>/`` against the current remote state and
    reports one of ``new`` / ``up to date`` / ``out of date`` / ``error`` per
    dep. The check is read-only: it never modifies ``.goga/usages/``.

    Args:
        ctx: Click execution context used to control process exit codes.
        info: When set, expand each dep into its per-node file/folder tree with
            per-node status markers.
        group: When set, limit the check to deps under this group.
        dep: When set, limit the check to deps with this name.

    Raises:
        click.ClickException: When the configuration file cannot be loaded or
            parsed (FileNotFoundError, KeyError, ValueError, yaml.YAMLError
            propagated from ``status_logic``).
    """
    try:
        report = status_logic(group, dep)
    except (FileNotFoundError, KeyError, ValueError, yaml.YAMLError) as exc:
        raise click.ClickException(str(exc)) from exc

    render_status_report(report, info)
    ctx.exit(report.exit_code)


def render_status_report(report: UsageStatusReport, info: bool) -> None:
    """Render a status report as a colored ``group/ -> dep/`` ASCII tree.

    Groups are listed sorted; within each group the deps are listed sorted by
    name. Each dep is a tree node rendered with a bracketed status marker
    (``[ ]`` unchanged, ``[*]`` modified, ``[+]`` new, ``[!]`` error) derived from
    its :class:`UsageState`; an ``error`` dep additionally appends its
    credential-free message. With ``info`` set, each dep is expanded into its
    per-node file/folder tree, each node carrying its own marker.

    Color is applied **only** to the changed markers (``[*]``, ``[+]``, ``[-]``,
    ``[!]``) — never to ``[ ]`` or the tree skeleton — and auto-disables outside a
    TTY (piped output, CI logs) so the same command stays readable in scripts.

    Args:
        report: The :class:`UsageStatusReport` to render. Read-only: this never
            mutates the report and never recomputes a status.
        info: When set, expand each dep into its per-node file/folder tree.

    Raises:
        click.ClickException: Never raised here; rendering is best-effort.
    """
    color = click.get_text_stream("stdout").isatty()

    by_group: dict[str, list[DepStatus]] = {}
    for dep in report.deps:
        by_group.setdefault(dep.group, []).append(dep)

    for group_name in sorted(by_group):
        click.echo(f"{group_name}/")
        deps = sorted(by_group[group_name], key=lambda x: x.dep)
        for index, dep in enumerate(deps):
            _render_dep(dep, last=index == len(deps) - 1, prefix="", info=info, color=color)


def _render_dep(dep: DepStatus, last: bool, prefix: str, info: bool, color: bool) -> None:
    """Render one dep node and, under ``info``, its per-node entry tree."""
    branch = "└── " if last else "├── "
    marker = "[!]" if dep.state is UsageState.error else _CHANGE_MARKER[_DEP_CHANGE[dep.state]]
    tail = f"  ({dep.error})" if dep.state is UsageState.error and dep.error else ""
    click.echo(f"{prefix}{branch}{_style(marker, color)} {dep.dep}/{tail}")

    if info and dep.entries:
        child_prefix = prefix + ("    " if last else "│   ")
        _render_nodes(_build_tree(dep.entries), child_prefix, color)


def _render_nodes(nodes: dict[str, _Node], prefix: str, color: bool) -> None:
    """Render a level of the entry tree, recursing into directories."""
    items = sorted(nodes.values(), key=lambda node: node.name)
    for index, node in enumerate(items):
        last = index == len(items) - 1
        branch = "└── " if last else "├── "
        suffix = "/" if node.kind is EntryKind.dir else ""
        click.echo(f"{prefix}{branch}{_style(_CHANGE_MARKER[node.change], color)} {node.name}{suffix}")
        if node.children:
            _render_nodes(node.children, prefix + ("    " if last else "│   "), color)


def _style(marker: str, color: bool) -> str:
    """Return ``marker`` colored with its foreground color, or plain when color is off.

    The unchanged ``"[ ]"`` marker (absent from :data:`_MARKER_COLOR`) is always
    plain — only changed markers carry color.
    """
    foreground = _MARKER_COLOR.get(marker)
    return click.style(marker, fg=foreground) if color and foreground else marker


def _build_tree(entries: list[EntryStatus]) -> dict[str, _Node]:
    """Fold a flat, path-sorted entry list into a nested name -> :class:`_Node` map.

    Directory entries (emitted by the diff for every ancestor prefix) seed their
    node with its aggregated verdict before their descendants are placed, so each
    directory node keeps its precomputed :class:`EntryChange` rather than a
    default.
    """
    root: dict[str, _Node] = {}
    for entry in entries:
        parts = entry.path.split("/")
        cursor = root
        for segment in parts[:-1]:
            cursor = cursor.setdefault(
                segment, _Node(name=segment, kind=EntryKind.dir, change=EntryChange.unchanged)
            ).children
        leaf = parts[-1]
        existing = cursor.get(leaf)
        if existing is None:
            cursor[leaf] = _Node(name=leaf, kind=entry.kind, change=entry.change)
        else:
            # A dir entry was seeded first; keep its children, adopt the entry's
            # verdict and kind.
            existing.change = entry.change
            existing.kind = entry.kind
    return root
