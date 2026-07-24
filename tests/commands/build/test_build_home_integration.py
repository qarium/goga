"""Contract and logic tests for home-config integration in ``goga/commands/build``.

Covers Task 5 of the add-project-name-and-home-config plan: the
``load_home_config`` preamble, ``home.env`` as the lowest-priority env layer,
and ``home.docker.run`` / ``home.docker.build`` forwarded as a separate
``extra_args`` keyword to the docker run / image-build surfaces.

The ``_isolate_home`` autouse fixture (``tests/conftest.py``) redirects HOME to
a tmp dir, so ``Path.home()`` resolves there and ``load_home_config()`` (the
real loader, exercised end-to-end here) reads a home file written under it.
"""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import yaml
from click.testing import CliRunner
from goga.commands import build as build_cmd
from goga.config import HomeConfig

_build_mod = __import__("goga.commands.build.build", fromlist=["build"])


def _write_project_yml(
    tmp_path: Path,
    *,
    task_executor_env: dict[str, str] | None = None,
    dockerfile: str | None = None,
) -> None:
    """Write a minimal .goga/config.yml, optionally with task_executor.env/dockerfile."""
    data: dict = {
        "language": "python",
        "image": "qarium/goga:latest",
        "build": {"task_executor": {"agent": "claude"}},
        "pipeline": {"agent": "claude"},
    }
    if task_executor_env is not None:
        data["build"]["task_executor"]["env"] = task_executor_env
    if dockerfile is not None:
        data["dockerfile"] = dockerfile
    (tmp_path / ".goga").mkdir(exist_ok=True)
    (tmp_path / ".goga" / "config.yml").write_text(yaml.dump(data))


def _write_home_yml(home: Path, data: dict) -> None:
    """Write ~/.goga/config.yml under the given home root."""
    goga = home / ".goga"
    goga.mkdir(parents=True, exist_ok=True)
    (goga / "config.yml").write_text(yaml.dump(data))


def _run_build_in_tmp(tmp_path, monkeypatch, args=None, *, skip_manifest_check=True):
    """Run the build command from tmp_path (cwd relocated for load_project_config)."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    full_args = list(args or [])
    if skip_manifest_check:
        full_args = ["--skip-manifest-check", *full_args]
    return runner.invoke(build_cmd, full_args)


# --- Contract tests ---


class TestBuildHomeIntegrationContract:
    def test_build_imports_load_home_config(self) -> None:
        from goga.config import load_home_config

        assert _build_mod.load_home_config is load_home_config

    def test_build_imports_home_config(self) -> None:
        assert _build_mod.HomeConfig is HomeConfig

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    @mock.patch.object(_build_mod, "_write_env_file", return_value=Path("/tmp/env"))
    def test_extra_args_forwarded_as_separate_keyword(
        self, mock_env, mock_git, mock_docker, tmp_path, monkeypatch
    ) -> None:
        """The extra_args channel reaches DockerRunner.run as a separate keyword
        (captured via the run call kwargs), not folded into ``params``."""
        _write_project_yml(tmp_path)
        _write_home_yml(Path.home(), {"docker": {"run": ["--network=host"]}})

        with (
            mock.patch.object(_build_mod, "docker_build_if_not_exist"),
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        run_kwargs = mock_runner.return_value.run.call_args.kwargs
        # extra_args is a SEPARATE keyword, not inside the unpacked params map —
        # the standard params (name, rm, env_file, ...) remain independent keys.
        assert run_kwargs["extra_args"] == ["--network=host"]
        assert "name" in run_kwargs


# --- Logic tests ---


class TestHomeEnvLayering:
    """home.env is the lowest-priority layer: project config wins on conflict,
    home.env survives where unconflicted."""

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_build_command_layers_home_env_as_base(
        self, mock_env, mock_git, mock_docker, tmp_path, monkeypatch
    ) -> None:
        _write_project_yml(tmp_path, task_executor_env={"API_KEY": "proj"})
        _write_home_yml(Path.home(), {"env": {"API_KEY": "home", "EXTRA": "home"}})
        mock_env.return_value = Path("/tmp/env")

        with (
            mock.patch.object(_build_mod, "docker_build_if_not_exist"),
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        env_dict = mock_env.call_args[0][0]
        # Project task_executor env wins on key conflict.
        assert env_dict["API_KEY"] == "proj"
        # home.env survives where unconflicted (it is the base layer).
        assert env_dict["EXTRA"] == "home"


class TestExtraArgsForwarding:
    """home.docker.run → DockerRunner.run extra_args; home.docker.build → image build."""

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    @mock.patch.object(_build_mod, "_write_env_file", return_value=Path("/tmp/env"))
    def test_build_forwards_home_docker_run_and_build_as_extra_args(
        self, mock_env, mock_git, mock_docker, tmp_path, monkeypatch
    ) -> None:
        _write_project_yml(tmp_path, dockerfile="Dockerfile")
        _write_home_yml(
            Path.home(),
            {"docker": {"run": ["--network=host"], "build": ["--squash"]}},
        )

        with (
            mock.patch.object(_build_mod, "docker_build_if_not_exist") as mock_build,
            mock.patch.object(_build_mod, "docker_update") as mock_update,
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["--update", "plan.md"])

        # Build tokens reach the image-build surfaces (build branch only).
        mock_build.assert_called_once_with("qarium/goga:latest", "Dockerfile", extra_args=["--squash"])
        mock_update.assert_called_once_with("qarium/goga:latest", "Dockerfile", extra_args=["--squash"])
        # Run tokens reach DockerRunner.run as a SEPARATE keyword.
        run_kwargs = mock_runner.return_value.run.call_args.kwargs
        assert run_kwargs["extra_args"] == ["--network=host"]
        # extra_args is never translated to an --extra-args flag inside params:
        # it is a top-level kwarg alongside the unpacked params keys.
        assert "name" in run_kwargs
        assert "env_file" in run_kwargs

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    @mock.patch.object(_build_mod, "_write_env_file", return_value=Path("/tmp/env"))
    def test_build_absent_home_file_is_noop(self, mock_env, mock_git, mock_docker, tmp_path, monkeypatch) -> None:
        """An absent home file yields an empty HomeConfig — extra_args is [] and
        home.env adds nothing (no effect, pre-refactor behavior preserved)."""
        _write_project_yml(tmp_path)
        # No home file written under the isolated HOME.

        with (
            mock.patch.object(_build_mod, "docker_build_if_not_exist") as mock_build,
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        mock_build.assert_called_once_with("qarium/goga:latest", None, extra_args=[])
        assert mock_runner.return_value.run.call_args.kwargs["extra_args"] == []


class TestHomeDoesNotOverrideProjectOrCli:
    """home.env is the base layer — CLI -e (a separate raw channel) still wins."""

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    @mock.patch.object(_build_mod, "_read_git_config", return_value={})
    @mock.patch.object(_build_mod, "_write_env_file")
    def test_cli_extra_env_wins_over_home_env(self, mock_env, mock_git, mock_docker, tmp_path, monkeypatch) -> None:
        """CLI ``-e KEY=VALUE`` is appended verbatim AFTER the env-file body, so it
        wins on key conflict even over a home.env base layer with the same key."""
        _write_project_yml(tmp_path)
        _write_home_yml(Path.home(), {"env": {"SHARED": "home"}})

        captured: dict = {}

        def _fake_write_env(env, extra_env):
            captured["env"] = dict(env)
            captured["extra"] = tuple(extra_env)
            return Path("/tmp/env")

        mock_env.side_effect = _fake_write_env

        with (
            mock.patch.object(_build_mod, "docker_build_if_not_exist"),
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(
                tmp_path,
                monkeypatch,
                ["-e", "SHARED=cli", "plan.md"],
            )

        # home.env reaches the env-file body as the base layer.
        assert captured["env"]["SHARED"] == "home"
        # CLI -e is a SEPARATE raw channel appended last — wins on conflict.
        assert "SHARED=cli" in captured["extra"]


class TestMalformedHomeConfigSurfacesCleanClickException:
    """A malformed ``~/.goga/config.yml`` surfaces as a clean ClickException
    (exit 1), not an uncaught traceback — the launcher wraps the loader's
    ``(ValueError, yaml.YAMLError)`` per the click-wrapping convention."""

    @mock.patch.object(_build_mod, "_check_docker", return_value=True)
    def test_malformed_home_file_raises_click_exception(self, mock_docker, tmp_path, monkeypatch) -> None:
        home_goga = Path.home() / ".goga"
        home_goga.mkdir(parents=True, exist_ok=True)
        (home_goga / "config.yml").write_text("- not a mapping\n")

        with mock.patch.object(_build_mod, "DockerRunner") as mock_runner:
            result = _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        assert result.exit_code == 1
        assert "must be a YAML mapping" in result.output
        # The home preamble fails before any docker run — no side effect.
        mock_runner.assert_not_called()
