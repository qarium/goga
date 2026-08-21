from __future__ import annotations

import inspect
import typing
from pathlib import Path
from unittest import mock

import goga.build.build_pass as build_pass_module
import pytest
from goga.build.build_pass import run_build_pass
from goga.config import BuildConfig, TaskExecutorConfig


def _make_build_config(**kwargs) -> BuildConfig:
    task_executor = TaskExecutorConfig(agent=kwargs.pop("agent", "claude"), env={})
    return BuildConfig(task_executor=task_executor, **kwargs)


class TestRunBuildPassContract:
    def test_run_build_pass_importable_from_module(self) -> None:
        assert callable(run_build_pass)

    def test_run_build_pass_has_correct_signature(self) -> None:
        sig = inspect.signature(run_build_pass)
        params = list(sig.parameters.keys())
        assert params == ["plan", "config", "options", "wrapper_path", "dry_run", "env"]
        assert sig.parameters["env"].default is None

    def test_run_build_pass_param_types(self) -> None:
        hints = typing.get_type_hints(run_build_pass)
        assert hints["plan"] is str
        assert hints["config"] is BuildConfig
        assert hints["options"] == dict[str, str | int | bool]
        assert hints["wrapper_path"] is str
        assert hints["dry_run"] is bool
        assert hints["env"] == dict[str, str] | None

    def test_run_build_pass_returns_int(self) -> None:
        hints = typing.get_type_hints(run_build_pass)
        assert hints["return"] is int

    def test_module_imports_run_ralphex(self) -> None:
        """The ralphex launch is delegated via a module-level import — the
        orchestrator and the tests patch goga.build.build_pass.run_ralphex."""
        from goga.ralphex import run_ralphex as origin

        assert build_pass_module.run_ralphex is origin

    def test_module_has_no_subprocess_call(self) -> None:
        source = inspect.getsource(build_pass_module)
        assert "subprocess" not in source


class TestRunBuildPassLogic:
    def test_run_build_pass_writes_config_and_delegates(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_build_config(codex_review=True)
        options = {"worktree": True, "tasks_only": True}

        with mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run:
            exit_code = run_build_pass("plan.md", config, options, "/w/claude.sh", False)

        assert exit_code == 0
        mock_run.assert_called_once_with("plan.md", {"worktree": True, "tasks_only": True}, False, env=None)
        assert Path(".ralphex/config").exists()
        assert "claude_command = /w/claude.sh" in Path(".ralphex/config").read_text()

    def test_run_build_pass_propagates_exit_code(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_build_config()

        with mock.patch("goga.build.build_pass.run_ralphex", return_value=42) as mock_run:
            exit_code = run_build_pass("plan.md", config, {}, "/w/claude.sh", False)

        assert exit_code == 42
        mock_run.assert_called_once()

    def test_run_build_pass_dry_run_still_writes_config(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_build_config()

        with mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run:
            exit_code = run_build_pass("plan.md", config, {}, "/w/claude.sh", True)

        assert exit_code == 0
        mock_run.assert_called_once_with("plan.md", {}, True, env=None)
        assert "claude_command = /w/claude.sh" in Path(".ralphex/config").read_text()

    def test_run_build_pass_no_direct_subprocess(self, tmp_path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_build_config()

        with (
            mock.patch("goga.build.build_pass.run_ralphex", return_value=0),
            mock.patch("subprocess.call") as mock_call,
        ):
            run_build_pass("plan.md", config, {}, "/w/claude.sh", False)

        mock_call.assert_not_called()

    @pytest.mark.parametrize(
        ("options", "wrapper"),
        [
            ({"tasks_only": True}, "/home/goga/bin/claude-as-claude.sh"),
            ({"review": True}, "/home/goga/bin/codex-as-claude.sh"),
            ({}, "/home/goga/bin/claude-as-claude.sh"),
        ],
    )
    def test_run_build_pass_passes_options_verbatim(self, tmp_path, monkeypatch, options: dict, wrapper: str) -> None:
        monkeypatch.chdir(tmp_path)
        config = _make_build_config()

        with mock.patch("goga.build.build_pass.run_ralphex", return_value=0) as mock_run:
            run_build_pass("plan.md", config, options, wrapper, False)

        assert mock_run.call_args.args[1] is options

    def test_run_build_pass_forwards_env_to_run_ralphex(self, tmp_path, monkeypatch) -> None:
        """The env layer is forwarded verbatim as a kwarg; the pass adds no
        env logic of its own and the config write is unaffected by it."""
        monkeypatch.chdir(tmp_path)
        config = _make_build_config()

        with mock.patch("goga.build.build_pass.run_ralphex", return_value=7) as mock_run:
            exit_code = run_build_pass(
                "p.md", config, {"review": True}, "/w/codex.sh", False, env={"A": "1"}
            )

        assert exit_code == 7
        mock_run.assert_called_once_with("p.md", {"review": True}, False, env={"A": "1"})
        assert mock_run.call_args.args == ("p.md", {"review": True}, False)
        assert mock_run.call_args.kwargs == {"env": {"A": "1"}}
        assert "claude_command = /w/codex.sh" in Path(".ralphex/config").read_text()

    def test_run_build_pass_config_reflects_pass_executor(self, tmp_path, monkeypatch) -> None:
        """The second pass rewrites claude_command to the review wrapper."""
        monkeypatch.chdir(tmp_path)
        config = _make_build_config()

        with mock.patch("goga.build.build_pass.run_ralphex", return_value=0):
            run_build_pass("plan.md", config, {"tasks_only": True}, "/home/goga/bin/claude-as-claude.sh", False)
            run_build_pass("plan.md", config, {"review": True}, "/home/goga/bin/codex-as-claude.sh", False)

        config_text = Path(".ralphex/config").read_text()
        assert "claude_command = /home/goga/bin/codex-as-claude.sh" in config_text
        assert "move_plan_on_completion = false" in config_text
