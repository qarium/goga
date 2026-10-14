"""Entry routine — the drift report of the project.

Produces the scoped report through the four view-producer calls: the
complete declared and code-derived views feed the comparison, the filtered
views scope the report. The routine reads no manifests and no sources
itself — the views arrive fully assembled from the two producers — and
every producer error propagates unchanged.
"""

from __future__ import annotations

from ..codegraph import codegraph
from ..schema import schema
from .compare import DriftEntry, compare_views, scope_entries


def drift(
    cells: list[str] = [],  # noqa: B006 — the CODEMANIFEST contract default; never mutated
    max_depth: int | None = None,
    depends_on: list[str] = [],  # noqa: B006 — the CODEMANIFEST contract default; never mutated
) -> list[DriftEntry]:
    """Produce the drift report of the project.

    The report carries the structural discrepancies between the declared
    contracts and the actual code, scoped by the filters.

    Args:
        cells: Cell paths to scope the report. Empty list scopes nothing.
        max_depth: Maximum nesting depth to scope the report; None means
            no limit.
        depends_on: Scope the report to cells depending on the given paths.

    Returns:
        The scoped discrepancy entries in the stable order — an empty list
            when the views agree; identical project state, configuration,
            and filters produce identical reports. The caller owns the
            serialization of the report.

    Raises:
        FileNotFoundError: When ``.goga/config.yml`` is absent — the
            uninitialized-project error of the code-derived view.
        ValueError: When the AST has parsing errors, the configured language
            is outside python, golang, javascript, kotlin, swift, a source
            file is unparseable, or a schema checkpoint hard-fails — every
            producer error propagates unchanged.
    """
    complete_schema = schema([], None, [])
    complete_codegraph = codegraph([], None, [])

    filtered_schema = schema(cells, max_depth, depends_on)
    filtered_codegraph = codegraph(cells, max_depth, depends_on)

    entries = compare_views(complete_schema, complete_codegraph)

    return scope_entries(entries, filtered_schema, filtered_codegraph)
