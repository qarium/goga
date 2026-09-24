from __future__ import annotations

import inspect
import typing
from pathlib import Path
from unittest import mock

import goga.build.build_pass as build_pass_module
import pytest
from goga.build.build_pass import run_build_pass
from goga.build.run_settings import PassSettings, ReviewPassSettings, RunSettings
from goga.config import AdditionalReviewConfig

WRAPPER = "/home/goga/bin/claude-as-claude.sh"


def _make_settings() -> RunSettings:
    """Baseline run plan; the pass is a pure conduit, so no scenario mutates it."""
    return RunSettings(
        skip=False,
        tasks=PassSettings(agent="claude", env={}),
        review=ReviewPassSettings(
            agent="claude",
            env={},
            strategy="medium",
            additional=AdditionalReviewConfig(agent="claude", patience=None, max_iterations=None),
        ),
    )


class TestRunBuildPassContract:
    def test_run_build_pass_importable_from_module(self) -> None:
        assert callable(run_build_pass)

    def test_run_build_pass_has_correct_signature(self) -> None:
        sig = inspect.signature(run_build_pass)
        params = list(sig.parameters.keys())
        assert params == ["plan", "settings", "options", "wrapper_path", "dry_run", "env"]
        assert sig.parameters["env"].default is None

    def test_run_build_pass_param_types(self) -> None:
        hints = typing.get_type_hints(run_build_pass)
        assert hints["plan"] is str
        assert hints["settings"] is RunSettings
        assert hints["options"] == dict[str, str | int | bool]
        assert hints["wrapper_path"] is str
        assert hints["dry_run"] is bool
        assert hints["env"] == dict[str, str] | None

    def test_run_build_pass_returns_int(self) -> None:
        hints = typing.get_type_hints(run_build_pass)
        assert hints["return"] is int

    def test_module_imports_collaborators(self) -> None:
        """Both collaborators are module-level imports — the tests (and the
        orchestrator) patch goga.build.build_pass.write_ralphex_config /
        run_ralphex."""
        from goga.build.ralphex_config import write_ralphex_config as config_origin
        from goga.ralphex import run_ralphex as launch_origin

        assert build_pass_module.write_ralphex_config is config_origin
        assert build_pass_module.run_ralphex is launch_origin

    def test_module_has_no_subprocess_call(self) -> None:
        source = inspect.getsource(build_pass_module)
        assert "subprocess" not in source

    def test_run_build_pass_delegates_config_write(self, tmp_path, monkeypatch) -> None:
        """The settings object is carried to the config routine verbatim, paired
        with this pass's wrapper."""
        monkeypatch.chdir(tmp_path)
        settings = _make_settings()

        with (
            mock.patch("goga.build.build_pass.write_ralphex_config") as mock_write,
            mock.patch("goga.build.build_pass.run_ralphex", return_value=0),
        ):
            run_build_pass("plan.md", settings, {"tasks_only": True}, WRAPPER, False)

        mock_write.assert_called_once_with(settings, WRAPPER)

    def test_run_build_pass_delegates_launch(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        options = {"review": True}

        with (
            mock.patch("goga.build.build_pass.write_ralphex_config"),
            mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run,
        ):
            run_build_pass("plan.md", _make_settings(), options, WRAPPER, True, env={"A": "1"})

        mock_run.assert_called_once_with("plan.md", options, True, env={"A": "1"})


class TestRunBuildPassLogic:
    def test_run_build_pass_writes_config_before_launch(self, tmp_path, monkeypatch) -> None:
        """The config routine runs to completion before the launch delegate is
        invoked: the config is already on disk (with this pass's wrapper) at the
        moment the launch fires."""
        monkeypatch.chdir(tmp_path)
        seen: dict[str, str] = {}

        def recording_launch(plan, options, dry_run, env=None):
            seen["config_at_launch"] = Path(".ralphex/config").read_text()
            return 0

        monkeypatch.setattr(build_pass_module, "run_ralphex", recording_launch)

        exit_code = run_build_pass("plan.md", _make_settings(), {"tasks_only": True}, WRAPPER, False)

        assert exit_code == 0
        assert f"claude_command = {WRAPPER}" in seen["config_at_launch"]

    def test_run_build_pass_propagates_exit_code_unchanged(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)

        with mock.patch("goga.build.build_pass.run_ralphex", return_value=7) as mock_run:
            exit_code = run_build_pass("plan.md", _make_settings(), {"review": True}, WRAPPER, False)

        assert exit_code == 7
        mock_run.assert_called_once()

    def test_run_build_pass_forwards_env_verbatim_and_never_prints(
        self, tmp_path, monkeypatch, capsys
    ) -> None:
        """The env layer reaches the launcher as the same object, never the
        config file, the stdout, or the stderr — a secret boundary."""
        monkeypatch.chdir(tmp_path)
        env = {"ANTHROPIC_API_KEY": "sekret-token-value"}
        recorded: dict[str, object] = {}

        def recording_launch(plan, options, dry_run, env=None):
            recorded["env"] = env
            return 0

        monkeypatch.setattr(build_pass_module, "run_ralphex", recording_launch)

        run_build_pass("p.md", _make_settings(), {"review": True}, WRAPPER, False, env=env)

        assert recorded["env"] is env
        config_text = Path(".ralphex/config").read_text()
        assert "sekret-token-value" not in config_text
        assert "ANTHROPIC_API_KEY" not in config_text
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == ""

    def test_run_build_pass_env_none_passes_pure_inheritance(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        recorded: dict[str, object] = {}

        def recording_launch(plan, options, dry_run, env=None):
            recorded["env"] = env
            return 0

        monkeypatch.setattr(build_pass_module, "run_ralphex", recording_launch)

        run_build_pass("p.md", _make_settings(), {"tasks_only": True}, WRAPPER, False)

        assert recorded["env"] is None

    def test_run_build_pass_dry_run_still_writes_config(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)

        with mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run:
            exit_code = run_build_pass("plan.md", _make_settings(), {}, WRAPPER, True)

        assert exit_code == 0
        mock_run.assert_called_once_with("plan.md", {}, True, env=None)
        assert "claude_command = /home/goga/bin/claude-as-claude.sh" in Path(".ralphex/config").read_text()

    @pytest.mark.parametrize(
        ("options", "wrapper"),
        [
            ({"tasks_only": True}, "/home/goga/bin/claude-as-claude.sh"),
            ({"review": True}, "/home/goga/bin/codex-as-claude.sh"),
            ({}, "/home/goga/bin/claude-as-claude.sh"),
        ],
    )
    def test_run_build_pass_passes_options_verbatim(
        self, tmp_path, monkeypatch, options: dict, wrapper: str
    ) -> None:
        monkeypatch.chdir(tmp_path)

        with mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run:
            run_build_pass("plan.md", _make_settings(), options, wrapper, False)

        assert mock_run.call_args.args[1] is options

    def test_run_build_pass_config_reflects_pass_executor(self, tmp_path, monkeypatch) -> None:
        """The second pass rewrites claude_command whole to the review wrapper —
        the two calls with the same settings and different wrappers express the
        two-pass config switch."""
        monkeypatch.chdir(tmp_path)

        with mock.patch("goga.build.build_pass.run_ralphex", return_value=0):
            run_build_pass("plan.md", _make_settings(), {"tasks_only": True}, WRAPPER, False)
            run_build_pass(
                "plan.md",
                _make_settings(),
                {"review": True},
                "/home/goga/bin/codex-as-claude.sh",
                False,
            )

        config_text = Path(".ralphex/config").read_text()
        assert "claude_command = /home/goga/bin/codex-as-claude.sh" in config_text
        assert f"claude_command = {WRAPPER}" not in config_text
        assert "move_plan_on_completion = false" in config_text

    def test_run_build_pass_no_direct_subprocess(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)

        with (
            mock.patch("goga.build.build_pass.run_ralphex", return_value=0),
            mock.patch("subprocess.call") as mock_call,
        ):
            run_build_pass("plan.md", _make_settings(), {}, WRAPPER, False)

        mock_call.assert_not_called()
