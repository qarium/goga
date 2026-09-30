"""Cross-package integration scenarios of the build orchestration.

The two suites moved out of ``tests/build/test_build.py`` — the classes
whose scenarios join more than one package and belong under
``tests/integration/`` per the testing conventions:

- the secret-safe dry run across the orchestrator/launcher seam
  (``goga/build`` with ``goga/ralphex``)
- the orchestration scenarios joining ``goga/build`` with
  ``goga/build/hooks`` over the fake tool packages

The orchestration harness — the pinned boundary, the in-tmp run, the
recording tool, and the synthetic vendored sources — is owned by the unit
suite and imported from it, so the two files stay behavior-identical.
"""

from __future__ import annotations

import logging
from pathlib import Path
from unittest import mock

from goga.config import ReviewConfig

from tests.build.test_build import (
    _FULL_CLI_OPTIONS,
    _install_recording_tool,
    _make_config,
    _mock_vendored_sources,
    _run_build_in_tmp,
    build_module,
)

# --- Integration: secret-safe dry-run across the orchestration/launcher seam ---


class TestBuildDryRunSecretSafeIntegration:
    """Cross-entity scenario joining the orchestrator (goga/build) with the
    launcher's print (goga/ralphex): a two-pass dry run prints the argv of both
    passes and never the contents of any env layer.

    The real launcher and the real pass executor run here: the dry-run branch
    performs no PATH check and no subprocess, so the seam under test is the
    actual print the container would emit — a regression in either the
    orchestration (folding an env into the options) or the launcher's print
    fails this test."""

    def test_build_dry_run_two_pass_no_env_in_output(self, tmp_path, monkeypatch, capsys) -> None:
        config = _make_config(
            env={"TASKS_SECRET": "tasks-value"},
            review=ReviewConfig(agent="codex", env={"ANTHROPIC_MODEL": "reviewer"}),
        )

        with _mock_vendored_sources(tmp_path):
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                config=config,
                cli_options={**_FULL_CLI_OPTIONS, "dry_run": True},
            )

        assert result == 0
        captured = capsys.readouterr()
        # Both planned passes had their argv printed to stderr.
        assert captured.err.count("ralphex") >= 2
        assert "--tasks-only" in captured.err
        assert "--review" in captured.err
        # No env layer value or name reaches the dry-run output.
        assert "reviewer" not in captured.err
        assert "ANTHROPIC_MODEL" not in captured.err
        assert "tasks-value" not in captured.err
        assert "TASKS_SECRET" not in captured.err
        # A dry run relocates nothing.
        assert (tmp_path / "plan.md").is_file()
        assert not (tmp_path / "completed").exists()


# --- Orchestration integration scenarios (Task 19) ---


class TestOrchestrationIntegrationScenarios:
    """Cross-entity scenarios joining goga/build with goga/build/hooks and the
    fake tool packages over the platform boundary fixtures: completion facts on
    the notifications, the dry-run rehearsal of the event structure, and the
    enumeration-once invariant of the run registry."""

    def test_notifications_carry_completion_facts(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The notification sequence carries the actual facts: pass completions
        with their real exit codes, and the completion event with the final
        code, the executed stages, and the failed-run relocation outcome."""
        recorded: list[tuple[str, object]] = []
        pin_package_environment({"goga_tool_demo": ["demo-dist"]})
        _install_recording_tool(install_tool_package, recorded)

        with mock.patch.object(build_module, "run_build_pass", side_effect=[0, 2]):
            result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options=dict(_FULL_CLI_OPTIONS))

        assert result == 2

        # The full notification sequence of a two-pass run with a failed review.
        assert [action for action, _context in recorded] == [
            "validate_build",
            "build_started",
            "pass_started",
            "pass_completed",
            "pass_started",
            "pass_completed",
            "build_completed",
        ]

        # Completion is a fact, not a success claim: the review pass's
        # completion carries its actual non-zero code.
        completions = [context for action, context in recorded if action == "pass_completed"]
        assert [context.exit_code for context in completions] == [0, 2]
        assert completions[1].facts.stage == "review"

        completed = next(context for action, context in recorded if action == "build_completed")
        assert completed.exit_code == 2
        assert completed.stages == ["tasks", "review"]
        assert completed.relocation.moved is False

        # The failed final pass keeps the plan in place for a resumable re-run.
        assert (tmp_path / "plan.md").is_file()

    def test_crashing_notification_hook_warns_and_run_unaffected(
        self,
        tmp_path: Path,
        monkeypatch,
        caplog,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A crashing soft hook warns inside the platform; the exit code of the
        run is never affected (SC4)."""

        def register(hooks: object) -> None:
            def broken(self: object, context: object) -> None:
                raise RuntimeError("notify boom")

            def make(action: str):
                def hook(self: object, context: object) -> None:
                    pass

                return hook

            hooks.subscribe("build", "build_started", "broken", broken)  # type: ignore[attr-defined]
            for action in ("pass_started", "pass_completed", "build_completed"):
                hooks.subscribe("build", action, action, make(action))  # type: ignore[attr-defined]

        pin_package_environment({"goga_tool_crash": ["crash-dist"]})
        install_tool_package("goga_tool_crash", register_hooks=register)

        with (
            caplog.at_level(logging.WARNING, logger="goga.hooks.dispatch.emit"),
            mock.patch.object(build_module, "run_build_pass", side_effect=[0, 2]),
        ):
            result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options=dict(_FULL_CLI_OPTIONS))

        assert result == 2
        warnings = [record for record in caplog.records if record.levelno == logging.WARNING]
        assert any(
            record.getMessage() == "hook broken of tool crash failed on build.build_started: notify boom"
            for record in warnings
        )

    def test_build_dry_run_rehearses_event_structure(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A dry run rehearses the identical event structure: the gate runs, both
        passes reach the launcher dry, the plan stays, the relocation outcome is
        not-moved, and every delivered moment carries dry_run=True (SC6).

        run_build_pass stays real here — only the launcher seam is stubbed. The
        patch lands at the consumer's import point (goga.build.build_pass),
        because the facade re-export shadows the submodule path named by the
        design (per [[feedback_mock_patch_module_shadowing]]).
        """
        recorded: list[tuple[str, object]] = []
        pin_package_environment({"goga_tool_demo": ["demo-dist"]})
        _install_recording_tool(install_tool_package, recorded)

        with mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_launch:
            result = _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                cli_options={**_FULL_CLI_OPTIONS, "dry_run": True},
            )

        assert result == 0

        # Both passes "ran" — the real pass executor delegated each to the
        # launcher with dry_run=True (third positional of run_ralphex).
        assert mock_launch.call_count == 2
        assert all(call.args[2] is True for call in mock_launch.call_args_list)

        # The identical event structure fired, gate included.
        assert [action for action, _context in recorded] == [
            "validate_build",
            "build_started",
            "pass_started",
            "pass_completed",
            "pass_started",
            "pass_completed",
            "build_completed",
        ]

        # Nothing executed and nothing relocated: the plan file is still at its
        # original path and the completion facts say so.
        assert (tmp_path / "plan.md").is_file()
        completed = next(context for action, context in recorded if action == "build_completed")
        assert completed.relocation.moved is False
        assert completed.moment.dry_run is True

        started = next(context for action, context in recorded if action == "build_started")
        assert started.moment.dry_run is True

    def test_registry_built_once_across_checkpoints(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """One HookRegistry per run: the packages_distributions boundary is read
        exactly once across a full build() run reaching several checkpoints."""
        recorded: list[tuple[str, object]] = []
        boundary = pin_package_environment({"goga_tool_demo": ["demo-dist"]})

        def register(hooks: object) -> None:
            def make(action: str):
                def hook(self: object, context: object) -> None:
                    recorded.append((action, context))

                return hook

            for action in ("validate_build", "build_started", "build_completed"):
                hooks.subscribe("build", action, action, make(action))  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register)

        with mock.patch.object(build_module, "run_build_pass", return_value=0):
            result = _run_build_in_tmp(tmp_path, monkeypatch, cli_options=dict(_FULL_CLI_OPTIONS))

        assert result == 0
        assert [action for action, _context in recorded] == ["validate_build", "build_started", "build_completed"]
        assert boundary.call_count == 1

    def test_second_run_sees_edited_hook(
        self,
        tmp_path: Path,
        monkeypatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """SC10 — no caching across runs: registration re-reads, so a second
        build() run in the same process picks up a hook edit made between the
        runs."""
        recorded: list[str] = []
        pin_package_environment({"goga_tool_edit": ["edit-dist"]})
        module = install_tool_package("goga_tool_edit")

        def register_v1(hooks: object) -> None:
            def hook(self: object, context: object) -> None:
                recorded.append("v1")

            hooks.subscribe("build", "validate_build", "guard", hook)  # type: ignore[attr-defined]

        module.register_hooks = register_v1

        with mock.patch.object(build_module, "run_build_pass", return_value=0):
            first = _run_build_in_tmp(tmp_path, monkeypatch, cli_options=dict(_FULL_CLI_OPTIONS))

        # The edit: the same installed package now registers a different hook
        # on a different action — only the registration callback changes.
        def register_v2(hooks: object) -> None:
            def hook(self: object, context: object) -> None:
                recorded.append("v2")

            hooks.subscribe("build", "build_started", "notified", hook)  # type: ignore[attr-defined]

        module.register_hooks = register_v2

        with mock.patch.object(build_module, "run_build_pass", return_value=0):
            second = _run_build_in_tmp(tmp_path, monkeypatch, cli_options=dict(_FULL_CLI_OPTIONS))

        assert first == 0
        assert second == 0
        assert recorded == ["v1", "v2"]
