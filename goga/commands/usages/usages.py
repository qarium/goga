"""goga usages command group.

The ``usages`` group is a ``click.Group`` container for usages subcommands
registered on the root ``app`` in ``goga/cli.py``. The ``sync`` subcommand
synchronizes cell-level usages from declared git dependencies, and the
``status`` subcommand checks already-synchronized usages against the current
remote git state.
"""

from __future__ import annotations

import click
import yaml

from ...usages import UsageState
from ...usages import status as status_logic
from ...usages import sync as sync_logic

# State -> click foreground color. Used by ``render_status_report`` to color
# each dep/folder line by its status. ``up_to_date`` is visually distinct from
# every other (drift/error) state.
_STATE_COLOR: dict[UsageState, str] = {
    UsageState.new: "yellow",
    UsageState.up_to_date: "green",
    UsageState.out_of_date: "red",
    UsageState.error: "bright_red",
}


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
@click.option("--info", "-i", is_flag=True, default=False, help="Expand each dep into its folders.")
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
        info: When set, expand each dep into a flat, sorted list of its folders
            with per-folder status.
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


def render_status_report(report: object, info: bool) -> None:
    """Render a status report as a colored group -> dep tree.

    Groups are listed sorted; within each group the deps are listed sorted by
    name. Each dep line shows its name and status display string, colored by
    state; an ``error`` dep additionally appends its credential-free message.
    When ``info`` is set, each dep that carries folders is expanded into a
    sorted, per-folder list colored by folder state. Color is applied via
    :func:`click.secho`, which disables it automatically outside a TTY.

    Args:
        report: The :class:`UsageStatusReport` to render. Read-only: this never
            mutates the report and never recomputes a status.
        info: When set, expand each dep into its per-folder statuses.

    Raises:
        click.ClickException: Never raised here; rendering is best-effort.
    """
    by_group: dict[str, list[object]] = {}
    for dep in report.deps:  # type: ignore[attr-defined]
        by_group.setdefault(dep.group, []).append(dep)  # type: ignore[attr-defined]

    for group_name in sorted(by_group):
        click.echo(group_name)
        for dep in sorted(by_group[group_name], key=lambda x: x.dep):
            line = f"  {dep.dep}  {dep.state.value}"
            if dep.state is UsageState.error and dep.error:
                line = f"{line}  ({dep.error})"
            click.secho(line, fg=_STATE_COLOR[dep.state])
            if info and dep.folders:
                for folder in sorted(dep.folders, key=lambda x: x.path):
                    click.secho(
                        f"    {folder.path} {folder.state.value}",
                        fg=_STATE_COLOR[folder.state],
                    )
