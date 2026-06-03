from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest import mock

import click
import yaml
from click.testing import CliRunner
from goga.commands import build as build_cmd

_build_mod = sys.modules["goga.commands.build.build"]


def _write_goga_yml(tmp_path: Path, extra: dict | None = None) -> None:
    """Write a minimal .goga/config.yml with optional extra build fields."""
    data: dict = {
        "language": "python",
        "build": {"task_executor": {"agent": "claude"}},
    }
    if extra:
        data["build"].update(extra)
    (tmp_path / ".goga").mkdir(exist_ok=True)
    (tmp_path / ".goga" / "config.yml").write_text(yaml.dump(data))


def _run_build_in_tmp(tmp_path, monkeypatch, args=None, *, skip_manifest_check=True):
    """Run the build command in tmp_path directory."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    full_args = list(args or [])
    if skip_manifest_check:
        full_args = ["--skip-manifest-check", *full_args]
    return runner.invoke(build_cmd, full_args)


# --- Facade / API Shape tests ---


class TestFacadeAvailability:
    def test_import_build_from_commands(self) -> None:
        assert build_cmd is not None

    def test_build_is_click_command(self) -> None:
        assert isinstance(build_cmd, click.Command)


class TestApiShape:
    def test_build_has_callback(self) -> None:
        assert build_cmd.callback is not None

    def test_build_name(self) -> None:
        assert build_cmd.name == "build"

    def test_build_has_plan_argument(self) -> None:
        param_names = [p.name for p in build_cmd.params]
        assert "plan" in param_names

    def test_build_plan_no_default_value(self) -> None:
        plan_param = next(p for p in build_cmd.params if p.name == "plan")
        assert plan_param.required is True

    def test_build_plan_is_required(self, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path)
        result = _run_build_in_tmp(tmp_path, monkeypatch)
        assert result.exit_code == 2
        assert "Missing argument" in result.output

    def test_build_has_ten_options(self) -> None:
        options = [p for p in build_cmd.params if isinstance(p, click.Option)]
        assert len(options) == 10

    def test_build_has_dry_run_option(self) -> None:
        param_names = [p.name for p in build_cmd.params]
        assert "dry_run" in param_names

    def test_build_has_worktree_option(self) -> None:
        param_names = [p.name for p in build_cmd.params]
        assert "worktree" in param_names

    def test_build_has_extra_env_option(self) -> None:
        param_names = [p.name for p in build_cmd.params]
        assert "extra_env" in param_names

    def test_build_has_skip_finalize_option(self) -> None:
        param_names = [p.name for p in build_cmd.params]
        assert "skip_finalize" in param_names

    def test_build_has_skip_manifest_check_option(self) -> None:
        param_names = [p.name for p in build_cmd.params]
        assert "skip_manifest_check" in param_names

    def test_build_has_session_timeout_option(self) -> None:
        param_names = [p.name for p in build_cmd.params]
        assert "session_timeout" in param_names

    def test_build_has_idle_timeout_option(self) -> None:
        param_names = [p.name for p in build_cmd.params]
        assert "idle_timeout" in param_names

    def test_build_has_wait_option(self) -> None:
        param_names = [p.name for p in build_cmd.params]
        assert "wait" in param_names

    def test_build_has_max_iterations_option(self) -> None:
        param_names = [p.name for p in build_cmd.params]
        assert "max_iterations" in param_names

    def test_build_has_review_patience_option(self) -> None:
        param_names = [p.name for p in build_cmd.params]
        assert "review_patience" in param_names


class TestHelpOutput:
    def test_help_exit_code_zero(self) -> None:
        runner = CliRunner()
        result = runner.invoke(build_cmd, ["--help"])
        assert result.exit_code == 0

    def test_help_contains_all_options(self) -> None:
        runner = CliRunner()
        result = runner.invoke(build_cmd, ["--help"])
        output = result.output
        for opt in (
            "--dry-run",
            "--worktree",
            "--skip-finalize",
            "--skip-manifest-check",
            "--session-timeout",
            "--idle-timeout",
            "--wait",
            "--max-iterations",
            "--review-patience",
            "-e",
        ):
            assert opt in output, f"Option {opt} not found in help output"


# --- Docker check tests ---


class TestDockerCheck:
    @mock.patch.object(_build_mod.subprocess, "run")
    def test_docker_available(self, mock_run, tmp_path, monkeypatch) -> None:
        mock_run.return_value = mock.Mock(returncode=0)
        _write_goga_yml(tmp_path)

        with mock.patch.object(subprocess, "call", return_value=0):
            result = _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        assert "docker not found" not in result.output

    def test_docker_not_available(self, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path)
        with mock.patch.object(_build_mod, "_check_docker", return_value=False):
            result = _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        assert result.exit_code == 1
        assert "docker not found" in result.output


# --- Dry run tests ---


class TestDryRun:
    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    def test_dry_run_exit_code_zero(self, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path)
        result = _run_build_in_tmp(tmp_path, monkeypatch, ["--dry-run", "plan.md"])
        assert result.exit_code == 0

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    @mock.patch.object(_build_mod, "_build_docker_cmd", return_value=["docker", "run"])
    def test_dry_run_does_not_call_docker(
        self, mock_cmd, mock_env, mock_docker, tmp_path, monkeypatch
    ) -> None:
        _write_goga_yml(tmp_path)
        with mock.patch.object(subprocess, "call") as mock_call:
            _run_build_in_tmp(tmp_path, monkeypatch, ["--dry-run", "plan.md"])
            mock_call.assert_not_called()


# --- Docker command assembly tests ---


class TestBuildDockerCmd:
    def test_basic_command(self) -> None:
        from goga.commands.build.build import _build_docker_cmd

        cmd = _build_docker_cmd("plan.md", "goga:latest", Path("/tmp/env"), {})
        assert cmd[0] == "docker"
        assert "run" in cmd
        assert "--env-file" in cmd
        assert "/tmp/env" in cmd
        assert "goga:latest" in cmd
        assert "-m" in cmd
        assert "goga.build" in cmd
        assert "plan.md" in cmd

    def test_dry_run_flag(self) -> None:
        from goga.commands.build.build import _build_docker_cmd

        cmd = _build_docker_cmd("plan.md", "goga:latest", Path("/tmp/env"), {"dry_run": True})
        assert "--dry-run" in cmd

    def test_worktree_flag(self) -> None:
        from goga.commands.build.build import _build_docker_cmd

        cmd = _build_docker_cmd("plan.md", "goga:latest", Path("/tmp/env"), {"worktree": True})
        assert "--worktree" in cmd

    def test_skip_finalize_flag(self) -> None:
        from goga.commands.build.build import _build_docker_cmd

        cmd = _build_docker_cmd("plan.md", "goga:latest", Path("/tmp/env"), {"skip_finalize": True})
        assert "--skip-finalize" in cmd

    def test_session_timeout_flag(self) -> None:
        from goga.commands.build.build import _build_docker_cmd

        cmd = _build_docker_cmd("plan.md", "goga:latest", Path("/tmp/env"), {"session_timeout": "30m"})
        assert "--session-timeout" in cmd
        assert "30m" in cmd

    def test_max_iterations_flag(self) -> None:
        from goga.commands.build.build import _build_docker_cmd

        cmd = _build_docker_cmd("plan.md", "goga:latest", Path("/tmp/env"), {"max_iterations": 10})
        assert "--max-iterations" in cmd
        assert "10" in cmd

    def test_review_patience_flag(self) -> None:
        from goga.commands.build.build import _build_docker_cmd

        cmd = _build_docker_cmd("plan.md", "goga:latest", Path("/tmp/env"), {"review_patience": 3})
        assert "--review-patience" in cmd
        assert "3" in cmd

    def test_custom_image(self) -> None:
        from goga.commands.build.build import _build_docker_cmd

        cmd = _build_docker_cmd("plan.md", "custom:tag", Path("/tmp/env"), {})
        assert "custom:tag" in cmd


# --- Env file tests ---


class TestWriteEnvFile:
    def test_creates_file_with_env_vars(self, tmp_path) -> None:
        from goga.commands.build.build import _write_env_file

        env_file = _write_env_file({"KEY1": "val1", "KEY2": "val2"}, ())
        assert env_file.is_file()
        content = env_file.read_text()
        assert "KEY1=val1" in content
        assert "KEY2=val2" in content
        env_file.unlink(missing_ok=True)

    def test_appends_extra_env(self, tmp_path) -> None:
        from goga.commands.build.build import _write_env_file

        env_file = _write_env_file({}, ("EXTRA=extra_val",))
        content = env_file.read_text()
        assert "EXTRA=extra_val" in content
        env_file.unlink(missing_ok=True)

    def test_merges_env_and_extra(self, tmp_path) -> None:
        from goga.commands.build.build import _write_env_file

        env_file = _write_env_file({"BASE": "base_val"}, ("EXTRA=extra_val",))
        content = env_file.read_text()
        assert "BASE=base_val" in content
        assert "EXTRA=extra_val" in content
        env_file.unlink(missing_ok=True)

    def test_file_permissions_0600(self, tmp_path) -> None:
        import stat as stat_mod

        from goga.commands.build.build import _write_env_file

        env_file = _write_env_file({}, ())
        mode = env_file.stat().st_mode
        assert mode & stat_mod.S_IRUSR
        assert mode & stat_mod.S_IWUSR
        assert not (mode & stat_mod.S_IRGRP)
        assert not (mode & stat_mod.S_IWGRP)
        env_file.unlink(missing_ok=True)


# --- Extra env CLI option tests ---


class TestExtraEnvOption:
    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    @mock.patch.object(_build_mod, "_build_docker_cmd", return_value=["docker", "run"])
    def test_extra_env_passed_to_write_env_file(
        self, mock_cmd, mock_env, mock_docker, tmp_path, monkeypatch
    ) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")

        with mock.patch.object(subprocess, "call", return_value=0):
            _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                ["-e", "KEY=VALUE", "-e", "OTHER=VAL2", "plan.md"],
            )

        call_args = mock_env.call_args
        extra_env = call_args[0][1]
        assert "KEY=VALUE" in extra_env
        assert "OTHER=VAL2" in extra_env

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    @mock.patch.object(_build_mod, "_build_docker_cmd", return_value=["docker", "run"])
    def test_no_extra_env_empty_tuple(
        self, mock_cmd, mock_env, mock_docker, tmp_path, monkeypatch
    ) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")

        with mock.patch.object(subprocess, "call", return_value=0):
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        call_args = mock_env.call_args
        extra_env = call_args[0][1]
        assert extra_env == ()


# --- Docker execution tests ---


class TestDockerExecution:
    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    @mock.patch.object(_build_mod, "_build_docker_cmd")
    def test_subprocess_called_with_docker_cmd(
        self, mock_cmd, mock_env, mock_docker, tmp_path, monkeypatch
    ) -> None:
        mock_env.return_value = Path("/tmp/env")
        mock_cmd.return_value = ["docker", "run", "goga:latest", "-m", "goga.build", "plan.md"]
        _write_goga_yml(tmp_path)

        with mock.patch.object(subprocess, "call", return_value=0) as mock_call:
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])
            mock_call.assert_called_once_with(
                ["docker", "run", "goga:latest", "-m", "goga.build", "plan.md"]
            )

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    @mock.patch.object(_build_mod, "_build_docker_cmd")
    def test_exit_code_propagated(
        self, mock_cmd, mock_env, mock_docker, tmp_path, monkeypatch
    ) -> None:
        mock_env.return_value = Path("/tmp/env")
        mock_cmd.return_value = ["docker", "run"]
        _write_goga_yml(tmp_path)

        with mock.patch.object(subprocess, "call", return_value=42):
            result = _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])
            assert result.exit_code == 42


# --- Env file cleanup tests ---


class TestEnvFileCleanup:
    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_build_docker_cmd", return_value=["docker", "run"])
    def test_env_file_cleaned_after_execution(self, mock_cmd, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path)
        real_env_files: list[Path] = []

        def capture_env_file(env, extra_env):
            fd, path = __import__("tempfile").mkstemp(prefix="goga-env-test-")
            __import__("os").close(fd)
            p = Path(path)
            real_env_files.append(p)
            return p

        with (
            mock.patch.object(_build_mod, "_write_env_file", side_effect=capture_env_file),
            mock.patch.object(subprocess, "call", return_value=0),
        ):
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        for env_file in real_env_files:
            assert not env_file.exists(), f"Env file {env_file} was not cleaned up"


# --- Config loading tests ---


class TestBuildUsesLoadConfigFromGogaConfig:
    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    @mock.patch.object(_build_mod, "_build_docker_cmd")
    def test_image_from_config(
        self, mock_cmd, mock_env, mock_docker, tmp_path, monkeypatch
    ) -> None:
        _write_goga_yml(tmp_path, extra={"image": "custom-image:v2"})
        mock_env.return_value = Path("/tmp/env")
        mock_cmd.return_value = ["docker", "run"]

        with mock.patch.object(subprocess, "call", return_value=0):
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        call_kwargs = mock_cmd.call_args[1]
        assert call_kwargs["image"] == "custom-image:v2"

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    @mock.patch.object(_build_mod, "_build_docker_cmd")
    def test_default_image(
        self, mock_cmd, mock_env, mock_docker, tmp_path, monkeypatch
    ) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")
        mock_cmd.return_value = ["docker", "run"]

        with mock.patch.object(subprocess, "call", return_value=0):
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        call_kwargs = mock_cmd.call_args[1]
        assert call_kwargs["image"] == "qarium/goga:latest"


class TestBuildMissingGogaYmlRaisesConfigError:
    def test_build_missing_goga_config_yml_raises_config_error(self, tmp_path, monkeypatch) -> None:
        result = _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])
        assert result.exit_code == 1
        assert ".goga/config.yml" in result.output


# --- Negative cases ---


class TestBuildNegativeCases:
    def test_build_invalid_goga_config_raises_config_error(self, tmp_path, monkeypatch) -> None:
        data = {
            "build": {"task_executor": {"agent": "claude"}},
        }
        (tmp_path / ".goga").mkdir(exist_ok=True)
        (tmp_path / ".goga" / "config.yml").write_text(yaml.dump(data))

        result = _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])
        assert result.exit_code == 1
        assert "is required in .goga/config.yml" in result.output or "must be" in result.output


# --- CLI flag forwarding tests ---


class TestCLIFlagForwarding:
    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    @mock.patch.object(_build_mod, "_build_docker_cmd")
    def test_worktree_forwarded(
        self, mock_cmd, mock_env, mock_docker, tmp_path, monkeypatch
    ) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")
        mock_cmd.return_value = ["docker", "run"]

        with mock.patch.object(subprocess, "call", return_value=0):
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md", "--worktree"])

        cli_flags = mock_cmd.call_args[1]["cli_flags"]
        assert cli_flags["worktree"] is True

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    @mock.patch.object(_build_mod, "_build_docker_cmd")
    def test_session_timeout_forwarded(
        self, mock_cmd, mock_env, mock_docker, tmp_path, monkeypatch
    ) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")
        mock_cmd.return_value = ["docker", "run"]

        with mock.patch.object(subprocess, "call", return_value=0):
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md", "--session-timeout", "30m"])

        cli_flags = mock_cmd.call_args[1]["cli_flags"]
        assert cli_flags["session_timeout"] == "30m"

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    @mock.patch.object(_build_mod, "_build_docker_cmd")
    def test_skip_finalize_forwarded(
        self, mock_cmd, mock_env, mock_docker, tmp_path, monkeypatch
    ) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")
        mock_cmd.return_value = ["docker", "run"]

        with mock.patch.object(subprocess, "call", return_value=0):
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md", "--skip-finalize"])

        cli_flags = mock_cmd.call_args[1]["cli_flags"]
        assert cli_flags["skip_finalize"] is True


# --- Git config tests ---


class TestReadGitConfig:
    @mock.patch.object(_build_mod.subprocess, "run")
    def test_returns_git_env_vars(self, mock_run) -> None:
        from goga.commands.build.build import _read_git_config

        mock_run.side_effect = [
            mock.Mock(returncode=0, stdout="John Doe\n"),
            mock.Mock(returncode=0, stdout="john@example.com\n"),
        ]
        result = _read_git_config()

        assert result == {
            "GIT_AUTHOR_NAME": "John Doe",
            "GIT_AUTHOR_EMAIL": "john@example.com",
            "GIT_COMMITTER_NAME": "John Doe",
            "GIT_COMMITTER_EMAIL": "john@example.com",
        }

    @mock.patch.object(_build_mod.subprocess, "run")
    def test_returns_empty_when_name_missing(self, mock_run) -> None:
        from goga.commands.build.build import _read_git_config

        mock_run.side_effect = [
            mock.Mock(returncode=1, stdout=""),
            mock.Mock(returncode=0, stdout="john@example.com\n"),
        ]
        result = _read_git_config()
        assert result == {}

    @mock.patch.object(_build_mod.subprocess, "run")
    def test_returns_empty_when_email_missing(self, mock_run) -> None:
        from goga.commands.build.build import _read_git_config

        mock_run.side_effect = [
            mock.Mock(returncode=0, stdout="John Doe\n"),
            mock.Mock(returncode=1, stdout=""),
        ]
        result = _read_git_config()
        assert result == {}

    @mock.patch.object(_build_mod.subprocess, "run", side_effect=FileNotFoundError)
    def test_returns_empty_when_git_not_found(self, mock_run) -> None:
        from goga.commands.build.build import _read_git_config

        result = _read_git_config()
        assert result == {}

    @mock.patch.object(_build_mod.subprocess, "run", side_effect=PermissionError)
    def test_returns_empty_on_permission_error(self, mock_run) -> None:
        from goga.commands.build.build import _read_git_config

        result = _read_git_config()
        assert result == {}


class TestGitConfigMergedInBuild:
    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    @mock.patch.object(_build_mod, "_build_docker_cmd", return_value=["docker", "run"])
    @mock.patch.object(_build_mod, "_read_git_config")
    def test_git_env_merged_into_env_file(  # noqa: PLR0913
        self, mock_git, mock_cmd, mock_env, mock_docker, tmp_path, monkeypatch
    ) -> None:
        _write_goga_yml(tmp_path, extra={"task_executor": {"agent": "claude", "env": {"API_KEY": "secret"}}})
        mock_git.return_value = {
            "GIT_AUTHOR_NAME": "User",
            "GIT_AUTHOR_EMAIL": "u@e.com",
            "GIT_COMMITTER_NAME": "User",
            "GIT_COMMITTER_EMAIL": "u@e.com",
        }
        mock_env.return_value = Path("/tmp/env")

        with mock.patch.object(subprocess, "call", return_value=0):
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        call_args = mock_env.call_args
        env_dict = call_args[0][0]
        assert env_dict["API_KEY"] == "secret"
        assert env_dict["GIT_AUTHOR_NAME"] == "User"
        assert env_dict["GIT_COMMITTER_EMAIL"] == "u@e.com"

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    @mock.patch.object(_build_mod, "_build_docker_cmd", return_value=["docker", "run"])
    @mock.patch.object(_build_mod, "_read_git_config")
    def test_task_executor_env_has_priority(  # noqa: PLR0913
        self, mock_git, mock_cmd, mock_env, mock_docker, tmp_path, monkeypatch
    ) -> None:
        _write_goga_yml(tmp_path, extra={"task_executor": {"agent": "claude", "env": {"GIT_AUTHOR_NAME": "override"}}})
        mock_git.return_value = {"GIT_AUTHOR_NAME": "GitUser"}
        mock_env.return_value = Path("/tmp/env")

        with mock.patch.object(subprocess, "call", return_value=0):
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        env_dict = mock_env.call_args[0][0]
        assert env_dict["GIT_AUTHOR_NAME"] == "override"
