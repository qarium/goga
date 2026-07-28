# tests/usages/test_status.py — contract and logic tests for the status domain

import dataclasses
import importlib
import inspect
from enum import Enum
from pathlib import Path
from unittest import mock

import pytest
from goga.usages.status import (
    DepStatus,
    FolderStatus,
    UsageState,
    UsageStatusReport,
    status,
)
from goga.usages.status import models as status_models

# Resolve the inner ``status.py`` submodule via importlib. The facade
# ``goga.usages.status`` re-exports the ``status`` function, which shadows the
# submodule attribute in the package ``__dict__``. Holding a direct reference to
# the module makes ``mock.patch.object`` patch the lookup site the orchestrator
# uses (``compute_dep_status`` imported into ``status.py``'s namespace), uniformly
# across Python versions — mirrors the pattern in ``test_integration.py``.
_status_mod = importlib.import_module("goga.usages.status.status")

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
        assert isinstance(inspect.getattr_static(UsageStatusReport, "exit_code"), property)

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
        deps = [DepStatus(group="g", dep=f"d{i}", state=state, folders=[]) for i, state in enumerate(states)]
        assert UsageStatusReport(deps=deps).exit_code == expected


# --- contract tests: status orchestrator entry point ---


class TestStatusContract:
    def test_status_importable_from_facade_and_submodule(self):
        """status is importable from the facade and is the same object as the submodule def."""
        from goga.usages.status import status as facade_status
        from goga.usages.status.status import status as mod_status

        assert callable(facade_status)
        assert facade_status is mod_status

    def test_status_signature(self):
        """status has signature (group: str|None=None, dep: str|None=None) -> UsageStatusReport."""
        sig = inspect.signature(status)
        params = sig.parameters
        assert list(params) == ["group", "dep"]
        assert params["group"].default is None
        assert params["group"].annotation == str | None
        assert params["dep"].default is None
        assert params["dep"].annotation == str | None
        assert sig.return_annotation is UsageStatusReport


# --- logic tests: status orchestration ---


class TestStatusLogic:
    @pytest.mark.parametrize("block", [None, "usages: {}"])
    def test_status_empty_usages_returns_empty_report(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        write_config,
        block,
    ):
        """An absent or empty usages section yields an empty report; no dep is checked."""
        write_config(block)
        monkeypatch.chdir(tmp_path)

        with mock.patch.object(_status_mod, "compute_dep_status") as compute_mock:
            report = status()

        assert report.deps == []
        assert report.exit_code == 0
        compute_mock.assert_not_called()

    def test_status_dep_new_when_target_absent(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        write_config,
    ):
        """A declared dep with no on-disk target is `new`; compare is not invoked."""
        write_config("usages:\n  libs:\n    click:\n      git: https://x/click.git\n")
        monkeypatch.chdir(tmp_path)

        with mock.patch.object(_status_mod, "compute_dep_status") as compute_mock:
            report = status()

        assert len(report.deps) == 1
        dep_status = report.deps[0]
        assert dep_status.group == "libs"
        assert dep_status.dep == "click"
        assert dep_status.state is UsageState.new
        assert dep_status.folders == []
        assert report.exit_code == 1
        compute_mock.assert_not_called()

    def test_status_propagates_config_load_error(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ):
        """A missing config.yml makes status fail-loud with FileNotFoundError."""
        monkeypatch.chdir(tmp_path)

        with pytest.raises(FileNotFoundError):
            status()

    def test_status_filters_group_and_dep(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        write_config,
    ):
        """group/dep filters narrow the check; non-matching is a skip, not an error."""
        write_config(
            "usages:\n"
            "  libs:\n"
            "    click:\n"
            "      git: https://x/click.git\n"
            "    cli:\n"
            "      git: https://x/cli.git\n"
            "  tools:\n"
            "    cli:\n"
            "      git: https://y/cli.git\n"
        )
        monkeypatch.chdir(tmp_path)

        usages_root = tmp_path / ".goga" / "usages"
        for group_name, dep_name in [("libs", "click"), ("libs", "cli"), ("tools", "cli")]:
            (usages_root / group_name / dep_name).mkdir(parents=True)

        def fake_compute(group_name, dep_name, depcfg, target):
            return DepStatus(
                group=group_name,
                dep=dep_name,
                state=UsageState.up_to_date,
                folders=[],
            )

        with mock.patch.object(_status_mod, "compute_dep_status", side_effect=fake_compute):
            r_libs = status(group="libs")
            r_dep_cli = status(dep="cli")
            r_tools_cli = status(group="tools", dep="cli")
            r_missing = status(group="nonexistent")

        def checked(report):
            return {(d.group, d.dep) for d in report.deps}

        assert checked(r_libs) == {("libs", "click"), ("libs", "cli")}
        assert checked(r_dep_cli) == {("libs", "cli"), ("tools", "cli")}
        assert checked(r_tools_cli) == {("tools", "cli")}
        assert r_missing.deps == []
        assert r_missing.exit_code == 0

    def test_status_clone_failure_yields_error_dep_best_effort(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        write_config,
    ):
        """A per-dep compare failure is best-effort: error dep + other dep still checked."""
        write_config(
            "usages:\n  libs:\n    good:\n      git: https://x/good.git\n    bad:\n      git: https://x/bad.git\n"
        )
        monkeypatch.chdir(tmp_path)

        usages_root = tmp_path / ".goga" / "usages"
        (usages_root / "libs" / "good").mkdir(parents=True)
        (usages_root / "libs" / "bad").mkdir(parents=True)

        def fake_compute(group_name, dep_name, depcfg, target):
            if dep_name == "bad":
                raise Exception("secret https://x/bad.git token Traceback (most recent call last)")
            return DepStatus(
                group=group_name,
                dep=dep_name,
                state=UsageState.up_to_date,
                folders=[],
            )

        with mock.patch.object(_status_mod, "compute_dep_status", side_effect=fake_compute):
            report = status()

        assert report.exit_code == 1
        by_dep = {d.dep: d for d in report.deps}
        assert by_dep["good"].state is UsageState.up_to_date
        assert by_dep["bad"].state is UsageState.error
        assert by_dep["bad"].error == "failed to check usages status for libs/bad"
        assert by_dep["bad"].folders == []
        # credential-free: the raised message's secret/URL/traceback must NOT leak
        # into the static error string
        assert "secret" not in by_dep["bad"].error
        assert "https" not in by_dep["bad"].error
        assert "Traceback" not in by_dep["bad"].error
