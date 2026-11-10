"""The amendment views of the drift domain hooks zone — the report adjuster and the entry contributor."""

from __future__ import annotations

from dataclasses import dataclass, field

from .facts import EntryFacts


@dataclass(kw_only=True)
class ReportAmendment:
    """The read-and-adjust view of one tool for the report.

    Args:
        report: the finished scoped report — read-only and identical for
            every tool; the receiving hook observes the
            comparison-computed entries only, never another tool's
            adjustment.
    """

    report: list[EntryFacts]

    _adjustment: list | None = field(init=False, default=None, repr=False)

    def adjust(self, entries: list[dict[str, object]]) -> None:
        """Buffer the whole-list replacement of the report.

        Args:
            entries: the adjusted report — each entry a mapping of exactly the
                fields kind (one of the comparison's entry kinds), cell (a
                non-empty string), and types (a list of strings, or omitted for
                a cell-level entry); buffered verbatim into this tool's buffer
                alone and changing nothing until the delivery validates and
                adopts it after the tool's hooks return. The replacement is
                whole — a later call replaces the earlier adjustment; the view
                records no hook identity — the delivery attributes the
                adjustment by observing the buffer change around each hook
                call; the adjusted list may be empty — clearing the report
                entirely is a valid adjustment. The call never cancels,
                redirects, or defers the operation — an adjustment settles the
                final list only — and never emits any provenance — no marker,
                annotation, or flag of the adjustment appears anywhere in the
                output.
        """

        self._adjustment = entries


@dataclass(kw_only=True)
class EntryAmendment:
    """The read-and-contribute view of one tool for one entry.

    Args:
        entry: the entry facts being enriched — read-only and identical
            for every tool; the receiving hook observes the entry's
            facts only, never another tool's contribution.
    """

    entry: EntryFacts

    _pending: list = field(init=False, default_factory=list, repr=False)

    def contribute(self, facts: dict[str, object]) -> None:
        """Buffer one fact-mapping contribution of this tool.

        Args:
            facts: the contribution mapping — fact names to JSON-representable values; buffered
                verbatim into this tool's buffer alone and changing nothing until the delivery
                commits it — the buffer merges key-wise, a later write replacing an earlier one
                on key conflict; an empty mapping contributes nothing. The call never cancels,
                redirects, or defers the operation — a contribution extends the entry's tools
                area only.
        """

        self._pending.append(facts)
