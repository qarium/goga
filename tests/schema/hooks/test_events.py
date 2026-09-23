"""Contract and logic tests for the entity declared in
``goga/schema/hooks/CODEMANIFEST`` with ``location: events.py``:

- ``SchemaHooks()`` — the checkpoint surface of the schema domain: the
  staged per-tool delivery of the hard ``schema/amend_cell`` action over
  the platform facade

The delivery runs for real over the platform boundary fixtures of
``tests/hooks/conftest.py`` (re-exported by the zone test package) — the
registry, the registrars, and the delivery execute the actual platform
code; only the installed-packages mapping and the ``sys.modules`` entry of
a fake ``goga_tool_*`` package are pinned.
"""

from __future__ import annotations

import inspect
import typing

import pytest
from goga.schema.hooks import CellFacts, SchemaHooks


def _cell(path: str = "goga/config") -> CellFacts:
    """A minimal authored cell — one type, no usages, no dependencies, leaf.

    Args:
        path: the normalized cell path of the returned facts.

    Returns:
        The authored facts handed to the checkpoint under test.
    """
    return CellFacts(
        path=path,
        description="Owner of the project configuration.",
        types=["ProjectConfig"],
        usages=[],
        dependencies=[],
        children=[],
    )


# --- Contract tests ---


class TestCheckpointContract:
    def test_surface_is_importable_from_the_facade(self) -> None:
        """The entity lives on the zone facade and resolves to ``events.py``."""
        import goga.schema.hooks as facade
        from goga.schema.hooks.events import SchemaHooks as Declared

        assert facade.SchemaHooks is Declared
        assert facade.SchemaHooks is SchemaHooks

        assert "SchemaHooks" in facade.__all__

    def test_constructor_takes_no_arguments(self) -> None:
        """Cheap construction — the surface declares no parameter."""
        assert list(inspect.signature(SchemaHooks).parameters) == []

    def test_amend_cell_carries_the_declared_signature(self) -> None:
        """The checkpoint takes exactly the declared parameter and returns the tools area."""
        parameters = inspect.signature(SchemaHooks.amend_cell).parameters

        assert list(parameters) == ["self", "cell"]
        assert typing.get_type_hints(SchemaHooks.amend_cell) == {
            "cell": CellFacts,
            "return": dict[str, dict[str, object]],
        }


# --- Logic tests: the checkpoint delivery (real platform) ---


class TestAmendCellDelivery:
    def test_amend_cell_commits_buffered_facts(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """One tool, one buffered fact — the composed tools area under the platform identity."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def cover(context: object) -> None:
                context.contribute({"coverage": 3})

            hooks.subscribe("schema", "amend_cell", "cover", cover)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        # The platform derives goga_tool_docs -> docs.
        assert SchemaHooks().amend_cell(cell=_cell()) == {"docs": {"coverage": 3}}

    def test_amend_cell_empty_contribute_commits_nothing(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """An empty mapping buffers but never commits — the key exists iff the merged buffer is non-empty."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})
        payloads: list[dict[str, object]] = [{}]
        views: list[object] = []

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                views.append(context)  # the delivered view — its buffer is inspected after the delivery
                context.contribute(payloads[0])

            hooks.subscribe("schema", "amend_cell", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        assert SchemaHooks().amend_cell(cell=_cell()) == {}  # buffered, merged to nothing, no key
        assert views[0]._pending == [{}]  # type: ignore[attr-defined]  # the empty mapping sits in the buffer

        # The inversion on the same fixture: one written fact opens the key.
        payloads[0] = {"a": 1}

        assert SchemaHooks().amend_cell(cell=_cell()) == {"docs": {"a": 1}}

    def test_contribute_merges_key_wise_later_wins(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Two payloads of one tool — the merged buffer keeps the later write per key."""
        pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute({"a": 1, "b": 2})
                context.contribute({"a": 3})

            hooks.subscribe("schema", "amend_cell", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        assert SchemaHooks().amend_cell(cell=_cell()) == {"docs": {"a": 3, "b": 2}}

    def test_amend_cell_builds_registry_once_per_run(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Two checkpoints on one surface — the package enumeration runs exactly once."""
        boundary = pin_package_environment({"goga_tool_docs": ["docs-dist"]})

        def register(hooks: object) -> None:
            def cover(context: object) -> None:
                context.contribute({"coverage": 3})

            hooks.subscribe("schema", "amend_cell", "cover", cover)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_docs", register_hooks=register)

        surface = SchemaHooks()
        first = surface.amend_cell(cell=_cell(path="goga/config"))
        second = surface.amend_cell(cell=_cell(path="goga/schema"))

        assert boundary.call_count == 1
        assert first == {"docs": {"coverage": 3}}
        assert second == {"docs": {"coverage": 3}}

    def test_amend_cell_crashed_hook_is_hard_failure_naming_cell_path(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A raising hook stops the walk — the error names the hook, the tool, the action, and the cell."""
        pin_package_environment({"goga_tool_boom": ["boom-dist"]})

        def register(hooks: object) -> None:
            def explode(context: object) -> None:
                raise RuntimeError("kaput")

            hooks.subscribe("schema", "amend_cell", "explode", explode)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_boom", register_hooks=register)

        with pytest.raises(
            ValueError,
            match=r"hook explode of tool boom failed on schema\.amend_cell at goga/config: kaput",
        ):
            SchemaHooks().amend_cell(cell=_cell(path="goga/config"))

    @pytest.mark.parametrize(
        "payload",
        [
            {"cfg": {}},  # an empty mapping under a key
            {"cfg": {"deep": {}}},  # an empty mapping deeper under a key
            {1: "x"},  # a non-string key
            {"v": {1, 2}},  # a set — not a JSON value
            {"v": float("nan")},  # a non-finite float
            [("a", 1)],  # a non-mapping payload — never coerced into one
        ],
    )
    def test_amend_cell_structurally_malformed_contribution_is_hard_failure(
        self,
        pin_package_environment,
        install_tool_package,
        payload: object,
    ) -> None:
        """A malformed payload fails the tool commit — never a coercion, never a raw escape."""
        pin_package_environment({"goga_tool_bad": ["bad-dist"]})

        def register(hooks: object) -> None:
            def emit(context: object) -> None:
                context.contribute(payload)  # type: ignore[arg-type]

            hooks.subscribe("schema", "amend_cell", "emit", emit)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_bad", register_hooks=register)

        with pytest.raises(
            ValueError,
            match=r"tool bad failed on schema\.amend_cell at goga/schema: structurally malformed contribution",
        ):
            SchemaHooks().amend_cell(cell=_cell(path="goga/schema"))

    def test_structural_check_runs_on_the_merged_buffer(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """An earlier empty mapping replaced by a later hook of the same tool commits — the merged buffer heals."""
        pin_package_environment({"goga_tool_bad": ["bad-dist"]})

        def register(hooks: object) -> None:
            def first(context: object) -> None:
                context.contribute({"a": {}})

            def second(context: object) -> None:
                context.contribute({"a": {"b": 1}})

            hooks.subscribe("schema", "amend_cell", "first", first)  # type: ignore[attr-defined]
            hooks.subscribe("schema", "amend_cell", "second", second)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_bad", register_hooks=register)

        assert SchemaHooks().amend_cell(cell=_cell(path="goga/schema")) == {"bad": {"a": {"b": 1}}}

    def test_amend_cell_without_subscriptions_returns_empty_mapping(
        self,
        pin_package_environment,
    ) -> None:
        """No subscriptions — the empty tools area, no hook ever called."""
        pin_package_environment({})

        assert SchemaHooks().amend_cell(cell=_cell()) == {}

    def test_construction_enumerates_nothing(self, pin_package_environment) -> None:
        """Cheap construction — the package environment stays unread."""
        boundary = pin_package_environment({"goga_tool_demo": ["demo"]})

        SchemaHooks()

        assert boundary.call_count == 0

    def test_frozen_facts_block_attribute_assignment_and_isolate_tools(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Mutual blindness — one tool's in-place write never reaches another view or the caller.

        Enumeration is alphabetical (``goga_tool_alpha`` before
        ``goga_tool_beta``), so the reading tool observes the state left
        by the mutating tool's in-place list write — which must be
        nothing: every tool reads its own fresh copy of the authored
        facts. The frozen record blocks attribute assignment from the
        hook side, and the caller's instance leaves the delivery
        untouched.
        """
        pin_package_environment({"goga_tool_alpha": ["alpha-dist"], "goga_tool_beta": ["beta-dist"]})
        observed: dict[str, object] = {}

        def register_alpha(hooks: object) -> None:
            def mutate(context: object) -> None:
                try:
                    context.cell.types = ["junk"]  # type: ignore[misc]
                    observed["assignment"] = "assigned"
                except Exception:
                    observed["assignment"] = "blocked"  # FrozenInstanceError subclasses AttributeError
                context.cell.types.append("junk")  # the in-place channel — local to this view

            hooks.subscribe("schema", "amend_cell", "mutating", mutate)  # type: ignore[attr-defined]

        def register_beta(hooks: object) -> None:
            def read(context: object) -> None:
                observed["types"] = list(context.cell.types)

            hooks.subscribe("schema", "amend_cell", "reading", read)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_alpha", register_hooks=register_alpha)
        install_tool_package("goga_tool_beta", register_hooks=register_beta)

        facts = _cell()
        tools = SchemaHooks().amend_cell(cell=facts)

        assert observed["assignment"] == "blocked"
        assert observed["types"] == ["ProjectConfig"]  # the authored list, never alpha's write
        assert facts.types == ["ProjectConfig"]  # the caller's instance untouched
        assert tools == {}  # neither tool contributed a fact
