"""Contract and logic tests for the comparison core of ``goga/drift``.

Entities under test (declared in ``goga/drift/CODEMANIFEST`` with
``location: compare.py``):

- ``DriftEntry(kind, cell, types)`` — the flat report record.
- ``compare_views(schema_tree, codegraph_tree) -> list[DriftEntry]`` — the
  name-level comparison of the two complete views.
- ``scope_entries(entries, schema_tree, codegraph_tree) -> list[DriftEntry]``
  — the survival scoping over the filtered views.

Pure logic over records — no filesystem, no mocks.
"""

from __future__ import annotations

import copy
import dataclasses
import inspect
import typing

import pytest
from goga.codegraph.facts import CodegraphNode
from goga.schema.hooks import SchemaNode

from tests.conftest import is_kw_only_dataclass


def _schema_node(
    path: str,
    types: list[str],
    children: list[SchemaNode] | None = None,
) -> SchemaNode:
    """Build a minimal schema node carrying a path, types, and children."""
    return SchemaNode(
        path=path,
        description="",
        types=list(types),
        usages=[],
        dependencies=[],
        children=list(children or []),
    )


def _codegraph_node(
    cell: str,
    types: list[str],
    children: list[CodegraphNode] | None = None,
) -> CodegraphNode:
    """Build a minimal codegraph node carrying a cell, types, and children."""
    return CodegraphNode(cell=cell, types=list(types), children=list(children or []))


class TestCompareCore:
    """Facade and call contract of the comparison core."""

    def test_drift_entry_importable_from_facade(self) -> None:
        """``DriftEntry`` is importable from the drift cell facade."""
        from goga.drift import DriftEntry  # noqa: F401

    def test_compare_views_importable_from_facade(self) -> None:
        """``compare_views`` is importable from the drift cell facade."""
        from goga.drift import compare_views  # noqa: F401

    def test_scope_entries_importable_from_facade(self) -> None:
        """``scope_entries`` is importable from the drift cell facade."""
        from goga.drift import scope_entries  # noqa: F401

    def test_facade_all_exposes_the_landed_names(self) -> None:
        """The facade ``__all__`` exposes the final four names of the cell."""
        import goga.drift

        assert goga.drift.__all__ == ["DriftEntry", "compare_views", "drift", "scope_entries"]

    def test_kind_constants_pin_the_serialized_literals(self) -> None:
        """The kind constants carry the serialized contract literals."""
        from goga.drift.compare import CODEGRAPH_ONLY, SCHEMA_ONLY

        assert SCHEMA_ONLY == "schema_only"
        assert CODEGRAPH_ONLY == "codegraph_only"

    def test_compare_views_has_correct_signature(self) -> None:
        """``compare_views`` declares the two view parameters."""
        from goga.drift import compare_views

        sig = inspect.signature(compare_views)
        params = list(sig.parameters.keys())

        assert params == ["schema_tree", "codegraph_tree"]

    def test_compare_views_param_and_return_types(self) -> None:
        """``compare_views`` types both views and the entry list it returns."""
        from goga.drift import DriftEntry, compare_views

        hints = typing.get_type_hints(compare_views)

        assert hints["schema_tree"] == list[SchemaNode]
        assert hints["codegraph_tree"] == list[CodegraphNode]
        assert hints["return"] == list[DriftEntry]

    def test_scope_entries_has_correct_signature(self) -> None:
        """``scope_entries`` declares the entries and the two filtered views."""
        from goga.drift import scope_entries

        sig = inspect.signature(scope_entries)
        params = list(sig.parameters.keys())

        assert params == ["entries", "schema_tree", "codegraph_tree"]

    def test_scope_entries_param_and_return_types(self) -> None:
        """``scope_entries`` types the entries, both views, and the report."""
        from goga.drift import DriftEntry, scope_entries

        hints = typing.get_type_hints(scope_entries)

        assert hints["entries"] == list[DriftEntry]
        assert hints["schema_tree"] == list[SchemaNode]
        assert hints["codegraph_tree"] == list[CodegraphNode]
        assert hints["return"] == list[DriftEntry]


class TestCompareViews:
    """Design scenarios of the name-level comparison of the two complete views."""

    def test_compare_views_reports_all_four_discrepancy_kinds(self) -> None:
        """Cell-level drift in both directions plus type-level drift in both directions."""
        from goga.drift import compare_views

        schema_tree = [
            _schema_node("lib", ["thing"]),
            _schema_node("mix", ["run", "stale"]),
            _schema_node("ghost", ["phantom"]),
        ]
        codegraph_tree = [
            _codegraph_node("lib", ["thing"]),
            _codegraph_node("mix", ["run", "helper2"]),
            _codegraph_node("extra", ["helper"]),
        ]

        entries = compare_views(schema_tree, codegraph_tree)

        assert [(entry.kind, entry.cell, entry.types) for entry in entries] == [
            ("codegraph_only", "extra", None),
            ("schema_only", "ghost", None),
            ("codegraph_only", "mix", ["helper2"]),
            ("schema_only", "mix", ["stale"]),
        ]

    def test_compare_views_agreeing_views_yield_empty_list(self) -> None:
        """Identical single-cell views produce no entries."""
        from goga.drift import compare_views

        schema_tree = [_schema_node("lib", ["thing"])]
        codegraph_tree = [_codegraph_node("lib", ["thing"])]

        assert compare_views(schema_tree, codegraph_tree) == []

    def test_compare_views_empty_views_yield_empty_list(self) -> None:
        """Two empty views agree — the report is empty."""
        from goga.drift import compare_views

        assert compare_views([], []) == []

    def test_compare_views_collects_nested_children(self) -> None:
        """Drift on a nested cell surfaces with the nested path — root-only indexing would miss it."""
        from goga.drift import compare_views

        schema_tree = [_schema_node("a", ["root"], [_schema_node("a/b", ["run", "stale"])])]
        codegraph_tree = [_codegraph_node("a", ["root"], [_codegraph_node("a/b", ["run"])])]

        entries = compare_views(schema_tree, codegraph_tree)

        assert len(entries) == 1
        assert entries[0].cell == "a/b"
        assert (entries[0].kind, entries[0].types) == ("schema_only", ["stale"])

    def test_compare_views_pure_inputs_unmutated(self) -> None:
        """Neither view tree is modified by the comparison."""
        from goga.drift import compare_views

        schema_tree = [
            _schema_node("mix", ["run", "stale"], [_schema_node("mix/inner", ["one"])]),
        ]
        codegraph_tree = [_codegraph_node("mix", ["run", "helper2"])]
        schema_copy = copy.deepcopy(schema_tree)
        codegraph_copy = copy.deepcopy(codegraph_tree)

        compare_views(schema_tree, codegraph_tree)

        assert schema_tree == schema_copy
        assert codegraph_tree == codegraph_copy

    def test_compare_views_cell_level_never_coexists_with_type_level(self) -> None:
        """A cell present in one view only yields a single cell-level entry with ``types=None``."""
        from goga.drift import compare_views

        schema_tree = [_schema_node("ghost", ["phantom"])]
        codegraph_tree = [_codegraph_node("mix", ["run"])]

        entries = compare_views(schema_tree, codegraph_tree)

        ghost_entries = [entry for entry in entries if entry.cell == "ghost"]
        assert len(ghost_entries) == 1
        assert ghost_entries[0].types is None


class TestScopeEntries:
    """Design scenarios of the survival scoping over the filtered views."""

    def test_scope_entries_keeps_entry_surviving_in_one_view_only(self) -> None:
        """An entry survives when its cell survives in either filtered view — the union."""
        from goga.drift import DriftEntry, scope_entries

        entries = [DriftEntry(kind="schema_only", cell="mix", types=None)]

        report = scope_entries(entries, [], [_codegraph_node("mix", ["run"])])

        assert report == entries

    def test_scope_entries_preserves_input_order(self) -> None:
        """Surviving entries keep the input order — no re-sorting."""
        from goga.drift import DriftEntry, scope_entries

        entries = [
            DriftEntry(kind="schema_only", cell="zeta", types=None),
            DriftEntry(kind="codegraph_only", cell="alpha", types=["x"]),
        ]

        report = scope_entries(
            entries,
            [_schema_node("alpha", ["y"])],
            [_codegraph_node("zeta", ["z"])],
        )

        assert report == entries

    def test_scope_entries_empty_filtered_views_drop_everything(self) -> None:
        """No surviving paths — every entry is dropped."""
        from goga.drift import DriftEntry, scope_entries

        entries = [DriftEntry(kind="schema_only", cell="mix", types=None)]

        assert scope_entries(entries, [], []) == []


class TestDriftEntry:
    """Design scenario: the record vocabulary of the report."""

    def test_drift_entry_is_frozen_kw_only_record(self) -> None:
        """Positional construction, mutation, and source-list aliasing all fail."""
        from goga.drift import DriftEntry

        with pytest.raises(TypeError):
            DriftEntry("schema_only", "mix", None)

        entry = DriftEntry(kind="schema_only", cell="mix", types=["stale"])

        with pytest.raises(dataclasses.FrozenInstanceError):
            entry.kind = "codegraph_only"

        source = ["stale"]
        entry = DriftEntry(kind="schema_only", cell="mix", types=source)
        source.append("extra")

        assert entry.types == ["stale"]


class TestDriftEntryToolsField:
    """The committed-overlay field of the report record — the codegraph mirror."""

    def test_tools_field_declared_after_types(self) -> None:
        """``DriftEntry`` gains exactly the ``tools`` field with the overlay shape."""
        from goga.drift import DriftEntry

        field_names = [item.name for item in dataclasses.fields(DriftEntry)]

        assert field_names == ["kind", "cell", "types", "tools"]

        tools_field = dataclasses.fields(DriftEntry)[-1]

        assert DriftEntry.__annotations__["tools"] == "dict[str, dict[str, object]]"
        assert tools_field.default_factory is dict

        assert DriftEntry.__dataclass_params__.frozen is True
        assert is_kw_only_dataclass(DriftEntry)

    def test_drift_entry_carries_the_tools_default(self) -> None:
        """The overlay defaults empty; an explicit overlay is kept verbatim; the record stays frozen."""
        from goga.drift import DriftEntry

        assert DriftEntry(kind="schema_only", cell="a").tools == {}

        entry = DriftEntry(kind="schema_only", cell="a", tools={"t": {"f": 1}})

        assert entry.tools == {"t": {"f": 1}}

        with pytest.raises(dataclasses.FrozenInstanceError):
            entry.tools = {}  # type: ignore[misc]
