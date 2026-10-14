"""Orchestrator — the prospective cell graph of the project code.

Wires the whole pipeline for one configured language: the project
configuration is loaded first (an absent file is the uninitialized-project
error), the language is validated against the supported whitelist, the
exclusion list comes from the lint section, and the discovered sources flow
through the three analysis stages in order into the renderer. The run is
read-only, deterministic, and idempotent — identical code and configuration
produce byte-identical output.
"""

from __future__ import annotations

from pathlib import Path

from ..config import load_project_config
from .analysis import collect_facts, derive_units, resolve_links
from .discovery import discover_sources
from .render import render_graph

_SUPPORTED_LANGUAGES = ("python", "golang", "javascript", "kotlin", "swift")


def codegraph(
    cells: list[str] = [],  # noqa: B006 — the CODEMANIFEST contract default; never mutated
    max_depth: int | None = None,
    depends_on: list[str] = [],  # noqa: B006 — the CODEMANIFEST contract default; never mutated
) -> str:
    """Derive the prospective cell graph of the project code and render it as JSON.

    Args:
        cells: Cell paths to include in the output — the matching cells plus
            their ancestor chain survive. Empty list includes all cells.
        max_depth: Maximum nesting depth of the tree; None means no limit.
        depends_on: Keep only cells whose own or any descendant dependencies
            reach at least one of the given paths.

    Returns:
        The JSON document of the tree — an empty project renders as ``[]``;
            identical code and configuration produce byte-identical output.

    Raises:
        FileNotFoundError: When ``.goga/config.yml`` is absent — the
            uninitialized-project error.
        ValueError: When the configured language is outside python, golang,
            javascript, kotlin, swift, or when a source file is unparseable —
            the error names the file.
    """
    config = load_project_config()

    language = config.language

    if language not in _SUPPORTED_LANGUAGES:
        expected = ", ".join(_SUPPORTED_LANGUAGES)
        raise ValueError(f"unsupported language: {language!r}; expected one of {expected}")

    ignore = config.lint.ignore if config.lint is not None else []

    files = discover_sources(language, ignore)
    root = Path.cwd()

    facts = collect_facts(files, language)
    units = derive_units(facts, language)
    links = resolve_links(units, facts, language, root)

    return render_graph(units, links, cells, max_depth, depends_on)
