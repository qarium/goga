"""Contract and logic tests for the entities declared in
``goga/contract/hooks/CODEMANIFEST`` with ``location: facts.py``:

- ``CellFacts(path, types)`` — the comparison facts of one cell, the
  per-cell read view delivered to a subscribed hook
- ``TypeFacts(name, signature, properties, methods)`` — the comparison
  facts of one declared type (pure data)
- ``FormFacts(codemanifest, implementation)`` — one compared form (pure
  strings only, an absent counterpart allowed)
- ``MemberFacts(name, form)`` — the compared form of one named member
  (pure data)

Supported data only — no mocks, no filesystem: the records carry the
constructor facts verbatim; the contract command constructs them from
its own comparison values, nothing is read inside. The tests import
from ``goga.contract.hooks.facts`` directly — the facade identity
assertions belong to the facade suite.
"""

from __future__ import annotations

import dataclasses
import typing

import pytest

from tests.conftest import is_kw_only_dataclass


def _form() -> object:
    """One compared form — the declared string with its counterpart."""
    from goga.contract.hooks.facts import FormFacts

    return FormFacts(codemanifest="str", implementation="str")


def _member(name: str = "language") -> object:
    """One compared member — a member name with its compared form."""
    from goga.contract.hooks.facts import FormFacts, MemberFacts

    return MemberFacts(name=name, form=FormFacts(codemanifest="str", implementation="str"))


@pytest.fixture
def facts() -> object:
    """A minimal compared cell — one entity type with one member of each kind."""
    from goga.contract.hooks.facts import CellFacts, FormFacts, MemberFacts, TypeFacts

    return CellFacts(
        path="goga/config",
        types=[
            TypeFacts(
                name="ProjectConfig",
                signature=FormFacts(
                    codemanifest="ProjectConfig(language: str)",
                    implementation="ProjectConfig(language: str)",
                ),
                properties=[
                    MemberFacts(
                        name="language",
                        form=FormFacts(codemanifest="str", implementation="str"),
                    )
                ],
                methods=[
                    MemberFacts(
                        name="reload",
                        form=FormFacts(codemanifest="reload() -> None", implementation=None),
                    )
                ],
            )
        ],
    )


# --- Contract tests ---


class TestFactsContract:
    def test_facts_are_importable_from_the_module(self) -> None:
        """All four names live in ``facts.py`` of the zone."""
        from goga.contract.hooks.facts import CellFacts, FormFacts, MemberFacts, TypeFacts

        assert callable(CellFacts)
        assert callable(FormFacts)
        assert callable(MemberFacts)
        assert callable(TypeFacts)

    def test_cell_facts_is_a_frozen_kw_only_dataclass(self) -> None:
        """Pure frozen data, keyword-only construction."""
        from goga.contract.hooks.facts import CellFacts

        assert dataclasses.is_dataclass(CellFacts)
        assert is_kw_only_dataclass(CellFacts)
        assert CellFacts.__dataclass_params__.frozen

        with pytest.raises(TypeError):
            CellFacts("goga/config", [])  # type: ignore[misc]

    def test_cell_facts_carries_exactly_the_declared_fields(self) -> None:
        """``path, types`` — names, order, all required."""
        from goga.contract.hooks.facts import CellFacts

        assert [field.name for field in dataclasses.fields(CellFacts)] == [
            "path",
            "types",
        ]

        defaults = [(field.name, field.default) for field in dataclasses.fields(CellFacts)]

        assert defaults == [
            ("path", dataclasses.MISSING),
            ("types", dataclasses.MISSING),
        ]

    def test_cell_facts_annotates_the_declared_property_types(self) -> None:
        """The fields carry the contract property types."""
        from goga.contract.hooks.facts import CellFacts, TypeFacts

        hints = typing.get_type_hints(CellFacts)

        assert hints["path"] is str
        assert hints["types"] == list[TypeFacts]

    def test_type_facts_is_a_frozen_kw_only_dataclass(self) -> None:
        """Pure frozen data, keyword-only construction."""
        from goga.contract.hooks.facts import TypeFacts

        assert dataclasses.is_dataclass(TypeFacts)
        assert is_kw_only_dataclass(TypeFacts)
        assert TypeFacts.__dataclass_params__.frozen

        with pytest.raises(TypeError):
            TypeFacts("ProjectConfig", _form(), [], [])  # type: ignore[misc]

    def test_type_facts_carries_exactly_the_declared_fields(self) -> None:
        """``name, signature, properties, methods`` — names, order, all required."""
        from goga.contract.hooks.facts import TypeFacts

        assert [field.name for field in dataclasses.fields(TypeFacts)] == [
            "name",
            "signature",
            "properties",
            "methods",
        ]

        defaults = [(field.name, field.default) for field in dataclasses.fields(TypeFacts)]

        assert defaults == [
            ("name", dataclasses.MISSING),
            ("signature", dataclasses.MISSING),
            ("properties", dataclasses.MISSING),
            ("methods", dataclasses.MISSING),
        ]

    def test_type_facts_annotates_the_declared_property_types(self) -> None:
        """The fields carry the contract property types."""
        from goga.contract.hooks.facts import FormFacts, MemberFacts, TypeFacts

        hints = typing.get_type_hints(TypeFacts)

        assert hints["name"] is str
        assert hints["signature"] is FormFacts
        assert hints["properties"] == list[MemberFacts]
        assert hints["methods"] == list[MemberFacts]

    def test_form_facts_is_a_frozen_kw_only_dataclass(self) -> None:
        """Pure frozen data, keyword-only construction."""
        from goga.contract.hooks.facts import FormFacts

        assert dataclasses.is_dataclass(FormFacts)
        assert is_kw_only_dataclass(FormFacts)
        assert FormFacts.__dataclass_params__.frozen

        with pytest.raises(TypeError):
            FormFacts("()", "()")  # type: ignore[misc]

    def test_form_facts_carries_exactly_the_declared_fields(self) -> None:
        """``codemanifest, implementation`` — names, order, all required."""
        from goga.contract.hooks.facts import FormFacts

        assert [field.name for field in dataclasses.fields(FormFacts)] == [
            "codemanifest",
            "implementation",
        ]

        defaults = [(field.name, field.default) for field in dataclasses.fields(FormFacts)]

        assert defaults == [
            ("codemanifest", dataclasses.MISSING),
            ("implementation", dataclasses.MISSING),
        ]

    def test_form_facts_annotates_the_declared_property_types(self) -> None:
        """The fields carry the contract property types."""
        from goga.contract.hooks.facts import FormFacts

        hints = typing.get_type_hints(FormFacts)

        assert hints["codemanifest"] is str
        assert hints["implementation"] == str | None

    def test_member_facts_is_a_frozen_kw_only_dataclass(self) -> None:
        """Pure frozen data, keyword-only construction."""
        from goga.contract.hooks.facts import MemberFacts

        assert dataclasses.is_dataclass(MemberFacts)
        assert is_kw_only_dataclass(MemberFacts)
        assert MemberFacts.__dataclass_params__.frozen

        with pytest.raises(TypeError):
            MemberFacts("language", _form())  # type: ignore[misc]

    def test_member_facts_carries_exactly_the_declared_fields(self) -> None:
        """``name, form`` — names, order, all required."""
        from goga.contract.hooks.facts import MemberFacts

        assert [field.name for field in dataclasses.fields(MemberFacts)] == [
            "name",
            "form",
        ]

        defaults = [(field.name, field.default) for field in dataclasses.fields(MemberFacts)]

        assert defaults == [
            ("name", dataclasses.MISSING),
            ("form", dataclasses.MISSING),
        ]

    def test_member_facts_annotates_the_declared_property_types(self) -> None:
        """The fields carry the contract property types."""
        from goga.contract.hooks.facts import FormFacts, MemberFacts

        hints = typing.get_type_hints(MemberFacts)

        assert hints["name"] is str
        assert hints["form"] is FormFacts


# --- Logic tests: pure facts ---


class TestFactsValues:
    def test_facts_records_are_frozen_pure_data(self) -> None:
        """Concrete values round-trip verbatim; assignment is blocked."""
        from goga.contract.hooks.facts import (
            CellFacts,
            FormFacts,
            MemberFacts,
            TypeFacts,
        )

        form = FormFacts(codemanifest="reload() -> None", implementation=None)
        member = MemberFacts(name="reload", form=form)
        type_facts = TypeFacts(
            name="ProjectConfig",
            signature=FormFacts(codemanifest="()", implementation="()"),
            properties=[],
            methods=[member],
        )
        facts = CellFacts(path="goga/x", types=[type_facts])

        assert facts.path == "goga/x"
        assert facts.types == [type_facts]
        assert member.name == "reload"
        assert member.form is form
        assert form.codemanifest == "reload() -> None"
        assert form.implementation is None

        with pytest.raises(dataclasses.FrozenInstanceError):
            facts.path = "other"  # type: ignore[misc]

    def test_entity_type_carries_its_member_lists(self, facts: object) -> None:
        """An entity node carries its property and method members."""
        entity = facts.types[0]

        assert entity.name == "ProjectConfig"
        assert [member.name for member in entity.properties] == ["language"]
        assert [member.name for member in entity.methods] == ["reload"]

    def test_routine_shape_carries_empty_member_lists(self) -> None:
        """A routine carries only its signature — both member lists empty."""
        from goga.contract.hooks.facts import FormFacts, TypeFacts

        routine = TypeFacts(
            name="load_project_config",
            signature=FormFacts(
                codemanifest="load_project_config() -> config: ProjectConfig",
                implementation="load_project_config() -> config: ProjectConfig",
            ),
            properties=[],
            methods=[],
        )

        assert routine.properties == []
        assert routine.methods == []

    def test_cell_without_types_is_constructible(self) -> None:
        """The empty-body cell — ``types=[]`` is a legal comparison shape."""
        from goga.contract.hooks.facts import CellFacts

        facts = CellFacts(path="goga/empty", types=[])

        assert facts.types == []
        assert facts == CellFacts(path="goga/empty", types=[])
