"""The ``render_workflow`` routine — whole-file Jinja rendering of workflow-files."""

from __future__ import annotations

from typing import Any

from jinja2 import Environment, TemplateSyntaxError

# The fixed rendering environment per the jinja2 practice — an accepted ADR
# decision. The standard Undefined keeps the "missing key is falsy/empty"
# semantics the templates depend on; autoescape stays off because the engine
# renders YAML text, not HTML.
_RENDER_ENVIRONMENT = Environment(
    trim_blocks=True,
    lstrip_blocks=True,
    keep_trailing_newline=True,
    autoescape=False,
)


def render_workflow(
    text: str,
    profile_data: dict[str, Any],
    source_name: str = "",
) -> str:
    """Render a whole workflow-file text as a Jinja template with the profile content as context.

    Args:
        text: the raw workflow-file text.
        profile_data: the template context — the entire active profile content,
            or an empty mapping for a context-less render.
        source_name: optional workflow file name carried into error messages.

    Returns:
        The rendered text — the input the standard parser consumes next.

    Raises:
        ValueError: If ``text`` carries a Jinja template syntax error — the
            message names the workflow file, the line number, and the Jinja
            error cause. Nested access on a missing context key raises the
            Jinja ``UndefinedError`` unwrapped.
    """
    try:
        return _RENDER_ENVIRONMENT.from_string(text).render(**profile_data)

    except TemplateSyntaxError as exc:
        raise ValueError(f"{source_name}: template syntax error at line {exc.lineno}: {exc.message}") from None
