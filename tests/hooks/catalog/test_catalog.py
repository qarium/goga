"""Contract and logic tests for the entities declared in
``goga/hooks/catalog/CODEMANIFEST`` with ``location: catalog.py``:

- ``Action(domain, name, error_class)`` — one catalog record, a named
  subscription address with its error class
- ``declared_actions()`` — the declared action catalog, the single source of
  known addresses

Supported data only — no mocks: the catalog is maintained data, not
discovery over installed packages.
"""

from __future__ import annotations

import dataclasses
import inspect
import typing

import pytest
from goga.hooks.catalog import Action, declared_actions

# --- Contract tests ---


class TestCatalogContract:
    def test_entities_are_importable_from_the_package_facade(self) -> None:
        """Both entities live on the cell package and its ``__all__`` is exact."""
        import goga.hooks.catalog as cell

        assert cell.Action is Action
        assert cell.declared_actions is declared_actions
        assert cell.__all__ == ["Action", "declared_actions"]

    def test_action_is_a_kw_only_frozen_dataclass(self) -> None:
        """``Action(domain=..., name=..., error_class=...)`` — keyword-only, frozen."""
        action = Action(domain="statuses", name="register_statuses", error_class="soft")

        assert action.domain == "statuses"
        assert action.name == "register_statuses"
        assert action.error_class == "soft"

        assert dataclasses.is_dataclass(Action)
        assert Action.__dataclass_params__.frozen
        assert Action.__dataclass_params__.kw_only

        with pytest.raises(TypeError):
            Action("statuses", "register_statuses", "soft")  # type: ignore[misc]

    def test_action_assignment_raises_frozen_instance_error(self) -> None:
        """A published record is never rewritten."""
        action = Action(domain="statuses", name="register_statuses", error_class="soft")

        with pytest.raises(dataclasses.FrozenInstanceError):
            action.domain = "other"  # type: ignore[misc]

    def test_action_carries_exactly_the_three_declared_fields(self) -> None:
        """No computed properties, no extra state — the record is data only."""
        field_names = [field.name for field in dataclasses.fields(Action)]

        assert field_names == ["domain", "name", "error_class"]

    def test_declared_actions_signature(self) -> None:
        """``declared_actions() -> list[Action]`` — no parameters."""
        parameters = inspect.signature(declared_actions).parameters
        return_hint = typing.get_type_hints(declared_actions)["return"]

        assert list(parameters) == []
        assert return_hint == list[Action]


# --- Logic tests ---


class TestDeclaredActions:
    def test_declared_actions_carries_the_statuses_action(self) -> None:
        """The seed record — the statuses registration action, soft failures."""
        records = {(action.domain, action.name): action for action in declared_actions()}

        assert ("statuses", "register_statuses") in records
        assert records[("statuses", "register_statuses")].error_class == "soft"

    def test_declared_actions_is_deterministic_and_complete(self) -> None:
        """Same records in ``(domain, name)`` order on every call, unfiltered.

        A fresh list per call — mutating a returned list never reaches the
        catalog constant.
        """
        first = declared_actions()
        second = declared_actions()

        assert first == second
        assert first is not second
        assert [(a.domain, a.name) for a in first] == sorted((a.domain, a.name) for a in first)

        first.clear()

        assert declared_actions() == second
        assert first != second

    def test_declared_actions_records_are_well_formed(self) -> None:
        """Non-empty addresses, valid error classes, unique pairs."""
        records = declared_actions()
        pairs = [(action.domain, action.name) for action in records]

        assert all(action.domain for action in records)
        assert all(action.name for action in records)
        assert {action.error_class for action in records} <= {"soft", "hard"}
        assert len(pairs) == len(set(pairs))
