from __future__ import annotations

import click

from ..config import resolve_project_name


def resolve_scaffold_name() -> str:
    """Resolve the project name for copier answers data.

    Resolves the project name via the git origin remote URL
    (:func:`goga.config.resolve_project_name`). When the git name is
    unavailable (``None``), falls back to an interactive ``click.prompt`` (no
    default, so it re-prompts on empty input). ``click`` is used only for the
    fallback prompt. On the git-None path nothing is raised — an unavailable
    git name falls back to the prompt rather than propagating
    (``resolve_project_name`` is itself tolerant and never raises). In a
    non-interactive shell with no usable input the prompt exhausts stdin and
    raises ``click.Abort``; that is caught by ``InitLogic.run`` and surfaced
    as a nonzero exit, not here.

    Returns:
        The resolved project name — the git-derived name when available, else
        the value supplied at the fallback prompt.
    """
    name = resolve_project_name()

    if name is None:
        name = click.prompt("Project name")

    return name
