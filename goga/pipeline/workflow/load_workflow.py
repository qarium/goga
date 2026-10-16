"""The ``load_workflow`` routine — the single loading chain of a workflow-file."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .loaded_workflow import LoadedWorkflow
from .parse_workflow import parse_workflow
from .render_workflow import render_workflow
from .resolve_activation import resolve_activation
from .resolve_profile import resolve_profile

# A top-level `profile:` line of the RAW workflow text, anchored at column 0 —
# an indented `profile:` line belongs to some nested mapping and never peeks.
_PROFILE_LINE_PATTERN = re.compile(r"^profile:[ \t]*(.*)$")

# Shortest value a matching quote pair can wrap — anything shorter stays as-is.
_MIN_QUOTED_LENGTH = 2


def _strip_trailing_comment(value: str) -> str:
    """Strip a trailing ``#`` comment from a peeked profile value.

    Args:
        value: the raw ``profile:`` value text (quotes still included).

    Returns:
        The value with the comment removed — a ``#`` at the value start or
        preceded by whitespace starts a comment ONLY outside quotes, so a
        quoted name may itself contain ``#``.
    """
    quote: str | None = None

    for index, char in enumerate(value):
        if quote is not None:
            if char == quote:
                quote = None
        elif char in "'\"":
            quote = char
        elif char == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index]

    return value


def _peek_literal_profile(text: str) -> str | None:
    """Peek the literal top-level ``profile:`` default from the raw workflow text.

    Args:
        text: the raw workflow-file text (before any rendering).

    Returns:
        The literal default profile name, or ``None`` when the file carries no
        top-level ``profile:`` line, its value is empty or whitespace-only, or
        the value contains Jinja markers — a default that materializes only
        through template rendering does not participate in activation.
    """
    for line in text.splitlines():
        match = _PROFILE_LINE_PATTERN.match(line)

        if match is None:
            continue

        value = _strip_trailing_comment(match.group(1)).strip()

        if not value or "{{" in value or "{%" in value:
            return None

        if len(value) >= _MIN_QUOTED_LENGTH and value[0] == value[-1] and value[0] in "'\"":
            value = value[1:-1].strip()

        return value or None

    return None


def load_workflow(
    workflow_path: Path,
    cli_profile: str | None = None,
    env_profile: str | None = None,
    home_profiles: dict[str, dict[str, Any]] | None = None,
) -> LoadedWorkflow:
    """Load a workflow-file through the whole chain: read, peek, activate, resolve, render, parse.

    Args:
        workflow_path: the workflow-file path — the caller owns composition
            and existence guards; an unreadable path raises ``OSError``
            unchanged.
        cli_profile: the CLI activation channel value, or None.
        env_profile: the environment activation channel value, or None.
        home_profiles: the decoded home bundle, or None (treated as empty).

    Returns:
        The loaded workflow — the parsed document of the rendered text plus
        the profile active during the render (None when no profile resolved;
        the render then ran with an empty context).

    Raises:
        OSError: If the workflow-file cannot be read — propagated unchanged.
        ValueError: If the resolved profile is missing or malformed, if the
            text carries a Jinja syntax error, or if the rendered text fails
            the standard structural validation.
    """
    text = workflow_path.read_text()

    default = _peek_literal_profile(text)

    name = resolve_activation(cli_profile, env_profile, default)

    profile = None

    if name is not None:
        profile = resolve_profile(name, Path.cwd() / ".goga" / "profiles", home_profiles or {})

    rendered = render_workflow(text, profile.data if profile is not None else {}, source_name=workflow_path.name)

    document = parse_workflow(rendered)

    return LoadedWorkflow(document=document, profile=profile)
