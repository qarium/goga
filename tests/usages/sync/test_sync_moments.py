"""Contract and logic tests for the run-level moments of the sync operation.

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
import itertools
import logging
from collections.abc import Callable
from pathlib import Path
from unittest import mock

import pytest
from goga.usages import sync as facade_sync
from goga.usages.hooks import Completion, SyncOutcome
from goga.usages.sync import sync

# Resolve the inner ``sync.py`` submodule via importlib. The facade ``goga.usages``
# re-exports the ``sync`` function, which shadows the submodule attribute in the
# package ``__dict__``. On Python 3.10
# ``mock.patch("goga.usages.sync.clone_repository")`` resolves the dotted path
# through sequential ``getattr``, finds the function where it expects the
# submodule, and raises ``AttributeError``. Holding a direct reference to the
# module makes ``mock.patch.object`` work uniformly across Python versions.
_sync_mod = importlib.import_module("goga.usages.sync.sync")

# --- helpers ---


def _clone_factory(tmp_path: Path) -> Callable[[str, str | None], Path]:
    """Build a ``clone_repository`` stand-in returning a fresh repo per call.

    Each repo carries one ``.usages/conventions.md`` so the real
    ``deploy_usages`` finds a cell to deploy. A fresh dir per call matters:
    the operation's ``finally`` removes every returned clone, so a shared
    dir would vanish under the second matched dep.
    """
    counter = itertools.count()

    def _clone(url: str, ref: str | None) -> Path:
        repo = tmp_path / "clones" / f"clone_{next(counter)}"
        (repo / ".usages").mkdir(parents=True)
        (repo / ".usages" / "conventions.md").write_text("# a cell-level usage\n")
        return repo

    return _clone


def _install_recorder(
    pin_package_environment: Callable[[dict[str, list[str]]], object],
    install_tool_package: Callable[..., object],
) -> list[tuple[str, object]]:
    """Pin the environment and install the all-addresses recorder.

    Returns the capture — ``(address, context)`` pairs, one per delivered
    context, in delivery order.
    """
    captured: list[tuple[str, object]] = []

    def _register(hooks: object) -> None:
        def _recorder_of(action: str) -> Callable[[object], None]:
            def _record(context: object) -> None:
                captured.append((action, context))

            return _record

        for action in ("sync_started", "sync_completed", "status_started", "status_completed"):
            hooks.subscribe("usages", action, f"rec_{action}", _recorder_of(action))  # type: ignore[attr-defined]

    pin_package_environment({"goga_tool_rec": ["goga-tool-rec"]})
    install_tool_package("goga_tool_rec", register_hooks=_register)

    return captured


def _of(captured: list[tuple[str, object]], action: str) -> list[object]:
    """Project the capture onto one address's delivered contexts."""
    return [context for name, context in captured if name == action]


_CLICK_DEP_BLOCK = "usages:\n  libs:\n    click:\n      git: https://x/click.git\n      ref: main\n"

# One dep per outcome: click clones and deploys, common's clone raises,
# skipped's target dir pre-exists (the incremental skip path).
_SYNCED_FAILED_SKIPPED_BLOCK = (
    "usages:\n"
    "  libs:\n"
    "    click:\n"
    "      git: https://x/click.git\n"
    "      ref: main\n"
    "    common:\n"
    "      git: https://x/common.git\n"
    "      ref: main\n"
    "    skipped:\n"
    "      git: https://x/skipped.git\n"
    "      ref: main\n"
)

# The apps group is declared before libs on purpose: the dep-filter outcomes
# assert the config's insertion order, and apps/common is expected first.
_APPS_BEFORE_LIBS_BLOCK = (
    "usages:\n"
    "  apps:\n"
    "    common:\n"
    "      git: https://x/common.git\n"
    "      ref: main\n"
    "  libs:\n"
    "    click:\n"
    "      git: https://x/click.git\n"
    "      ref: main\n"
    "    common:\n"
    "      git: https://x/common.git\n"
    "      ref: main\n"
)


# --- contract tests ---


class TestSyncMomentsContract:
    def test_signature_is_unchanged(self) -> None:
        """Signature stays sync(force: bool = False, group=None, dep=None) -> int."""
        sig = inspect.signature(sync)
        params = list(sig.parameters)
        assert params == ["force", "group", "dep"]
        assert sig.parameters["force"].annotation is bool
        assert sig.parameters["force"].default is False
        assert sig.parameters["group"].default is None
        assert sig.parameters["dep"].default is None
        assert sig.return_annotation is int

    def test_importable_from_goga_usages_sync(self) -> None:
        """sync is importable from goga.usages.sync."""
        assert callable(sync)

    def test_importable_from_facade(self) -> None:
        """sync is the same object exported by the goga.usages facade."""
        assert sync is facade_sync


# --- logic tests — the real operation over the boundary fixtures ---


class TestSyncMoments:
    def test_sync_emits_both_moments_with_per_dep_outcomes(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        write_config,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A mixed run records one outcome per matched dep, in iteration order.

        The failed record carries the credential-free message — the crash
        text of the clone (which embeds the URL with its token) never
        reaches the facts.
        """
        write_config(_SYNCED_FAILED_SKIPPED_BLOCK)
        (tmp_path / ".goga" / "usages" / "libs" / "skipped").mkdir(parents=True)
        monkeypatch.chdir(tmp_path)
        captured = _install_recorder(pin_package_environment, install_tool_package)

        clone_ok = _clone_factory(tmp_path)

        def _clone_or_fail(url: str, ref: str | None) -> Path:
            if url == "https://x/common.git":
                raise RuntimeError("git failed https://user:tok@x/common.git")
            return clone_ok(url, ref)

        with mock.patch.object(_sync_mod, "clone_repository", side_effect=_clone_or_fail):
            sync_result = sync(force=False, group="libs", dep=None)

        started = _of(captured, "sync_started")
        completed = _of(captured, "sync_completed")

        assert sync_result == 1
        assert len(started) == 1
        assert started[0].moment.operation == "sync"
        assert started[0].moment.group == "libs"
        assert started[0].force is False
        assert len(completed) == 1
        assert [(o.group, o.dep, o.outcome) for o in completed[0].deps] == [
            ("libs", "click", SyncOutcome.synced),
            ("libs", "common", SyncOutcome.failed),
            ("libs", "skipped", SyncOutcome.skipped),
        ]
        assert completed[0].deps[1].message == "failed to sync usages for libs/common"
        assert "tok" not in completed[0].deps[1].message  # credential-free by construction
        assert completed[0].success is False
        assert completed[0].completion is Completion.finished

    def test_sync_no_op_run_fires_both_moments_with_empty_outcomes(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        write_config,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """An absent usages section still fires both moments with the empty fact set.

        The moments wrap the operation, not the workload — nothing to do is
        a completed run, not a silent one.
        """
        write_config(None)
        monkeypatch.chdir(tmp_path)
        captured = _install_recorder(pin_package_environment, install_tool_package)

        assert sync() == 0

        started = _of(captured, "sync_started")
        completed = _of(captured, "sync_completed")

        assert len(started) == 1
        assert len(completed) == 1
        assert completed[0].deps == []
        assert completed[0].success is True
        assert completed[0].completion is Completion.finished

    def test_failing_hook_warns_and_the_operation_is_unaffected(
        self,
        tmp_path: Path,
        write_config,
        pin_package_environment,
        install_tool_package,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A raising sync_started hook warns; the run itself completes unchanged.

        The soft error class of the address carries the failure — the hook
        is skipped inside the platform and the sequence continues. (The
        autouse cwd isolation already points the run at ``tmp_path``.)
        """
        write_config(_CLICK_DEP_BLOCK)
        pin_package_environment({"goga_tool_mixed": ["goga-tool-mixed"]})
        completed: list[object] = []

        def _register(hooks: object) -> None:
            def boom(context: object) -> None:
                raise RuntimeError("kaput")

            def record(context: object) -> None:
                completed.append(context)

            hooks.subscribe("usages", "sync_started", "boom", boom)  # type: ignore[attr-defined]
            hooks.subscribe("usages", "sync_completed", "record", record)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_mixed", register_hooks=_register)

        with (
            mock.patch.object(_sync_mod, "clone_repository", side_effect=_clone_factory(tmp_path)),
            caplog.at_level(logging.WARNING),
        ):
            result = sync()

        assert result == 0
        assert any("usages.sync_started" in entry.message and "kaput" in entry.message for entry in caplog.records)
        assert len(completed) == 1  # the run reached its completion

    def test_config_boundary_abort_fires_no_usages_moment(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A missing config.yml aborts before any usages moment fires.

        The fail-loud configuration boundary precedes the start emission —
        the command wrapper converts the propagated error, as for any other
        failure.
        """
        monkeypatch.chdir(tmp_path)
        captured = _install_recorder(pin_package_environment, install_tool_package)

        with pytest.raises(FileNotFoundError):
            sync()

        assert captured == []

    def test_sync_crash_path_emits_the_crashed_completion_and_reraises(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        write_config,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A crash after the start emits the crashed completion, then re-raises.

        The injection point (``clean_usages_dir``) sits outside the
        absorbing per-dep try, so the exception escapes the work helper and
        reaches the crash wrapper; the outcome set stays empty — the
        break-off preceded every dep.
        """
        write_config(_CLICK_DEP_BLOCK)
        monkeypatch.chdir(tmp_path)
        captured = _install_recorder(pin_package_environment, install_tool_package)

        with (
            mock.patch.object(_sync_mod, "clean_usages_dir", side_effect=RuntimeError("boom")),
            pytest.raises(RuntimeError, match="boom"),
        ):
            sync(force=True)

        completed = _of(captured, "sync_completed")

        assert completed[0].completion is Completion.crashed
        assert completed[0].success is False
        assert completed[0].reason == "boom"
        assert completed[0].deps == []

    def test_filtered_deps_are_absent_from_every_fact(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        write_config,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A dep-only filter syncs its matches across groups; the rest are absent.

        ``click`` is filtered out — absent from the outcomes without any
        skipped record — while the envelope mirrors the applied filter.
        """
        write_config(_APPS_BEFORE_LIBS_BLOCK)
        monkeypatch.chdir(tmp_path)
        captured = _install_recorder(pin_package_environment, install_tool_package)

        with mock.patch.object(_sync_mod, "clone_repository", side_effect=_clone_factory(tmp_path)):
            assert sync(dep="common") == 0

        started = _of(captured, "sync_started")
        completed = _of(captured, "sync_completed")

        outcomes = [(o.group, o.dep) for o in completed[0].deps]
        assert outcomes == [("apps", "common"), ("libs", "common")]  # click absent, insertion order
        assert started[0].moment.dep == "common"  # the envelope mirrors the filters
