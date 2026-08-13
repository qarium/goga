from __future__ import annotations

import click

from ..config import resolve_project_name


def resolve_scaffold_name() -> str:
    """Resolve the project name for copier answers data.

    Resolves the project name via the git origin remote URL
    (:func:`goga.config.resolve_project_name`). When the git name is
    unavailable (``None``), falls back to an interactive ``click.prompt`` so a
    non-empty name is always produced. ``click`` is used only for the fallback
    prompt.

    Returns:
        The resolved project name — the git-derived name when available, else
        the value supplied at the fallback prompt.

    Raises:
        Nothing on the git-None path: an unavailable git name falls back to the
        prompt rather than propagating. (``resolve_project_name`` is itself
        tolerant and never raises.)
    """
    name = resolve_project_name()
    if name is None:
        name = click.prompt("Project name")
    return name
