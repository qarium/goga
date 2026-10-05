from __future__ import annotations

import click

from ..config import resolve_project_name


def resolve_scaffold_name() -> str:
    """Resolve the project name for copier answers data.

    Returns:
        The resolved project name — the git-derived name when available, else
        the value supplied at the fallback prompt.
    """
    name = resolve_project_name()

    if name is None:
        name = click.prompt("Project name")

    return name
