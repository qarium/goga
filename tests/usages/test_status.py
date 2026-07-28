# tests/usages/test_status.py — contract and logic tests for the status domain

import dataclasses
import inspect
from enum import Enum

import pytest
from goga.usages.status import (
    DepStatus,
    FolderStatus,
    UsageState,
    UsageStatusReport,
)
from goga.usages.status import models as status_models

# --- contract tests: data models ---


class TestStatusModels:
    def test_models_importable_from_facade(self):
        """The four model entities are importable from the status package facade."""
        assert UsageState is status_models.UsageState
        assert FolderStatus is status_models.FolderStatus
        assert DepStatus is status_models.DepStatus
        assert UsageStatusReport is status_models.UsageStatusReport

    def test_usage_state_is_enum(self):
        """UsageState is implemented as enum.Enum (lint-accepted fixed value set)."""
        assert issubclass(UsageState, Enum)

    def test_usage_state_members_and_display_values(self):
        """UsageState has exactly the four members with the display strings the renderer uses."""
        assert {m.name for m in UsageState} == {
            "new",
            "up_to_date",
            "out_of_date",
            "error",
        }
        assert UsageState.new.value == "new"
        assert UsageState.up_to_date.value == "up to date"
        assert UsageState.out_of_date.value == "out of date"
        assert UsageState.error.value == "error"

    def test_dataclasses_construct_kw_only(self):
        """The three dataclasses accept keyword arguments only."""
        folder = FolderStatus(path="docs", state=UsageState.up_to_date)
        dep = DepStatus(group="libs", dep="click", state=UsageState.new, folders=[folder])
        report = UsageStatusReport(deps=[dep])
        assert dep.error is None
        assert report.deps == [dep]

    def test_dataclasses_kw_only_rejects_positional(self):
        """kw_only dataclasses reject positional construction."""
        with pytest.raises(TypeError):
            FolderStatus("docs", UsageState.up_to_date)

    def test_dataclasses_are_frozen(self):
        """Frozen dataclasses raise FrozenInstanceError on attribute mutation."""
        folder = FolderStatus(path="docs", state=UsageState.up_to_date)
        dep = DepStatus(group="libs", dep="click", state=UsageState.new, folders=[])
        with pytest.raises(dataclasses.FrozenInstanceError):
            folder.path = "other"
        with pytest.raises(dataclasses.FrozenInstanceError):
            dep.state = UsageState.error

    def test_dep_status_error_defaults_to_none(self):
        """DepStatus.error defaults to None when omitted."""
        dep = DepStatus(group="libs", dep="click", state=UsageState.new, folders=[])
        assert dep.error is None

    def test_exit_code_is_property_not_field(self):
        """UsageStatusReport.exit_code is a computed @property, never a stored field."""
        assert "exit_code" not in {f.name for f in dataclasses.fields(UsageStatusReport)}
        assert isinstance(
            inspect.getattr_static(UsageStatusReport, "exit_code"), property
        )

    @pytest.mark.parametrize(
        ("states", "expected"),
        [
            ([], 0),
            ([UsageState.up_to_date], 0),
            ([UsageState.up_to_date, UsageState.up_to_date], 0),
            ([UsageState.new], 1),
            ([UsageState.out_of_date], 1),
            ([UsageState.error], 1),
            ([UsageState.up_to_date, UsageState.new], 1),
            ([UsageState.out_of_date, UsageState.error], 1),
            ([UsageState.new, UsageState.up_to_date, UsageState.error], 1),
        ],
    )
    def test_exit_code_property_semantics(self, states, expected):
        """exit_code is 0 iff every dep is up_to_date; empty deps yields 0."""
        deps = [
            DepStatus(group="g", dep=f"d{i}", state=state, folders=[])
            for i, state in enumerate(states)
        ]
        assert UsageStatusReport(deps=deps).exit_code == expected
