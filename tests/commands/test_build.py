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


def _write_goga_yml(tmp_path: Path, extra: dict | None = None, *, no_image: bool = False) -> None:
    """Write a minimal .goga/config.yml in the new schema (top-level image, pipeline block)."""
    data: dict = {
        "language": "python",
        "image": "qarium/goga:latest",
        "build": {"task_executor": {"agent": "claude"}},
        "pipeline": {"agent": "claude"},
    }
    if no_image:
        del data["image"]
    if extra:
        # `image` is a top-level field now; build-internal keys go under `build`.
        for key, value in extra.items():
            if key == "image":
                data["image"] = value
            else:
                data["build"][key] = value
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

    def test_build_has_fourteen_options(self) -> None:
        options = [p for p in build_cmd.params if isinstance(p, click.Option)]
        assert len(options) == 14

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

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with mock.patch.object(subprocess, "Popen", return_value=mock_proc):
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
        with mock.patch.object(subprocess, "run"):
            result = _run_build_in_tmp(tmp_path, monkeypatch, ["--dry-run", "plan.md"])
        assert result.exit_code == 0

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_dry_run_does_not_call_docker(self, mock_env, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")
        with mock.patch.object(_build_mod, "DockerRunner") as mock_runner:
            _run_build_in_tmp(tmp_path, monkeypatch, ["--dry-run", "plan.md"])
            mock_runner.return_value.run.assert_not_called()


# --- Docker runner params assembly tests ---


class TestDockerRunnerParams:
    """The build assembles args + params and hands them to DockerRunner.run."""

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_basic_args_and_params(self, mock_env, mock_git, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")
        with mock.patch.object(_build_mod, "DockerRunner") as mock_runner:
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        mock_runner.assert_called_once_with("qarium/goga:latest")
        run = mock_runner.return_value.run
        run.assert_called_once()
        args = run.call_args.args[0]
        params = run.call_args.kwargs
        assert args[:2] == ["-m", "goga.build"]
        assert "plan.md" in args
        assert params["name"].startswith("goga-build-")
        assert params["rm"] is True
        assert params["entrypoint"] == "python3"
        assert params["workdir"] == "/workspace"
        assert params["env_file"] == "/tmp/env"

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_custom_image_used(self, mock_env, mock_git, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path, extra={"image": "custom:tag"})
        mock_env.return_value = Path("/tmp/env")
        with mock.patch.object(_build_mod, "DockerRunner") as mock_runner:
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])
        mock_runner.assert_called_once_with("custom:tag")

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_codex_auth_mounted_when_exists(self, mock_env, mock_git, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")
        codex_dir = tmp_path / ".codex"
        codex_dir.mkdir()
        (codex_dir / "auth.json").write_text("{}")
        monkeypatch.setenv("HOME", str(tmp_path))
        with mock.patch.object(_build_mod, "DockerRunner") as mock_runner:
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])
        mounts = mock_runner.return_value.run.call_args.kwargs["v"]
        assert any(m.endswith(":/home/goga/.codex/auth.json:ro") for m in mounts)

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_no_codex_auth_when_file_absent(self, mock_env, mock_git, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")
        monkeypatch.setenv("HOME", str(tmp_path))
        with mock.patch.object(_build_mod, "DockerRunner") as mock_runner:
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])
        mounts = mock_runner.return_value.run.call_args.kwargs["v"]
        assert not any(".codex" in m for m in mounts)


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
    def test_extra_env_passed_to_write_env_file(self, mock_env, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")

        with mock.patch.object(_build_mod, "DockerRunner") as mock_runner:
            mock_runner.return_value.run.return_value = 0
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
    def test_no_extra_env_empty_tuple(self, mock_env, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")

        with mock.patch.object(_build_mod, "DockerRunner") as mock_runner:
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        call_args = mock_env.call_args
        extra_env = call_args[0][1]
        assert extra_env == ()


# --- Docker execution tests ---


class TestDockerExecution:
    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_runner_called_with_build_args(self, mock_env, mock_docker, tmp_path, monkeypatch) -> None:
        mock_env.return_value = Path("/tmp/env")
        _write_goga_yml(tmp_path)

        with mock.patch.object(_build_mod, "DockerRunner") as mock_runner:
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        mock_runner.assert_called_once_with("qarium/goga:latest")
        args = mock_runner.return_value.run.call_args.args[0]
        assert args[:3] == ["-m", "goga.build", "plan.md"]

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_exit_code_propagated(self, mock_env, mock_docker, tmp_path, monkeypatch) -> None:
        mock_env.return_value = Path("/tmp/env")
        _write_goga_yml(tmp_path)

        with mock.patch.object(_build_mod, "DockerRunner") as mock_runner:
            mock_runner.return_value.run.return_value = 42
            result = _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])
            assert result.exit_code == 42


# --- Env file cleanup tests ---


class TestEnvFileCleanup:
    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    def test_env_file_cleaned_after_execution(self, mock_docker, tmp_path, monkeypatch) -> None:
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
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        for env_file in real_env_files:
            assert not env_file.exists(), f"Env file {env_file} was not cleaned up"


# --- Config loading tests ---


class TestBuildUsesLoadConfigFromGogaConfig:
    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_image_from_config(self, mock_env, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path, extra={"image": "custom-image:v2"})
        mock_env.return_value = Path("/tmp/env")

        with mock.patch.object(_build_mod, "DockerRunner") as mock_runner:
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        mock_runner.assert_called_once_with("custom-image:v2")

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_default_image(self, mock_env, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")

        with mock.patch.object(_build_mod, "DockerRunner") as mock_runner:
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        mock_runner.assert_called_once_with("qarium/goga:latest")

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    def test_build_raises_when_image_is_none(self, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path, no_image=True)

        result = _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        assert result.exit_code == 1
        assert "image in .goga/config.yml is not set" in result.output


class TestBuildMissingGogaYmlRaisesConfigError:
    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    def test_build_missing_goga_config_yml_raises_config_error(self, mock_docker, tmp_path, monkeypatch) -> None:
        result = _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])
        assert result.exit_code == 1
        assert ".goga/config.yml" in result.output


# --- Build section None-guard (D3, step 2b) tests ---


class TestBuildSectionGuard:
    """D3 — host-side None-guard: ClickException when the build section is absent.

    The guard (Algorithm step 2b) runs right after ``load_config()`` and before
    any ``config.build.*`` access or the secret env-file write, so a build-less
    config produces a clean user-facing error + exit 1 (no AttributeError, no
    docker run, no leaked env file).
    """

    @staticmethod
    def _write_config_without_build(tmp_path: Path) -> None:
        """Write a valid config that has NO build section (only language+image+pipeline)."""
        data = {
            "language": "python",
            "image": "qarium/goga:latest",
            "pipeline": {"agent": "claude"},
        }
        (tmp_path / ".goga").mkdir(exist_ok=True)
        (tmp_path / ".goga" / "config.yml").write_text(yaml.dump(data))

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    def test_build_command_raises_click_exception_when_build_section_absent(
        self, mock_docker, tmp_path, monkeypatch
    ) -> None:
        self._write_config_without_build(tmp_path)
        with mock.patch.object(_build_mod, "DockerRunner") as mock_runner:
            result = _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        assert result.exit_code == 1
        assert "build section is required" in result.output
        # docker run never starts on a build-less config.
        mock_runner.return_value.run.assert_not_called()

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_build_command_no_leak_env_file_when_build_section_absent(
        self, mock_env, mock_docker, tmp_path, monkeypatch
    ) -> None:
        """The guard runs BEFORE the env-file write, so no secret env file leaks on disk.

        Ordering invariant (step 2b before step 10): the env file carries git
        identity and ``task_executor`` secrets and is only unlinked by the
        ``finally`` of the try block — so the None-guard must run before
        ``_write_env_file`` to guarantee the raise cannot leak it.
        """
        self._write_config_without_build(tmp_path)
        with mock.patch.object(_build_mod, "DockerRunner"):
            result = _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        assert result.exit_code == 1
        assert "build section is required" in result.output
        mock_env.assert_not_called()


# --- Negative cases ---


class TestBuildNegativeCases:
    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    def test_build_invalid_goga_config_raises_config_error(self, mock_docker, tmp_path, monkeypatch) -> None:
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
    def test_worktree_forwarded(self, mock_env, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")

        with mock.patch.object(_build_mod, "DockerRunner") as mock_runner:
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md", "--worktree"])

        args = mock_runner.return_value.run.call_args.args[0]
        assert "--worktree" in args

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_session_timeout_forwarded(self, mock_env, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")

        with mock.patch.object(_build_mod, "DockerRunner") as mock_runner:
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md", "--session-timeout", "30m"])

        args = mock_runner.return_value.run.call_args.args[0]
        assert "--session-timeout" in args
        assert "30m" in args

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_skip_finalize_forwarded(self, mock_env, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")

        with mock.patch.object(_build_mod, "DockerRunner") as mock_runner:
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md", "--skip-finalize"])

        args = mock_runner.return_value.run.call_args.args[0]
        assert "--skip-finalize" in args


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
    @mock.patch.object(_build_mod, "_read_git_config")
    def test_git_env_merged_into_env_file(self, mock_git, mock_env, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path, extra={"task_executor": {"agent": "claude", "env": {"API_KEY": "secret"}}})
        mock_git.return_value = {
            "GIT_AUTHOR_NAME": "User",
            "GIT_AUTHOR_EMAIL": "u@e.com",
            "GIT_COMMITTER_NAME": "User",
            "GIT_COMMITTER_EMAIL": "u@e.com",
        }
        mock_env.return_value = Path("/tmp/env")

        with mock.patch.object(_build_mod, "DockerRunner") as mock_runner:
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        call_args = mock_env.call_args
        env_dict = call_args[0][0]
        assert env_dict["API_KEY"] == "secret"
        assert env_dict["GIT_AUTHOR_NAME"] == "User"
        assert env_dict["GIT_COMMITTER_EMAIL"] == "u@e.com"

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    @mock.patch.object(_build_mod, "_read_git_config")
    def test_task_executor_env_has_priority(self, mock_git, mock_env, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path, extra={"task_executor": {"agent": "claude", "env": {"GIT_AUTHOR_NAME": "override"}}})
        mock_git.return_value = {"GIT_AUTHOR_NAME": "GitUser"}
        mock_env.return_value = Path("/tmp/env")

        with mock.patch.object(_build_mod, "DockerRunner") as mock_runner:
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        env_dict = mock_env.call_args[0][0]
        assert env_dict["GIT_AUTHOR_NAME"] == "override"


# --- Image update (--update → docker_update) tests ---


class TestImageUpdateInBuild:
    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_update_called_with_config_image_and_dockerfile(self, mock_env, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path, extra={"image": "custom-image:v2"})
        mock_env.return_value = Path("/tmp/env")

        with (
            mock.patch.object(_build_mod, "docker_update") as mock_update,
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["--update", "plan.md"])

        # dockerfile is None here → docker_update takes the pull branch.
        mock_update.assert_called_once_with("custom-image:v2", None)

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_update_not_called_on_dry_run(self, mock_env, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path)
        mock_env.return_value = Path("/tmp/env")

        with (
            mock.patch.object(_build_mod, "docker_update") as mock_update,
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["--dry-run", "plan.md"])

        mock_update.assert_not_called()

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_pull_failure_warns_and_continues(  # noqa: PLR0913, PLR0917
        self, mock_env, mock_git, mock_docker, tmp_path, monkeypatch, caplog
    ) -> None:
        """A failing `docker pull` (the pull branch of docker_update) is logged as a
        WARNING by the docker cell and the build proceeds to launch.

        Drives a real failing pull through the global `subprocess.run`
        (returncode=1) rather than faking `docker_update`, so the
        warn-and-continue contract is exercised end-to-end. The launch then
        flows through `DockerRunner.run` → `subprocess.Popen` (mocked).
        """
        import logging

        _write_goga_yml(tmp_path, extra={"image": "broken:image"})
        mock_env.return_value = Path("/tmp/env")

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0

        def fake_run(cmd, *args, **kwargs):
            # `docker pull` fails; other docker calls (kill cleanup) succeed.
            if cmd[:2] == ["docker", "pull"]:
                return mock.Mock(returncode=1)
            # resolve_build_runtime_dir shells out to `git branch --show-current`
            # (via resolve_git_branch); answer with empty stdout so it falls
            # back to the "default" branch rather than a Mock object.
            if cmd[:2] == ["git", "branch"]:
                return mock.Mock(returncode=128, stdout="", stderr="")
            return mock.Mock(returncode=0)

        with (
            mock.patch.object(subprocess, "run", side_effect=fake_run),
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            caplog.at_level(logging.WARNING),
        ):
            result = _run_build_in_tmp(tmp_path, monkeypatch, ["--update", "plan.md"])

        # a warning was emitted for the failed pull, and the launch still proceeded
        assert any("failed to pull image" in rec.message for rec in caplog.records)
        mock_popen.assert_called_once()
        assert result.exit_code == 0


# --- Task 6: top-level Config.image contract ---


class TestTopLevelImageContract:
    """Logic tests for goga/commands/build.build reading the top-level Config.image."""

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    def test_build_uses_top_level_config_image(self, mock_git, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path, extra={"image": "qarium/foo:1.0"})

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        cmd = mock_popen.call_args[0][0]
        assert "qarium/foo:1.0" in cmd
        # The removed build.image default must not leak into the command.
        assert "qarium/goga:latest" not in cmd

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config")
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_build_env_file_task_executor_overrides_git(
        self, mock_env, mock_git, mock_docker, tmp_path, monkeypatch
    ) -> None:
        _write_goga_yml(
            tmp_path,
            extra={"task_executor": {"agent": "claude", "env": {"GIT_AUTHOR_NAME": "from-task"}}},
        )
        mock_git.return_value = {"GIT_AUTHOR_NAME": "from-git", "GIT_AUTHOR_EMAIL": "x@y"}
        mock_env.return_value = Path("/tmp/env")

        with mock.patch.object(_build_mod, "DockerRunner") as mock_runner:
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        env_dict = mock_env.call_args[0][0]
        # task_executor env takes precedence over git identity env.
        assert env_dict["GIT_AUTHOR_NAME"] == "from-task"
        assert env_dict["GIT_AUTHOR_EMAIL"] == "x@y"

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    def test_build_mounts_codex_auth_json_when_present(self, mock_git, mock_docker, tmp_path, monkeypatch) -> None:
        fake_home = tmp_path / "home"
        (fake_home / ".codex").mkdir(parents=True)
        (fake_home / ".codex" / "auth.json").write_text("{}")

        _write_goga_yml(tmp_path)
        # resolve_credential_mounts expands ~ via $HOME (not Path.home()), so
        # redirect detection to fake_home.
        monkeypatch.setenv("HOME", str(fake_home))

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(Path, "home", return_value=fake_home),
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        cmd = mock_popen.call_args[0][0]
        assert any(arg.endswith(":/home/goga/.codex/auth.json:ro") for arg in cmd)

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    def test_build_raises_clickexception_when_config_image_is_none(self, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(tmp_path, no_image=True)

        result = _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        assert result.exit_code != 0
        assert "image" in result.output

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_build_image_none_does_not_write_env_file(self, mock_env, mock_docker, tmp_path, monkeypatch) -> None:
        """When image is None, the env file is never written — no secret leak on disk.

        The env file holds git identity plus ``task_executor`` env (potential
        secrets) and is only unlinked by the ``finally`` of the try block in
        ``build``. The ``config.image is None`` check must therefore run before
        ``_write_env_file`` so the raise cannot leak the file (mirrors the
        cleanup guarantee in ``goga.commands.pipeline``).
        """
        _write_goga_yml(tmp_path, no_image=True)

        result = _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        assert result.exit_code != 0
        assert "image" in result.output
        mock_env.assert_not_called()

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_build_works_when_git_config_absent(self, mock_env, mock_git, mock_docker, tmp_path, monkeypatch) -> None:
        _write_goga_yml(
            tmp_path,
            extra={"task_executor": {"agent": "claude", "env": {"FOO": "1"}}},
        )
        mock_env.return_value = Path("/tmp/env")

        with mock.patch.object(_build_mod, "DockerRunner") as mock_runner:
            mock_runner.return_value.run.return_value = 0
            result = _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        assert result.exit_code == 0
        env_dict = mock_env.call_args[0][0]
        # With git config absent, only the task_executor env reaches the file.
        assert env_dict == {"FOO": "1"}
