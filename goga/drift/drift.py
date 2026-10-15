"""Entry routine — the drift report of the project.

Produces the scoped report through the four view-producer calls: the
complete declared and code-derived views feed the comparison, the filtered
views scope the report. The run is observed and adjusted by the installed
tool packages — the start moment fires before the first producer call, the
settled report and its entries pass the two amendments, and the completion
moment fires on every terminal state of a started run, a failure included.
The routine reads no manifests and no sources itself — the views arrive
fully assembled from the two producers — and every producer error
propagates unchanged.
"""

from __future__ import annotations

from ..codegraph import codegraph
from ..schema import schema
from .compare import DriftEntry, compare_views, scope_entries
from .hooks import DriftFilters, DriftHooks, EntryFacts, ReportEntry, RunCompletion, RunOutcome


def drift(
    cells: list[str] = [],  # noqa: B006 — the CODEMANIFEST contract default; never mutated
    max_depth: int | None = None,
    depends_on: list[str] = [],  # noqa: B006 — the CODEMANIFEST contract default; never mutated
) -> list[DriftEntry]:
    """Produce the drift report of the project, observed and adjusted by the installed tools.

    The report carries the structural discrepancies between the declared
    contracts and the actual code, scoped by the filters. The run fires
    the checkpoint family in a fixed order: the start moment, the view
    production with comparison and scoping, the report amendment, the
    per-entry facts amendment, and the completion moment on the terminal
    state — finished and crashed alike.

    Args:
        cells: Cell paths to scope the report. Empty list scopes nothing.
        max_depth: Maximum nesting depth to scope the report; None means
            no limit.
        depends_on: Scope the report to cells depending on the given paths.

    Returns:
        The settled post-amendment report — the list the last adjusting
            tool left when any tool adjusted, the scoped report otherwise;
            a tool-added or tool-removed entry changes what the caller
            sees and how the caller grades the run. An empty list when
            the views agree; identical project state, configuration,
            filters, and tools produce identical reports. The caller owns
            the serialization of the report.

    Raises:
        FileNotFoundError: When ``.goga/config.yml`` is absent — the
            uninitialized-project error of the code-derived view.
        ValueError: When the AST has parsing errors, the configured language
            is outside python, golang, javascript, kotlin, swift, a source
            file is unparseable, a schema checkpoint hard-fails — every
            producer error propagates unchanged — or a drift amendment
            hard-fails: a crashed hook or a malformed adjustment or
            contribution, the message naming the hook or tool, the action,
            the entry subject where one exists, and the reason.
        ImportError: When a tool package facade fails to import — the
            message names the package; the run never started, so no
            completion moment fires.
    """
    hooks = DriftHooks()

    hooks.emit_run_started(DriftFilters(cells=cells, max_depth=max_depth, depends_on=depends_on))

    carried: list[ReportEntry] | None = None

    try:
        complete_schema = schema([], None, [])
        complete_codegraph = codegraph([], None, [])

        filtered_schema = schema(cells, max_depth, depends_on)
        filtered_codegraph = codegraph(cells, max_depth, depends_on)

        entries = compare_views(complete_schema, complete_codegraph)

        scoped = scope_entries(entries, filtered_schema, filtered_codegraph)

        # The scoped pre-amendment projection — the stage a later failure
        # carries; replaced by the final projection only after the entry
        # loop completes, never a half-enriched list.
        carried = [ReportEntry(kind=entry.kind, cell=entry.cell, types=entry.types) for entry in scoped]

        settled = hooks.amend_report(
            [EntryFacts(kind=entry.kind, cell=entry.cell, types=entry.types) for entry in scoped]
        )

        final: list[DriftEntry] = []

        for facts in settled:
            tools = hooks.amend_entry(facts)
            final.append(DriftEntry(kind=facts.kind, cell=facts.cell, types=facts.types, tools=tools))

        carried = [
            ReportEntry(kind=entry.kind, cell=entry.cell, types=entry.types, tools=entry.tools) for entry in final
        ]

        hooks.emit_run_completed(RunCompletion(report=carried, outcome=RunOutcome.finished, reason=""))

        return final

    except Exception as reason:
        hooks.emit_run_completed(RunCompletion(report=carried, outcome=RunOutcome.crashed, reason=str(reason)))

        raise
