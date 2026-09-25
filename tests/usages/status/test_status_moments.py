"""Contract and logic tests for the run-level moments of the status operation.

The operation under test runs for real against the platform boundary
fixtures re-exported by the usages suites — the fake ``goga_tool_*``
package imitates the consumer practice's subscribe sketch, appending every
delivered ``usages`` context to a capture owned by the test. The delivered
contexts are the platform's delivery views (the proxy hides the context
class — no type to introspect), so the capture records the emission
address alongside the view and each test projects it onto the address it
asserts.
"""

from __future__ import annotations

import importlib
import inspect
import logging
from pathlib import Path
from unittest import mock

import pytest
from goga.usages import status as facade_status
from goga.usages.hooks import ChangeVerdict, Completion, DepDrift, DriftVerdict, FileChange
from goga.usages.status import (
    DepStatus,
    EntryChange,
    EntryKind,
    EntryStatus,
    UsageState,
    UsageStatusReport,
    status,
)

from tests.usages.conftest import _of

# Resolve the inner ``status.py`` submodule via importlib. The facade
# ``goga.usages.status`` re-exports the ``status`` function, which shadows the
# submodule attribute in the package ``__dict__``. On Python 3.10 a dotted
# ``mock.patch`` target resolves through sequential ``getattr`` and finds the
# function where it expects the submodule; holding a direct reference to the
# module makes ``mock.patch.object`` work uniformly across Python versions —
# the pattern ``test_status.py`` documents.
_status_mod = importlib.import_module("goga.usages.status.status")

# --- helpers ---


def _write_config(tmp_path: Path, usages_block: str) -> None:
    """Write a ``.goga/config.yml`` carrying ``usages_block`` under ``tmp_path``.

    The parametrized crash test's argument budget is spent on its two case
    parameters, so it writes its config through this module-level helper (the
    pattern of the neighboring ``test_config_checkpoint.py``) instead of the
    shared ``write_config`` fixture; the autouse cwd isolation already points
    the run at ``tmp_path``.
    """
    config_dir = tmp_path / ".goga"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "config.yml").write_text(f"language: python\n{usages_block}")


_CLICK_DEP_BLOCK = "usages:\n  libs:\n    click:\n      git: https://x/click.git\n      ref: main\n"

_CLICK_COMMON_BLOCK = (
    "usages:\n"
    "  libs:\n"
    "    click:\n"
    "      git: https://x/click.git\n"
    "      ref: main\n"
    "    common:\n"
    "      git: https://x/common.git\n"
    "      ref: main\n"
)


# --- contract tests ---


class TestStatusMomentsContract:
    def test_signature_is_unchanged(self) -> None:
        """Signature stays status(group: str | None = None, dep: str | None = None) -> report."""
        sig = inspect.signature(status)
        params = list(sig.parameters)
        assert params == ["group", "dep"]
        assert sig.parameters["group"].annotation == str | None
        assert sig.parameters["group"].default is None
        assert sig.parameters["dep"].annotation == str | None
        assert sig.parameters["dep"].default is None
        assert sig.return_annotation is UsageStatusReport

    def test_importable_from_goga_usages_status(self) -> None:
        """status is importable from goga.usages.status."""
        assert callable(status)

    def test_importable_from_facade(self) -> None:
        """status is the same object exported by the goga.usages facade."""
        assert status is facade_status


# --- logic tests — the real operation over the boundary fixtures ---


class TestStatusMoments:
    def test_status_emits_the_changed_set_with_the_file_projection(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        write_config,
        recorder,
    ) -> None:
        """An out-of-date run projects the per-file changes into the changed set.

        Files only (the ``docs`` directory node is dropped), unchanged files
        dropped, the verdict mapped, and the path-sorted entry order
        preserved — the riskiest new logic pinned with one exhaustive
        expected value.
        """
        write_config(_CLICK_DEP_BLOCK)
        (tmp_path / ".goga" / "usages" / "libs" / "click").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        dep_status = DepStatus(
            group="libs",
            dep="click",
            state=UsageState.out_of_date,
            entries=[
                EntryStatus(path="b.md", kind=EntryKind.file, change=EntryChange.unchanged),
                EntryStatus(path="c.md", kind=EntryKind.file, change=EntryChange.removed),
                EntryStatus(path="docs", kind=EntryKind.dir, change=EntryChange.modified),
                EntryStatus(path="docs/a.md", kind=EntryKind.file, change=EntryChange.added),
            ],
        )

        with mock.patch.object(_status_mod, "compute_dep_status", return_value=dep_status):
            report = status(group="libs")

        started = _of(recorder, "status_started")
        completed = _of(recorder, "status_completed")

        assert len(started) == 1
        assert started[0].moment.operation == "status"
        assert started[0].moment.group == "libs"
        assert len(completed) == 1
        assert completed[0].changed == [
            DepDrift(
                group="libs",
                dep="click",
                verdict=DriftVerdict.out_of_date,
                changes=[
                    FileChange(path="c.md", change=ChangeVerdict.removed),
                    FileChange(path="docs/a.md", change=ChangeVerdict.added),
                ],
            )
        ]
        assert completed[0].success is False
        assert report.deps[0].state is UsageState.out_of_date  # the report is unchanged in shape

    def test_status_up_to_date_run_has_an_empty_changed_set_and_success(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        write_config,
        recorder,
    ) -> None:
        """An up-to-date run records no drift: the empty changed set reads as success."""
        write_config(_CLICK_DEP_BLOCK)
        (tmp_path / ".goga" / "usages" / "libs" / "click").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        dep_status = DepStatus(
            group="libs",
            dep="click",
            state=UsageState.up_to_date,
            entries=[EntryStatus(path="b.md", kind=EntryKind.file, change=EntryChange.unchanged)],
        )

        with mock.patch.object(_status_mod, "compute_dep_status", return_value=dep_status):
            report = status()

        completed = _of(recorder, "status_completed")

        assert completed[0].changed == []
        assert completed[0].success is True
        assert report.exit_code == 0

    def test_status_new_dep_lands_in_the_changed_set_with_the_empty_change_list(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        write_config,
        recorder,
    ) -> None:
        """A never-synced dep is drift: the ``new`` verdict with the empty change list.

        No git-boundary mock — ``_check_dep`` answers ``new`` before
        ``compute_dep_status`` is ever reached.
        """
        write_config(_CLICK_DEP_BLOCK)
        monkeypatch.chdir(tmp_path)

        report = status()

        completed = _of(recorder, "status_completed")

        assert completed[0].changed == [DepDrift(group="libs", dep="click", verdict=DriftVerdict.new, changes=[])]
        assert completed[0].changed[0].message is None
        assert completed[0].success is False
        assert report.deps[0].state is UsageState.new
        assert report.exit_code == 1
        assert completed[0].completion is Completion.finished

    def test_status_error_dep_lands_in_the_changed_set_with_its_message(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        write_config,
        recorder,
    ) -> None:
        """A per-dep check failure is best-effort drift: the error verdict carries its message.

        The crash text of the compare (which embeds the URL with its token)
        never reaches the facts — the record reuses the credential-free
        ``DepStatus.error``. An error dep is drift: the check's success is
        False even though the run finished through its own paths.
        """
        write_config(_CLICK_DEP_BLOCK)
        (tmp_path / ".goga" / "usages" / "libs" / "click").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)

        with mock.patch.object(
            _status_mod,
            "compute_dep_status",
            side_effect=RuntimeError("git failed https://user:tok@x/click.git"),
        ):
            result = status()

        completed = _of(recorder, "status_completed")

        assert completed[0].changed[0].verdict is DriftVerdict.error
        assert completed[0].changed[0].changes == []
        assert completed[0].changed[0].message == "failed to check usages status for libs/click"
        assert completed[0].success is False  # error deps count as drift
        assert completed[0].completion is Completion.finished  # best-effort, not a crash
        assert result.exit_code == 1

    @pytest.mark.parametrize("boom_address", ["status_started", "status_completed"])
    def test_failing_hook_warns_and_the_check_is_unaffected(  # noqa: PLR0913, PLR0917
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        write_config,
        pin_package_environment,
        install_tool_package,
        caplog: pytest.LogCaptureFixture,
        boom_address: str,
    ) -> None:
        """A raising hook of either status address warns; the report is unchanged.

        The soft error class of the address carries the failure — the hook
        is skipped inside the platform and the sequence continues, so even a
        completion-time raise leaves the report intact.
        """
        write_config(_CLICK_DEP_BLOCK)
        (tmp_path / ".goga" / "usages" / "libs" / "click").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        pin_package_environment({"goga_tool_mixed": ["goga-tool-mixed"]})
        completed: list[object] = []

        def _register(hooks: object) -> None:
            def boom(context: object) -> None:
                raise RuntimeError("kaput")

            def record(context: object) -> None:
                completed.append(context)

            hooks.subscribe("usages", boom_address, "boom", boom)  # type: ignore[attr-defined]
            hooks.subscribe("usages", "status_completed", "record", record)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_mixed", register_hooks=_register)

        dep_status = DepStatus(group="libs", dep="click", state=UsageState.up_to_date, entries=[])

        with (
            mock.patch.object(_status_mod, "compute_dep_status", return_value=dep_status),
            caplog.at_level(logging.WARNING),
        ):
            report = status()

        assert report.exit_code == 0
        assert any(f"usages.{boom_address}" in entry.message and "kaput" in entry.message for entry in caplog.records)
        assert len(completed) == 1  # the check reached its completion

    @pytest.mark.parametrize(
        ("first_dep_status", "expected_changed"),
        [
            (
                DepStatus(
                    group="libs",
                    dep="click",
                    state=UsageState.out_of_date,
                    entries=[EntryStatus(path="b.md", kind=EntryKind.file, change=EntryChange.modified)],
                ),
                [
                    DepDrift(
                        group="libs",
                        dep="click",
                        verdict=DriftVerdict.out_of_date,
                        changes=[FileChange(path="b.md", change=ChangeVerdict.modified)],
                    )
                ],
            ),
            (
                DepStatus(group="libs", dep="click", state=UsageState.up_to_date, entries=[]),
                [],
            ),
        ],
    )
    def test_status_crash_path_carries_the_partial_changed_set(
        self,
        tmp_path: Path,
        recorder,
        first_dep_status: DepStatus,
        expected_changed: list[DepDrift],
    ) -> None:
        """A crash after the start emits the crashed completion with the partial drift.

        The injection point is ``_check_dep`` — a raise of
        ``compute_dep_status`` is absorbed by ``_check_dep``'s own
        ``except Exception`` into an error dep (the best-effort path, never a
        crash) — so the second dep's raise escapes the work helper to the
        crash wrapper, carrying whatever the first dep already recorded.
        (The autouse cwd isolation already points the run at ``tmp_path``.)
        """
        _write_config(tmp_path, _CLICK_COMMON_BLOCK)

        with (
            mock.patch.object(_status_mod, "_check_dep", side_effect=[first_dep_status, RuntimeError("boom")]),
            pytest.raises(RuntimeError, match="boom"),
        ):
            status()

        completed = _of(recorder, "status_completed")

        assert completed[0].completion is Completion.crashed
        assert completed[0].reason == "boom"
        assert completed[0].success is False
        assert completed[0].changed == expected_changed

    def test_a_keyboard_interrupt_completes_nothing_and_propagates(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        write_config,
        recorder,
    ) -> None:
        """A ``BaseException`` such as ``KeyboardInterrupt`` completes nothing.

        The crash wrapper catches ``Exception`` only — matching the
        platform's own catch policy — so a Ctrl-C during the check
        propagates without a completion moment: the start moment is the
        run's last fact.
        """
        write_config(_CLICK_DEP_BLOCK)
        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(_status_mod, "_check_dep", side_effect=KeyboardInterrupt()),
            pytest.raises(KeyboardInterrupt),
        ):
            status()

        assert len(_of(recorder, "status_started")) == 1
        assert _of(recorder, "status_completed") == []

    def test_status_no_op_run_fires_both_moments_with_the_empty_changed_set(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        write_config,
        recorder,
    ) -> None:
        """An absent usages section still fires both moments with the empty fact set.

        The None-or-empty short-circuit returns through the same single
        finished-emission site as a populated run — nothing to check is a
        completed run, not a silent one.
        """
        write_config(None)
        monkeypatch.chdir(tmp_path)

        report = status()

        started = _of(recorder, "status_started")
        completed = _of(recorder, "status_completed")

        assert report.deps == []
        assert report.exit_code == 0
        assert len(started) == 1
        assert len(completed) == 1
        assert completed[0].changed == []
        assert completed[0].success is True
        assert completed[0].completion is Completion.finished

    def test_config_boundary_abort_fires_no_usages_moment(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        recorder,
    ) -> None:
        """A missing config.yml aborts before any usages moment fires.

        The fail-loud configuration boundary precedes the start emission —
        the command wrapper converts the propagated error, as for any other
        failure.
        """
        monkeypatch.chdir(tmp_path)

        with pytest.raises(FileNotFoundError):
            status()

        assert recorder == []
