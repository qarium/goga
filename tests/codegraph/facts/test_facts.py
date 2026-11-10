"""Contract and logic tests for the six immutable records of ``goga/codegraph/facts``.

Records under test (declared in ``goga/codegraph/facts/CODEMANIFEST`` with
``location: facts.py``):

- ``Declaration(path, name, is_public)`` — one named code declaration
- ``ImportRef(source, specifier, names, is_relative, is_wildcard)`` — one import or usage
- ``FileFacts(path, declarations, imports, exports, module)`` — one file's analysis result
- ``Unit(path, files, facade, is_cell)`` — one language unit, a candidate cell
- ``CellLink(source, target, types)`` — one resolved reference between two units
- ``CodegraphNode(cell, types, dependencies, children, tools)`` — one output-tree node

Pure data records — no mocks, no filesystem: construction semantics only.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest
from goga.codegraph.facts import (
    CellLink,
    CodegraphNode,
    Declaration,
    FileFacts,
    ImportRef,
    Unit,
)

from tests.conftest import is_kw_only_dataclass

_RECORD_NAMES = ("CellLink", "CodegraphNode", "Declaration", "FileFacts", "ImportRef", "Unit")
_RECORDS = (CellLink, CodegraphNode, Declaration, FileFacts, ImportRef, Unit)


class TestFactsRecords:
    """Facade and record contract of the facts vocabulary."""

    def test_facade_imports_all_six_records(self) -> None:
        """Every record name is importable from the cell facade."""
        import goga.codegraph.facts as facts_module

        for name in _RECORD_NAMES:
            assert getattr(facts_module, name) is not None

    def test_facade_all_equals_sorted_six_names(self) -> None:
        """``__all__`` is exactly the sorted six record names."""
        import goga.codegraph.facts as facts_module

        assert facts_module.__all__ == list(_RECORD_NAMES)

    def test_every_record_is_a_frozen_kw_only_dataclass(self) -> None:
        """All six are frozen keyword-only dataclasses."""
        for cls in _RECORDS:
            assert dataclasses.is_dataclass(cls)
            assert cls.__dataclass_params__.frozen is True
            assert is_kw_only_dataclass(cls)

    def test_declaration_constructs_with_keywords(self) -> None:
        """The CODEMANIFEST signature example constructs successfully."""
        record = Declaration(path=Path("a"), name="x", is_public=False)

        assert record.path == Path("a")
        assert record.name == "x"
        assert record.is_public is False

    def test_records_default_to_empty_values(self) -> None:
        """Every field has an empty default per the conventions."""
        assert Declaration() == Declaration(path=Path(), name="", is_public=False)

        ref = ImportRef()

        assert ref == ImportRef(source=Path(), specifier="", names=[], is_relative=False, is_wildcard=False)

        facts = FileFacts()

        assert facts == FileFacts(path=Path(), declarations=[], imports=[], exports=[], module="")

        unit = Unit()

        assert unit == Unit(path=Path(), files=[], facade=[], is_cell=False)

        link = CellLink()

        assert link == CellLink(source=Path(), target=Path(), types=[])

        node = CodegraphNode()

        assert node == CodegraphNode(cell="", types=[], dependencies={}, children=[])

    def test_facts_records_frozen_kw_only(self) -> None:
        """Immutability contract: kw-only construction, frozen fields, defensive copies.

        ``Unit(path=...)`` with only some keywords succeeds (empty defaults);
        positional construction is what kw_only forbids — it raises TypeError.
        Frozen forbids field reassignment, not list mutation: the construction-time
        copy guards caller-list aliasing only.
        """
        unit = Unit(path=Path("a"), files=[], facade=["X"], is_cell=True)

        assert unit.facade == ["X"]

        unit.facade.append("Y")

        assert unit.facade == ["X", "Y"]

        with pytest.raises(TypeError):
            Unit(Path("a"))  # type: ignore[misc]

        record = Declaration(path=Path("a"), name="x", is_public=False)

        with pytest.raises(dataclasses.FrozenInstanceError):
            record.is_public = True  # type: ignore[misc]

        source_list: list[ImportRef] = []
        facts = FileFacts(
            path=Path("a"),
            declarations=[],
            imports=source_list,
            exports=[],
            module="",
        )
        source_list.append(ImportRef(source=Path("a")))

        assert len(facts.imports) == 0

        assert dataclasses.is_dataclass(Unit)
        assert Unit.__dataclass_params__.frozen is True

    def test_sequence_fields_are_copied_on_construction(self) -> None:
        """No record aliases a caller-owned list, dict, or nested node list."""
        files = [Path("a.py")]
        facade = ["X"]
        unit = Unit(path=Path("a"), files=files, facade=facade, is_cell=True)
        files.append(Path("b.py"))
        facade.append("Y")

        assert unit.files == [Path("a.py")]
        assert unit.facade == ["X"]

        types = ["B", "A"]
        link = CellLink(source=Path("a"), target=Path("b"), types=types)
        types.append("C")

        assert link.types == ["B", "A"]

        child = CodegraphNode(cell="child")
        dependencies = {"b": ["Y"]}
        node = CodegraphNode(cell="root", types=["T"], dependencies=dependencies, children=[child])
        dependencies["c"] = ["Z"]

        assert node.dependencies == {"b": ["Y"]}
        assert [c.cell for c in node.children] == ["child"]


class TestCodegraphNodeToolsField:
    """The committed-overlay field of the output record."""

    def test_tools_field_declared_after_children(self) -> None:
        """``CodegraphNode`` gains exactly the ``tools`` field with the overlay shape."""
        field_names = [item.name for item in dataclasses.fields(CodegraphNode)]

        assert field_names == ["cell", "types", "dependencies", "children", "tools"]

        tools_field = dataclasses.fields(CodegraphNode)[-1]

        assert CodegraphNode.__annotations__["tools"] == "dict[str, dict[str, object]]"
        assert tools_field.default_factory is dict

        assert CodegraphNode.__dataclass_params__.frozen is True
        assert is_kw_only_dataclass(CodegraphNode)

    def test_codegraph_node_carries_the_tools_default(self) -> None:
        """The overlay defaults empty; an explicit overlay is kept verbatim."""
        assert CodegraphNode(cell="a").tools == {}

        node = CodegraphNode(cell="a", tools={"t": {"f": 1}})

        assert node.tools == {"t": {"f": 1}}

    def test_tools_assignment_blocked_on_the_frozen_record(self) -> None:
        """``tools`` reassignment raises FrozenInstanceError — an AttributeError."""
        node = CodegraphNode(cell="a")

        with pytest.raises(dataclasses.FrozenInstanceError):
            node.tools = {}  # type: ignore[misc]
