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

from collections.abc import Iterator
from pathlib import Path
from typing import NamedTuple
from unittest import mock

import pytest
from click.testing import CliRunner
from goga.commands import build as build_cmd
from goga.config import HomeConfig
from goga.docker import decode_extra_env

_build_mod = __import__("goga.commands.build.build", fromlist=["build"])


def _run_build_in_tmp(tmp_path, monkeypatch, args=None, *, skip_manifest_check=True):
    """Run the build command from tmp_path (cwd relocated for load_project_config)."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    full_args = list(args or [])
    if skip_manifest_check:
        full_args = ["--skip-manifest-check", *full_args]
    return runner.invoke(build_cmd, full_args)


class _BuildBoundary(NamedTuple):
    """The three process-boundary mocks every home scenario patches identically."""

    docker: mock.Mock
    git: mock.Mock
    env: mock.Mock


@pytest.fixture
def build_boundary() -> Iterator[_BuildBoundary]:
    """Patch the build command's process boundary for one home scenario.

    The docker check (daemon reachable), the git-config read (empty), and the
    env-file writer (captured) are patched exactly as the decorator stack this
    fixture replaces; bundling the three into one fixture keeps the scenario
    signatures within the argument budget.
    """
    with (
        mock.patch.object(_build_mod, "_check_docker", return_value=True) as mock_docker,
        mock.patch.object(_build_mod, "_read_git_config", return_value={}) as mock_git,
        mock.patch.object(_build_mod, "_write_env_file") as mock_env,
    ):
        yield _BuildBoundary(docker=mock_docker, git=mock_git, env=mock_env)


# --- Contract tests ---


class TestBuildHomeIntegrationContract:
    def test_build_imports_load_home_config(self) -> None:
        from goga.config import load_home_config

        assert _build_mod.load_home_config is load_home_config

    def test_build_imports_home_config(self) -> None:
        assert _build_mod.HomeConfig is HomeConfig

    def test_extra_args_forwarded_as_separate_keyword(
        self,
        tmp_path,
        monkeypatch,
        write_goga_config,
        write_home_config,
        build_boundary: _BuildBoundary,
    ) -> None:
        """The extra_args channel reaches DockerRunner.run as a separate keyword
        (captured via the run call kwargs), not folded into ``params``."""
        build_boundary.env.return_value = tmp_path / "env"
        write_goga_config()
        write_home_config({"docker": {"run": ["--network=host"]}})

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
    """home.env is the env-file base layer; the task env (build.env) never
    joins it — build.env reaches the container through the mounted config and
    is applied in-container as the tasks-pass layer."""

    def test_build_command_layers_home_env_as_base(
        self,
        tmp_path,
        monkeypatch,
        write_goga_config,
        write_home_config,
        build_boundary: _BuildBoundary,
    ) -> None:
        write_goga_config(build_env={"API_KEY": "proj"})
        write_home_config({"env": {"API_KEY": "home", "EXTRA": "home"}})
        build_boundary.env.return_value = tmp_path / "env"

        with (
            mock.patch.object(_build_mod, "docker_build_if_not_exist"),
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            _run_build_in_tmp(tmp_path, monkeypatch, ["plan.md"])

        lines = build_boundary.env.call_args[0][0]
        # home.env is the env-file base layer — the project task env (build.env)
        # is NOT written into the file (secret boundary; in-container layer).
        assert "API_KEY=home" in lines
        assert "EXTRA=home" in lines
        assert not any("proj" in line for line in lines)


class TestExtraArgsForwarding:
    """home.docker.run → DockerRunner.run extra_args; home.docker.build → image build."""

    def test_build_forwards_home_docker_run_and_build_as_extra_args(
        self,
        tmp_path,
        monkeypatch,
        write_goga_config,
        write_home_config,
        build_boundary: _BuildBoundary,
    ) -> None:
        build_boundary.env.return_value = tmp_path / "env"
        write_goga_config(dockerfile="Dockerfile")
        write_home_config({"docker": {"run": ["--network=host"], "build": ["--squash"]}})

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

    def test_build_absent_home_file_is_noop(
        self,
        tmp_path,
        monkeypatch,
        write_goga_config,
        build_boundary: _BuildBoundary,
    ) -> None:
        """An absent home file yields an empty HomeConfig — extra_args is [] and
        home.env adds nothing (no effect, pre-refactor behavior preserved)."""
        build_boundary.env.return_value = tmp_path / "env"
        write_goga_config()
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

    def test_cli_extra_env_wins_over_home_env(
        self,
        tmp_path,
        monkeypatch,
        write_goga_config,
        write_home_config,
        build_boundary: _BuildBoundary,
    ) -> None:
        """CLI ``-e KEY=VALUE`` is appended verbatim AFTER the env-file body, so it
        wins on key conflict even over a home.env base layer with the same key."""
        write_goga_config()
        write_home_config({"env": {"SHARED": "home"}})

        captured: dict = {}

        def _fake_write_env(lines):
            captured["lines"] = list(lines)
            return tmp_path / "env"

        build_boundary.env.side_effect = _fake_write_env

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

        # home.env reaches the env-file as the base layer ...
        assert "SHARED=home" in captured["lines"]
        # ... and the CLI -e line lands after it — wins on conflict under
        # docker's last-write-wins. The payload carries the same parsed value.
        assert "SHARED=cli" in captured["lines"]
        assert captured["lines"].index("SHARED=cli") > captured["lines"].index("SHARED=home")
        payload = next(line for line in captured["lines"] if line.startswith("GOGA_EXTRA_ENV="))
        assert decode_extra_env(payload.partition("=")[2]) == {"SHARED": "cli"}


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
