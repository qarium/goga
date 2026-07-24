"""Contract and logic tests for home-config integration in the pipeline launcher.

Covers Task 6 of the add-project-name-and-home-config plan: the
``load_home_config`` preamble, ``home.env`` as the lowest-priority env layer in
RUN mode only (discovery writes no env-file), and ``home.docker.run`` forwarded
to every ``DockerRunner.run`` as a separate ``extra_args`` keyword in BOTH
modes. ``home.docker.build`` is NOT forwarded by this launcher (build-token
forwarding is ``goga/commands/build`` only).

The ``_isolate_home`` autouse fixture (``tests/conftest.py``) redirects HOME to
a tmp dir, so ``Path.home()`` resolves there and ``load_home_config()`` (the
real loader, exercised end-to-end here) reads a home file written under it.

The dispatch target (``DockerRunner.run``) is mocked so the ``extra_args``
keyword can be captured directly, and ``docker_build_if_not_exist`` /
``docker_update`` are mocked so no real docker/subprocess runs.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import yaml
from goga.commands.pipeline.run_pipeline_container import run_pipeline_container as rpc
from goga.config import BuildConfig, HomeConfig, PipelineConfig, ProjectConfig, TaskExecutorConfig

# Resolve the real submodule via sys.modules (the package __init__ binds the
# function name `run_pipeline_container`, which would shadow string-based
# mock.patch paths walking through the package on Python 3.10).
_rpc_mod = sys.modules["goga.commands.pipeline.run_pipeline_container"]


def _make_config(
    *,
    pipeline_env: dict[str, str] | None = None,
    dockerfile: str | None = None,
) -> ProjectConfig:
    """Build a minimal ProjectConfig with a pipeline section for run-mode dispatch."""
    return ProjectConfig(
        lang="python",
        image="qarium/goga:latest",
        dockerfile=dockerfile,
        build=BuildConfig(task_executor=TaskExecutorConfig(agent="claude")),
        pipeline=PipelineConfig(agent="claude", env=pipeline_env or {}),
    )


def _write_home_yml(home: Path, data: dict) -> None:
    """Write ~/.goga/config.yml under the given home root."""
    goga = home / ".goga"
    goga.mkdir(parents=True, exist_ok=True)
    (goga / "config.yml").write_text(yaml.dump(data))


# --- Contract tests ---


class TestPipelineHomeIntegrationContract:
    def test_launcher_imports_load_home_config(self) -> None:
        from goga.config import load_home_config

        assert _rpc_mod.load_home_config is load_home_config

    def test_launcher_imports_home_config(self) -> None:
        assert _rpc_mod.HomeConfig is HomeConfig

    @mock.patch.object(_rpc_mod, "docker_build_if_not_exist")
    @mock.patch.object(_rpc_mod, "DockerRunner")
    def test_discovery_forwards_extra_args_as_separate_keyword(
        self, mock_runner, mock_build, tmp_path: Path, monkeypatch
    ) -> None:
        """Discovery forwards ``home.docker.run`` to DockerRunner.run as a SEPARATE
        keyword (captured via the run call kwargs), not folded into ``params``."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.chdir(tmp_path)
        _write_home_yml(Path.home(), {"docker": {"run": ["--network=host"]}})
        mock_runner.return_value.run.return_value = 0

        rpc(None, config)

        run_kwargs = mock_runner.return_value.run.call_args.kwargs
        assert run_kwargs["extra_args"] == ["--network=host"]
        # extra_args is a SEPARATE keyword, not inside the unpacked params map —
        # the standard params (name, rm, ...) remain independent keys.
        assert "name" in run_kwargs
        assert "rm" in run_kwargs

    @mock.patch.object(_rpc_mod, "docker_build_if_not_exist")
    @mock.patch.object(_rpc_mod, "DockerRunner")
    def test_run_forwards_extra_args_as_separate_keyword(
        self, mock_runner, mock_build, tmp_path: Path, monkeypatch
    ) -> None:
        """Run mode forwards ``home.docker.run`` to DockerRunner.run as a SEPARATE
        keyword (captured via the run call kwargs)."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)
        _write_home_yml(Path.home(), {"docker": {"run": ["--network=host"]}})
        mock_runner.return_value.run.return_value = 0

        rpc("deploy", config)

        run_kwargs = mock_runner.return_value.run.call_args.kwargs
        assert run_kwargs["extra_args"] == ["--network=host"]
        assert "name" in run_kwargs
        assert "env_file" in run_kwargs


# --- Logic tests ---


class TestDiscoveryHomeDockerRunOnly:
    """Discovery forwards home.docker.run (extra_args) and applies NO home.env
    (no env-file is written)."""

    @mock.patch.object(_rpc_mod, "_write_env_file")
    @mock.patch.object(_rpc_mod, "docker_build_if_not_exist")
    @mock.patch.object(_rpc_mod, "DockerRunner")
    def test_discovery_forwards_home_docker_run_and_writes_no_env_file(
        self, mock_runner, mock_build, mock_env_write, tmp_path: Path, monkeypatch
    ) -> None:
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.chdir(tmp_path)
        _write_home_yml(
            Path.home(),
            {"env": {"SHOULD_NOT_APPEAR": "1"}, "docker": {"run": ["--network=host"]}},
        )
        mock_runner.return_value.run.return_value = 0

        rpc(None, config)

        # home.docker.run reaches DockerRunner.run as a SEPARATE keyword.
        run_kwargs = mock_runner.return_value.run.call_args.kwargs
        assert run_kwargs["extra_args"] == ["--network=host"]
        # Discovery writes NO env-file, so home.env does NOT apply here.
        mock_env_write.assert_not_called()


class TestRunModeHomeEnvBaseLayer:
    """Run mode layers home.env as the lowest-priority env layer (project +
    CLI win on key conflict) and forwards home.docker.run as a separate keyword."""

    @mock.patch.object(_rpc_mod, "docker_build_if_not_exist")
    @mock.patch.object(_rpc_mod, "DockerRunner")
    def test_run_mode_layers_home_env_as_base(self, mock_runner, mock_build, tmp_path: Path, monkeypatch) -> None:
        config = _make_config(pipeline_env={"API_KEY": "proj"})
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)
        _write_home_yml(
            Path.home(),
            {"env": {"API_KEY": "home", "EXTRA": "home"}, "docker": {"run": ["--network=host"]}},
        )
        mock_runner.return_value.run.return_value = 0

        captured_env: dict[str, str] = {}
        real_write = _rpc_mod._write_env_file

        def capture(env: dict[str, str], extra_env: tuple[str, ...] = ()) -> Path:
            captured_env.update(env)
            return real_write(env, extra_env)

        monkeypatch.setattr(_rpc_mod, "_write_env_file", capture)

        rpc("deploy", config)

        # Project pipeline.env wins over home.env on key conflict.
        assert captured_env["API_KEY"] == "proj"
        # home.env survives where unconflicted (it is the base layer).
        assert captured_env["EXTRA"] == "home"
        # home.docker.run reaches DockerRunner.run as a SEPARATE keyword.
        run_kwargs = mock_runner.return_value.run.call_args.kwargs
        assert run_kwargs["extra_args"] == ["--network=host"]

    @mock.patch.object(_rpc_mod, "docker_build_if_not_exist")
    @mock.patch.object(_rpc_mod, "DockerRunner")
    def test_cli_extra_env_channel_is_separate_from_home_env_base(
        self, mock_runner, mock_build, tmp_path: Path, monkeypatch
    ) -> None:
        """CLI ``-e KEY=VALUE`` is a SEPARATE raw channel appended last to the
        env-file, so it wins on key conflict even over a home.env base layer with
        the same key (home.env reaches the env-file body as the base layer)."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)
        _write_home_yml(Path.home(), {"env": {"SHARED": "home"}})
        mock_runner.return_value.run.return_value = 0

        captured: dict[str, object] = {}
        real_write = _rpc_mod._write_env_file

        def capture(env: dict[str, str], extra_env: tuple[str, ...] = ()) -> Path:
            captured["env"] = dict(env)
            captured["extra_env"] = extra_env
            return real_write(env, extra_env)

        monkeypatch.setattr(_rpc_mod, "_write_env_file", capture)

        rpc("deploy", config, ("SHARED=cli",))

        # home.env reaches the env-file body as the base layer (AFM_DIR is also
        # present, always added by _build_env_file — not relevant here).
        assert captured["env"]["SHARED"] == "home"
        # CLI -e is a SEPARATE raw channel appended last — wins on conflict.
        assert captured["extra_env"] == ("SHARED=cli",)


class TestPipelineDoesNotForwardHomeDockerBuild:
    """The pipeline launcher forwards home.docker.run only — home.docker.build
    is NOT forwarded to docker_build_if_not_exist / docker_update (that is
    goga/commands/build's job)."""

    @mock.patch.object(_rpc_mod, "docker_build_if_not_exist")
    @mock.patch.object(_rpc_mod, "docker_update")
    @mock.patch.object(_rpc_mod, "DockerRunner")
    def test_pipeline_does_not_forward_home_docker_build(
        self, mock_runner, mock_update, mock_build, tmp_path: Path, monkeypatch
    ) -> None:
        config = _make_config(dockerfile="Dockerfile")
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)
        _write_home_yml(
            Path.home(),
            {"docker": {"run": ["--network=host"], "build": ["--squash"]}},
        )
        mock_runner.return_value.run.return_value = 0

        rpc("deploy", config, update=True)

        # docker_build_if_not_exist / docker_update receive NO extra_args (the
        # pipeline launcher forwards build tokens to neither).
        _, kwargs = mock_build.call_args
        assert "extra_args" not in kwargs
        _, kwargs = mock_update.call_args
        assert "extra_args" not in kwargs


class TestPipelineAbsentHomeIsNoop:
    """An absent home file yields an empty HomeConfig — extra_args is [] and
    home.env adds nothing (no effect, pre-refactor behavior preserved)."""

    @mock.patch.object(_rpc_mod, "docker_build_if_not_exist")
    @mock.patch.object(_rpc_mod, "DockerRunner")
    def test_absent_home_file_yields_empty_extra_args_in_both_modes(
        self, mock_runner, mock_build, tmp_path: Path, monkeypatch
    ) -> None:
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)
        # No home file written under the isolated HOME.
        mock_runner.return_value.run.return_value = 0

        rpc(None, config)
        discovery_kwargs = mock_runner.return_value.run.call_args.kwargs
        assert discovery_kwargs["extra_args"] == []

        rpc("deploy", config)
        run_kwargs = mock_runner.return_value.run.call_args.kwargs
        assert run_kwargs["extra_args"] == []
