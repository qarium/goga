"""Contract and logic tests for the entity declared in
``goga/drift/hooks/CODEMANIFEST`` with ``location: events.py``:

- ``DriftHooks()`` — the checkpoint surface of the drift domain: the two
  soft run moments (``emit_run_started`` / ``emit_run_completed``) delivered
  through the platform ``emit_hook_event``, the hard whole-list report
  amendment ``amend_report``, and the hard per-entry contribution walk
  ``amend_entry``

The delivery runs for real over the platform boundary fixtures of
``tests/hooks/conftest.py`` (re-exported by the zone test package) — the
registry, the registrars, and the delivery execute the actual platform
code; only the installed-packages mapping and the ``sys.modules`` entry of
a fake ``goga_tool_*`` package are pinned.
"""

from __future__ import annotations

import inspect
import logging
import typing

import pytest
from goga.drift.hooks import (
    DriftFilters,
    DriftHooks,
    EntryFacts,
    ReportEntry,
    RunCompletion,
    RunOutcome,
)


def _entry_facts(kind: str = "schema_only", cell: str = "goga/config") -> EntryFacts:
    """A minimal delivered entry — the schema-only direction, a cell-level subject.

    Args:
        kind: the entry kind of the returned facts.
        cell: the cell path of the returned facts.

    Returns:
        The entry facts handed to the checkpoint under test.
    """
    return EntryFacts(kind=kind, cell=cell, types=None)


def _typed_entry() -> EntryFacts:
    """A minimal delivered entry carrying a type list.

    Returns:
        The entry facts handed to the checkpoint under test.
    """
    return EntryFacts(kind="schema_only", cell="goga/config", types=["ProjectConfig"])


# --- Contract tests ---


class TestCheckpointContract:
    def test_surface_is_importable_from_the_facade(self) -> None:
        """The entity lives on the zone facade and resolves to ``events.py``."""
        import goga.drift.hooks as facade
        from goga.drift.hooks.events import DriftHooks as Declared

        assert facade.DriftHooks is Declared
        assert facade.DriftHooks is DriftHooks

        assert "DriftHooks" in facade.__all__

    def test_constructor_takes_no_arguments(self) -> None:
        """Cheap construction — the surface declares no parameter."""
        assert list(inspect.signature(DriftHooks).parameters) == []

    def test_emit_run_started_carries_the_declared_signature(self) -> None:
        """The start moment takes exactly the declared parameter and returns nothing."""
        parameters = inspect.signature(DriftHooks.emit_run_started).parameters

        assert list(parameters) == ["self", "filters"]
        assert typing.get_type_hints(DriftHooks.emit_run_started) == {
            "filters": DriftFilters,
            "return": type(None),
        }

    def test_amend_report_carries_the_declared_signature(self) -> None:
        """The report amendment takes exactly the declared parameter and returns the settled list."""
        parameters = inspect.signature(DriftHooks.amend_report).parameters

        assert list(parameters) == ["self", "report"]
        assert typing.get_type_hints(DriftHooks.amend_report) == {
            "report": list[EntryFacts],
            "return": list[EntryFacts],
        }

    def test_amend_entry_carries_the_declared_signature(self) -> None:
        """The entry amendment takes exactly the declared parameter and returns the tools area."""
        parameters = inspect.signature(DriftHooks.amend_entry).parameters

        assert list(parameters) == ["self", "entry"]
        assert typing.get_type_hints(DriftHooks.amend_entry) == {
            "entry": EntryFacts,
            "return": dict[str, dict[str, object]],
        }

    def test_emit_run_completed_carries_the_declared_signature(self) -> None:
        """The completion moment takes exactly the declared parameter and returns nothing."""
        parameters = inspect.signature(DriftHooks.emit_run_completed).parameters

        assert list(parameters) == ["self", "completion"]
        assert typing.get_type_hints(DriftHooks.emit_run_completed) == {
            "completion": RunCompletion,
            "return": type(None),
        }

    def test_surface_stays_in_the_facade_alongside_the_zone_names(self) -> None:
        """The zone facade keeps the checkpoint surface and the zone names together."""
        import goga.drift.hooks as facade

        for name in (
            "DriftFilters",
            "DriftHooks",
            "EntryAmendment",
            "EntryFacts",
            "ReportAmendment",
            "ReportEntry",
            "RunCompletion",
            "RunOutcome",
            "ToolContribution",
            "merge_entry_contributions",
        ):
            assert name in facade.__all__


# --- Logic tests: the run moments (real platform) ---


class TestRunMoments:
    def test_emit_run_started_is_soft_and_delivers_the_filters(
        self,
        pin_package_environment,
        install_tool_package,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """One tool, two hooks — the observer records the filters, the crash only warns, nothing raises."""
        pin_package_environment({"goga_tool_watch": ["watch-dist"]})
        recorded: list[object] = []

        def register(hooks: object) -> None:
            def watch(context: object) -> None:
                recorded.append((context.filters.cells, context.filters.max_depth))  # type: ignore[attr-defined]

            def boom(context: object) -> None:
                raise RuntimeError("nope")

            hooks.subscribe("drift", "run_started", "watch", watch)  # type: ignore[attr-defined]
            hooks.subscribe("drift", "run_started", "boom", boom)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_watch", register_hooks=register)

        with caplog.at_level(logging.WARNING, logger="goga.hooks.dispatch.emit"):
            DriftHooks().emit_run_started(DriftFilters(cells=["goga/config"], max_depth=2, depends_on=[]))

        assert recorded == [(["goga/config"], 2)]  # the moment delivered — and continued past the crash

        warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
        assert any("watch" in record.getMessage() and "drift.run_started" in record.getMessage() for record in warnings)

    def test_emit_run_completed_delivers_the_terminal_facts(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """One observing tool — the completion moment delivers the outcome, the report, the reason."""
        pin_package_environment({"goga_tool_watch": ["watch-dist"]})
        recorded: list[object] = []

        def register(hooks: object) -> None:
            def watch(context: object) -> None:
                completion = context.completion  # type: ignore[attr-defined]
                recorded.append((completion.outcome, len(completion.report or []), completion.reason))

            hooks.subscribe("drift", "run_completed", "watch", watch)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_watch", register_hooks=register)

        DriftHooks().emit_run_completed(
            RunCompletion(
                report=[ReportEntry(kind="schema_only", cell="a", types=None, tools={})],
                outcome=RunOutcome.finished,
                reason="",
            )
        )

        assert recorded == [(RunOutcome.finished, 1, "")]


# --- Logic tests: the report amendment (real platform) ---


class TestAmendReportDelivery:
    def test_amend_report_last_adjusting_tool_wins_and_tools_are_blind(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """One adjusting tool, one observing tool — the observer reads the original, never the adjustment."""
        pin_package_environment({"goga_tool_alpha": ["alpha-dist"], "goga_tool_beta": ["beta-dist"]})
        observed: list[tuple[str, str]] = []

        def register_alpha(hooks: object) -> None:
            def adjust(context: object) -> None:
                context.adjust([{"kind": "schema_only", "cell": "a"}])  # type: ignore[attr-defined]

            hooks.subscribe("drift", "amend_report", "adjusting", adjust)  # type: ignore[attr-defined]

        def register_beta(hooks: object) -> None:
            def read(context: object) -> None:
                observed.extend((entry.kind, entry.cell) for entry in context.report)  # type: ignore[attr-defined]

            hooks.subscribe("drift", "amend_report", "reading", read)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_alpha", register_hooks=register_alpha)
        install_tool_package("goga_tool_beta", register_hooks=register_beta)

        settled = DriftHooks().amend_report([EntryFacts(kind="codegraph_only", cell="z", types=None)])

        assert settled == [EntryFacts(kind="schema_only", cell="a", types=None)]
        assert observed == [("codegraph_only", "z")]  # the original entry only — z, never a

    def test_amend_report_two_adjusting_tools_last_wins_over_the_original(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Two adjusting tools — the later replacement wins whole; the earlier appears nowhere."""
        pin_package_environment({"goga_tool_alpha": ["alpha-dist"], "goga_tool_beta": ["beta-dist"]})

        def register_alpha(hooks: object) -> None:
            def adjust(context: object) -> None:
                context.adjust([{"kind": "schema_only", "cell": "from-alpha"}])  # type: ignore[attr-defined]

            hooks.subscribe("drift", "amend_report", "adjusting", adjust)  # type: ignore[attr-defined]

        def register_beta(hooks: object) -> None:
            def adjust(context: object) -> None:
                context.adjust([{"kind": "codegraph_only", "cell": "from-beta"}])  # type: ignore[attr-defined]

            hooks.subscribe("drift", "amend_report", "adjusting", adjust)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_alpha", register_hooks=register_alpha)
        install_tool_package("goga_tool_beta", register_hooks=register_beta)

        settled = DriftHooks().amend_report([EntryFacts(kind="schema_only", cell="orig", types=None)])

        assert settled == [EntryFacts(kind="codegraph_only", cell="from-beta", types=None)]
        assert "from-alpha" not in str(settled)  # whole replacement, never a chained merge

    def test_amend_report_empty_adjustment_clears_and_adds_entries(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Clearing is a valid adjustment — and an adding adjustment settles its entries verbatim."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})
        payloads: list[list[dict[str, object]]] = [[{"kind": "codegraph_only", "cell": "extra", "types": ["thing"]}]]

        def register(hooks: object) -> None:
            def adjust(context: object) -> None:
                context.adjust(payloads[0])  # type: ignore[attr-defined]

            hooks.subscribe("drift", "amend_report", "adjusting", adjust)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        surface = DriftHooks()
        scoped = [EntryFacts(kind="schema_only", cell="orig", types=None)]

        # Scenario A: clearing the report entirely.
        payloads[0] = []

        assert surface.amend_report(scoped) == []

        # Scenario B on a fresh surface: adding an entry the comparison never produced.
        payloads[0] = [{"kind": "codegraph_only", "cell": "extra", "types": ["thing"]}]

        assert DriftHooks().amend_report(scoped) == [EntryFacts(kind="codegraph_only", cell="extra", types=["thing"])]

    def test_amend_report_carries_empty_types_list_and_cell_level_added_entry(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """An adjusted empty types list is a list of strings; an omitted types is a cell-level entry."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def adjust(context: object) -> None:
                context.adjust(  # type: ignore[attr-defined]
                    [
                        {"kind": "schema_only", "cell": "leaf", "types": []},
                        {"kind": "codegraph_only", "cell": "whole"},
                    ]
                )

            hooks.subscribe("drift", "amend_report", "adjusting", adjust)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        settled = DriftHooks().amend_report([EntryFacts(kind="schema_only", cell="orig", types=None)])

        assert settled == [
            EntryFacts(kind="schema_only", cell="leaf", types=[]),
            EntryFacts(kind="codegraph_only", cell="whole", types=None),
        ]

    @pytest.mark.parametrize(
        "adjustment",
        [
            pytest.param([{"kind": "wrong", "cell": "a"}], id="an-unknown-kind"),
            pytest.param([{"kind": "schema_only"}], id="a-missing-cell"),
            pytest.param([{"kind": "schema_only", "cell": ""}], id="an-empty-cell"),
            pytest.param([{"kind": "schema_only", "cell": "a", "extra": 1}], id="a-key-outside-the-shape"),
            pytest.param([{"kind": "schema_only", "cell": "a", "types": "b"}], id="a-non-list-types"),
            pytest.param(("not", "a list"), id="a-non-list-adjustment"),
            pytest.param([["kind", "cell"]], id="a-non-mapping-entry"),
        ],
    )
    def test_amend_report_malformed_adjustment_is_never_adopted(
        self,
        pin_package_environment,
        install_tool_package,
        adjustment: object,
    ) -> None:
        """A shape violation fails the attributed hook — never sanitized, never adopted."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def adjust(context: object) -> None:
                context.adjust(adjustment)  # type: ignore[arg-defined]

            hooks.subscribe("drift", "amend_report", "adjusting", adjust)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        with pytest.raises(
            ValueError,
            match=r"hook .* of tool .* failed on drift\.amend_report: malformed adjustment",
        ):
            DriftHooks().amend_report([EntryFacts(kind="schema_only", cell="orig", types=None)])

    def test_amend_report_crashed_hook_stops_and_adopts_nothing(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A crashing hook stops the walk at the first failure — the later tool never runs."""
        pin_package_environment({"goga_tool_alpha": ["alpha-dist"], "goga_tool_beta": ["beta-dist"]})
        observed: list[str] = []

        def register_alpha(hooks: object) -> None:
            def boom(context: object) -> None:
                raise RuntimeError("boom")

            hooks.subscribe("drift", "amend_report", "boom", boom)  # type: ignore[attr-defined]

        def register_beta(hooks: object) -> None:
            def adjust(context: object) -> None:
                observed.append("beta")
                context.adjust([{"kind": "schema_only", "cell": "from-beta"}])  # type: ignore[attr-defined]

            hooks.subscribe("drift", "amend_report", "adjusting", adjust)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_alpha", register_hooks=register_alpha)
        install_tool_package("goga_tool_beta", register_hooks=register_beta)

        with pytest.raises(ValueError, match=r"hook boom of tool alpha failed on drift\.amend_report: boom"):
            DriftHooks().amend_report([EntryFacts(kind="schema_only", cell="orig", types=None)])

        assert observed == []  # the later tool never ran — first-failure stop


# --- Logic tests: the entry amendment (real platform) ---


class TestAmendEntryDelivery:
    def test_amend_entry_commits_facts_per_entry(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """One tool, one buffered fact — the composed tools area under the platform identity."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def ticket(context: object) -> None:
                context.contribute({"ticket": "GOGA-1"})  # type: ignore[attr-defined]

            hooks.subscribe("drift", "amend_entry", "ticket", ticket)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        # The platform derives goga_tool_docs -> docs.
        assert DriftHooks().amend_entry(EntryFacts(kind="schema_only", cell="mix", types=["stale"])) == {
            "docs": {"ticket": "GOGA-1"}
        }

    def test_amend_entry_committed_area_is_owned(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Ownership of the commit — a retained payload mutated at a later entry never reaches a committed area."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def ticket(self: object, context: object) -> None:
                if not hasattr(self, "sink"):
                    self.sink = {"ticket": 1}  # type: ignore[attr-defined]
                else:
                    self.sink["ticket"] = 99  # the in-place mutation before every later contribute  # type: ignore[index]

                context.contribute(self.sink)  # type: ignore[arg-type]

            hooks.subscribe("drift", "amend_entry", "ticket", ticket)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        surface = DriftHooks()
        first = surface.amend_entry(_entry_facts(cell="a"))
        second = surface.amend_entry(_entry_facts(cell="b"))

        assert first == {"docs": {"ticket": 1}}
        assert second == {"docs": {"ticket": 99}}
        assert first == {"docs": {"ticket": 1}}  # STILL — the ownership cut of the commit point

    def test_amend_entry_hard_failure_names_the_entry(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A raising hook stops the walk — the error names the hook, the tool, the action, and the entry."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def boom(context: object) -> None:
                raise RuntimeError("kaboom")

            hooks.subscribe("drift", "amend_entry", "boom", boom)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        with pytest.raises(
            ValueError,
            match=r"hook boom of tool docs failed on drift\.amend_entry at codegraph_only extra: kaboom",
        ):
            DriftHooks().amend_entry(EntryFacts(kind="codegraph_only", cell="extra", types=["helper"]))

    def test_amend_entry_structurally_malformed_contribution_names_the_entry(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A malformed payload fails the tool commit with the entry subject in the message."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute({"k": {}})  # type: ignore[arg-defined]

            hooks.subscribe("drift", "amend_entry", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        with pytest.raises(
            ValueError,
            match=r"tool docs failed on drift\.amend_entry at schema_only mix: structurally malformed contribution",
        ) as excinfo:
            DriftHooks().amend_entry(EntryFacts(kind="schema_only", cell="mix", types=None))

        # The nested structural detail rides along — the empty nested mapping of the merged buffer.
        assert "empty mapping at the merged contribution.k" in str(excinfo.value)

    def test_amend_entry_fresh_view_per_tool_keeps_writes_local(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Mutual blindness — one tool's in-place write never reaches another view or the caller."""
        pin_package_environment({"goga_tool_alpha": ["alpha-dist"], "goga_tool_beta": ["beta-dist"]})
        observed: dict[str, object] = {}

        def register_alpha(hooks: object) -> None:
            def mutate(context: object) -> None:
                context.entry.types.append("X")  # type: ignore[attr-defined]  # the in-place channel — local to this view

            hooks.subscribe("drift", "amend_entry", "mutating", mutate)  # type: ignore[attr-defined]

        def register_beta(hooks: object) -> None:
            def read(context: object) -> None:
                observed["types"] = list(context.entry.types)  # type: ignore[attr-defined]

            hooks.subscribe("drift", "amend_entry", "reading", read)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_alpha", register_hooks=register_alpha)
        install_tool_package("goga_tool_beta", register_hooks=register_beta)

        facts = _typed_entry()
        tools = DriftHooks().amend_entry(facts)

        assert observed["types"] == ["ProjectConfig"]  # the comparison-computed list, never alpha's write
        assert facts.types == ["ProjectConfig"]  # the caller's instance untouched
        assert tools == {}  # neither tool contributed a fact


# --- Logic tests: the inert zone ---


class TestZoneInertness:
    @pytest.mark.parametrize("checkpoint", ["run_started", "run_completed", "amend_report", "amend_entry"])
    def test_zone_checkpoints_without_subscriptions_are_inert(
        self,
        pin_package_environment,
        checkpoint: str,
    ) -> None:
        """No subscriptions — no raise, value-identical report, the empty tools area.

        This is what keeps plain ``goga drift`` byte-identical when no
        tool subscribes: the checkpoints fire, deliver nothing, and leave
        the run untouched.
        """
        pin_package_environment({})
        surface = DriftHooks()

        if checkpoint == "run_started":
            surface.emit_run_started(DriftFilters(cells=[], max_depth=None, depends_on=[]))
        elif checkpoint == "run_completed":
            surface.emit_run_completed(RunCompletion(report=None, outcome=RunOutcome.crashed, reason="x"))
        elif checkpoint == "amend_report":
            assert surface.amend_report([_entry_facts()]) == [_entry_facts()]
        else:
            assert surface.amend_entry(_entry_facts()) == {}

    def test_amend_report_returns_input_values_unchanged_without_subscriptions(
        self,
        pin_package_environment,
    ) -> None:
        """The inert amendment settles value-identical fresh copies and never mutates the input."""
        pin_package_environment({})

        report = [
            EntryFacts(kind="schema_only", cell="a", types=None),
            EntryFacts(kind="codegraph_only", cell="b", types=["x"]),
        ]

        assert DriftHooks().amend_report(report) == report
        assert len(report) == 2  # the caller's list object untouched

    def test_amend_report_builds_registry_once_per_run(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Moments and amendments on one surface — the package enumeration runs exactly once."""
        boundary = pin_package_environment({"goga_tool_demo": ["demo"]})
        delivered: list[str] = []

        def register(hooks: object) -> None:
            def started(context: object) -> None:
                delivered.append("run_started")

            def adjust(context: object) -> None:
                delivered.append("amend_report")

            hooks.subscribe("drift", "run_started", "started", started)  # type: ignore[attr-defined]
            hooks.subscribe("drift", "amend_report", "adjusting", adjust)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register)

        surface = DriftHooks()
        surface.emit_run_started(DriftFilters(cells=[], max_depth=None, depends_on=[]))
        surface.amend_report([_entry_facts()])

        assert boundary.call_count == 1
        assert delivered == ["run_started", "amend_report"]  # both checkpoints delivered

    def test_construction_enumerates_nothing(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Cheap construction — the package environment stays unread."""
        boundary = pin_package_environment({"goga_tool_demo": ["demo"]})

        def register(hooks: object) -> None:
            def started(context: object) -> None:
                pass

            hooks.subscribe("drift", "run_started", "started", started)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register)

        DriftHooks()

        assert boundary.call_count == 0
