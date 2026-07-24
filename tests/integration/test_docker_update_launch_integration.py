"""Cross-cell integration tests for ``--update`` + launch delegation and the D7 leak invariant.

These verify the end-to-end wiring across cells that no single-entity unit test
fully covers — the coordination between the host-side command launchers, the
``goga/docker`` cell, and the secret-file writers::

    goga/commands/build|pipeline   (caller — owns host cleanup + the D7 caller handler)
        -> goga/docker             (docker_update acquisition + DockerRunner launch)
        -> secret-file writers     (_write_env_file, _write_afm_config_tmpfile)

The docker cell boundary is stubbed per ``[[feedback_mock_patch_module_shadowing]]``
(the package ``__init__`` re-exports submodule functions, which shadows string-based
``mock.patch`` paths on Python 3.10, so the real modules are resolved via
``__import__(..., fromlist=[...])`` / ``sys.modules`` and patched by attribute).
The secret-file writers are WRAPPED (not stubbed) so the test observes the real
paths they create and can verify the D7 leak-prevention invariant: the secret
files are unlinked on every exit path, including the signal-exit path.

The coverage focus is the cross-cell interaction, not the already unit-tested
docker cell internals:

- ``goga build --update`` with ``dockerfile`` set → ``docker_update`` runs (build
  branch) BEFORE ``DockerRunner.run``; a propagated build exception surfaces as a
  ``ClickException`` (exit 1) and ``DockerRunner.run`` is NOT called; the env-file
  is unlinked.
- ``goga build --update`` with ``dockerfile`` None → ``docker_update`` runs (pull
  branch, non-fatal); ``DockerRunner.run`` runs regardless; env-file unlinked;
  ``.ralphex/`` removed from the project dir.
- D7 invariant: a ``SystemExit(128 + signum)`` raised during the window after the
  env-file write (simulated by making ``docker_update`` raise) unwinds through the
  caller ``finally`` → env-file unlinked + handlers restored; the secret file does
  not leak.
- ``goga pipeline`` discovery + run: ``docker_update`` delegation and
  ``DockerRunner.run`` launch in both modes; run-mode tmpfile + env-file unlinked on
  the signal-exit path; the persistent afm-state dir survives.
"""

from __future__ import annotations

import signal
import subprocess
import sys
from pathlib import Path
from unittest import mock

import click
import pytest
import yaml
from click.testing import CliRunner
from goga.commands import build as build_cmd
from goga.commands.pipeline.run_pipeline_container import (
    run_pipeline_container as rpc,
)
from goga.config import BuildConfig, PipelineConfig, ProjectConfig, TaskExecutorConfig

# Resolve the real submodules via __import__/sys.modules: the package __init__
# binds the function names, which shadow string-based mock.patch paths walking
# through the package on Python 3.10.
_build_mod = __import__("goga.commands.build.build", fromlist=["build"])
_rpc_mod = sys.modules["goga.commands.pipeline.run_pipeline_container"]


def _write_goga_yml(
    tmp_path: Path,
    *,
    image: str = "qarium/goga:latest",
    dockerfile: str | None = None,
) -> None:
    """Write a minimal .goga/config.yml, optionally with a top-level dockerfile."""
    data: dict = {
        "language": "python",
        "image": image,
        "build": {"task_executor": {"agent": "claude"}},
        "pipeline": {"agent": "claude"},
    }
    if dockerfile is not None:
        data["dockerfile"] = dockerfile
    (tmp_path / ".goga").mkdir(parents=True, exist_ok=True)
    (tmp_path / ".goga" / "config.yml").write_text(yaml.dump(data))


def _make_config(
    *,
    image: str = "qarium/goga:latest",
    dockerfile: str | None = None,
    pipeline_agent: str = "claude",
) -> ProjectConfig:
    """Build a minimal ProjectConfig satisfying the schema (top-level image + dockerfile)."""
    return ProjectConfig(
        lang="python",
        image=image,
        dockerfile=dockerfile,
        build=BuildConfig(task_executor=TaskExecutorConfig(agent="claude")),
        pipeline=PipelineConfig(agent=pipeline_agent, env={}),
    )


def _run_build(tmp_path: Path, monkeypatch, args: list[str] | None = None):
    """Invoke the build click command from tmp_path (--skip-manifest-check prepended)."""
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    full_args = ["--skip-manifest-check", *(args or [])]
    return runner.invoke(build_cmd, full_args)


def _track_env_file_writes() -> tuple[list[Path], object]:
    """Wrap the build _write_env_file to record the real env-file paths it creates."""
    created: list[Path] = []
    real_write = _build_mod._write_env_file

    def track_write(env: dict[str, str], extra_env: tuple[str, ...]) -> Path:
        path = real_write(env, extra_env)
        created.append(path)
        return path

    return created, track_write


# ===========================================================================
# build: cross-cell --update + launch delegation
# ===========================================================================


class TestBuildUpdateLaunchIntegration:
    """``goga build --update`` → docker_update → DockerRunner.run → host cleanup."""

    def test_build_update_dockerfile_runs_update_before_launch(self, tmp_path: Path, monkeypatch) -> None:
        """docker_update (build branch) runs BEFORE DockerRunner.run; ordering is cross-cell."""
        _write_goga_yml(tmp_path, dockerfile="Dockerfile")
        monkeypatch.setattr(_build_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_build_mod, "_read_git_config", lambda: {})

        order: list[str] = []

        def fake_update(image: str, dockerfile: str | None, **_kw) -> None:
            order.append("update")
            # dockerfile flows through → the build branch
            assert image == "qarium/goga:latest"
            assert dockerfile == "Dockerfile"

        def fake_run(args: list[str], **params) -> int:
            order.append("launch")
            return 0

        with (
            mock.patch.object(_build_mod, "docker_build_if_not_exist"),
            mock.patch.object(_build_mod, "docker_update", side_effect=fake_update),
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.side_effect = fake_run
            result = _run_build(tmp_path, monkeypatch, ["--update", "plan.md"])

        assert result.exit_code == 0
        # docker_update ran first (build branch), then launch
        assert order == ["update", "launch"]
        # DockerRunner constructed with the config image
        mock_runner.assert_called_once_with("qarium/goga:latest")

    def test_build_update_fatal_build_surfaces_clickexception_and_skips_launch(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """A propagated (fatal) build exception surfaces as ClickException (exit 1),
        DockerRunner.run is NOT called, and the secret env-file is unlinked."""
        _write_goga_yml(tmp_path, dockerfile="Dockerfile")
        monkeypatch.setattr(_build_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_build_mod, "_read_git_config", lambda: {})

        created_env, track_write = _track_env_file_writes()
        monkeypatch.setattr(_build_mod, "_write_env_file", track_write)

        with (
            mock.patch.object(_build_mod, "docker_build_if_not_exist"),
            mock.patch.object(_build_mod, "docker_update", side_effect=RuntimeError("build failed")),
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            result = _run_build(tmp_path, monkeypatch, ["--update", "plan.md"])

        # D5: fatal build surfaces as a clean message + exit 1 (no traceback)
        assert result.exit_code == 1
        assert "build failed" in result.output
        # launch skipped on build failure
        mock_runner.return_value.run.assert_not_called()
        # the secret env-file was created then unlinked (D7 leak prevention)
        assert created_env
        assert all(not p.exists() for p in created_env)

    def test_build_update_pull_branch_launches_and_cleans_env_file_and_ralphex(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """With dockerfile None, docker_update runs (pull branch, non-fatal);
        DockerRunner.run runs regardless; the env-file is unlinked and the
        Docker-created .ralphex/ mount point is removed from the project dir."""
        _write_goga_yml(tmp_path, dockerfile=None)
        monkeypatch.setattr(_build_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_build_mod, "_read_git_config", lambda: {})

        created_env, track_write = _track_env_file_writes()
        monkeypatch.setattr(_build_mod, "_write_env_file", track_write)

        # Pre-create the Docker-created empty .ralphex/ mount point in the project
        # dir; the host cleanup removes it unconditionally on every exit path.
        ralphex_dir = tmp_path / ".ralphex"
        ralphex_dir.mkdir()

        with (
            mock.patch.object(_build_mod, "docker_build_if_not_exist"),
            mock.patch.object(_build_mod, "docker_update") as mock_update,
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            result = _run_build(tmp_path, monkeypatch, ["--update", "plan.md"])

        assert result.exit_code == 0
        # pull branch: docker_update called with (image, None) + home.docker.build
        # extra_args (empty list when the home file is absent — Task 5).
        mock_update.assert_called_once_with("qarium/goga:latest", None, extra_args=[])
        # launch runs regardless of the (non-fatal) pull outcome
        mock_runner.return_value.run.assert_called_once()
        # env-file unlinked
        assert created_env
        assert all(not p.exists() for p in created_env)
        # .ralphex/ removed from the project dir
        assert not ralphex_dir.exists()

    def test_build_signal_during_window_unlinks_env_file_and_restores_handlers(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """D7: a SystemExit(143) raised during the window after the env-file write
        (simulated by making docker_update raise) unwinds through the caller finally
        → env-file unlinked + both handlers restored; the secret file does not leak
        and launch is never reached."""
        _write_goga_yml(tmp_path, dockerfile="Dockerfile")
        monkeypatch.setattr(_build_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_build_mod, "_read_git_config", lambda: {})

        created_env, track_write = _track_env_file_writes()
        monkeypatch.setattr(_build_mod, "_write_env_file", track_write)

        # Pre-create the Docker-created .ralphex/ mount point in the project dir;
        # the CODEMANIFEST forbids it under any exit path, so the caller finally
        # removes it even on the signal-exit path.
        ralphex_dir = tmp_path / ".ralphex"
        ralphex_dir.mkdir()

        # Record signal calls so the restore can be verified (install + restore for
        # both SIGTERM and SIGINT).
        sig_calls: list[tuple[int, object]] = []

        def fake_signal(sig: int, handler: object) -> object:
            sig_calls.append((sig, handler))
            return signal.SIG_DFL

        monkeypatch.setattr(_build_mod.signal, "signal", mock.MagicMock(side_effect=fake_signal))

        with (
            mock.patch.object(_build_mod, "docker_build_if_not_exist"),
            mock.patch.object(_build_mod, "docker_update", side_effect=SystemExit(143)),
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            result = _run_build(tmp_path, monkeypatch, ["--update", "plan.md"])

        # the secret env-file was created then unlinked (no leak)
        assert created_env
        assert all(not p.exists() for p in created_env)
        # launch never reached (the signal aborted before DockerRunner.run)
        mock_runner.return_value.run.assert_not_called()
        # the SystemExit(143) propagated (the 128 + SIGTERM signal-exit code)
        assert isinstance(result.exception, SystemExit)
        assert result.exception.code == 143
        # both handlers restored in the caller finally (install + restore each)
        sigterm = [s for s, _ in sig_calls if s == signal.SIGTERM]
        sigint = [s for s, _ in sig_calls if s == signal.SIGINT]
        assert len(sigterm) == 2
        assert len(sigint) == 2
        # .ralphex/ removed from the project dir even on the signal-exit path
        assert not ralphex_dir.exists()


# ===========================================================================
# pipeline: cross-cell --update + launch delegation (discovery + run)
# ===========================================================================


def _patch_pipeline_common(monkeypatch, runtime_dir: Path) -> object:
    """Stub the docker/subprocess boundary + host helpers shared by both modes.

    Redirects the persistent afm-state dir to ``runtime_dir`` so its survival can
    be observed independently of the project dir. Returns the ``subprocess.run``
    side effect (the runner's guaranteed ``docker kill`` cleanup routes through it).

    Also stubs ``docker_build_if_not_exist`` to a no-op so the existing
    ``--update`` tests are not affected by the first-run safety net (the safety
    net has its own dedicated tests in TestPipelineFirstRunAutoBuildIntegration).
    """
    monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
    monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
    monkeypatch.setattr(_rpc_mod, "resolve_credential_mounts", lambda: [])
    monkeypatch.setattr(_rpc_mod, "resolve_pipeline_runtime_dir", lambda _name: runtime_dir)
    monkeypatch.setattr(_rpc_mod, "docker_build_if_not_exist", lambda *_a, **_k: None)

    def run_side_effect(*args, **kwargs) -> mock.Mock:
        return mock.Mock(returncode=0)

    return run_side_effect


class TestPipelineUpdateLaunchIntegration:
    """``goga pipeline`` → docker_update → DockerRunner.run in both modes."""

    def test_pipeline_discovery_update_delegates_to_docker_update_and_launches(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Discovery mode (name None): docker_update(image, dockerfile) on --update,
        and DockerRunner.run launches the list command (captured via global
        subprocess.Popen, which DockerRunner.run routes through)."""
        config = _make_config(dockerfile=None)
        runtime_dir = tmp_path / "afm-state-discovery"
        patches = _patch_pipeline_common(monkeypatch, runtime_dir)
        monkeypatch.chdir(tmp_path)

        popen_cmds: list[list[str]] = []

        def popen_side_effect(cmd, *args, **kwargs):
            popen_cmds.append(list(cmd))
            mock_proc = mock.Mock()
            mock_proc.wait.return_value = 0
            return mock_proc

        with (
            mock.patch.object(_rpc_mod, "docker_update") as mock_update,
            mock.patch.object(subprocess, "Popen", side_effect=popen_side_effect),
            mock.patch.object(subprocess, "run", side_effect=patches),
        ):
            result = rpc(None, config, update=True)

        assert result == 0
        # pull branch (dockerfile None) — extra_args=home.docker.build (empty when no home file)
        mock_update.assert_called_once_with("qarium/goga:latest", None, extra_args=[])
        # launch happened with the discovery list command, no port/env-file/-p
        assert popen_cmds, "DockerRunner.run never launched the container"
        cmd = popen_cmds[-1]
        assert "goga.pipeline" in cmd
        assert "list" in cmd
        assert "-p" not in cmd
        assert "--env-file" not in cmd
        assert "--workdir" in cmd

    def test_pipeline_run_update_delegates_to_docker_update_and_launches(self, tmp_path: Path, monkeypatch) -> None:
        """Run mode: docker_update(image, dockerfile) on --update (build branch when
        dockerfile set), and DockerRunner.run launches the run command with the port."""
        config = _make_config(dockerfile="Dockerfile")
        runtime_dir = tmp_path / "afm-state-run"
        patches = _patch_pipeline_common(monkeypatch, runtime_dir)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.chdir(tmp_path)

        popen_cmds: list[list[str]] = []

        def popen_side_effect(cmd, *args, **kwargs):
            popen_cmds.append(list(cmd))
            mock_proc = mock.Mock()
            mock_proc.wait.return_value = 0
            return mock_proc

        with (
            mock.patch.object(_rpc_mod, "docker_update") as mock_update,
            mock.patch.object(subprocess, "Popen", side_effect=popen_side_effect),
            mock.patch.object(subprocess, "run", side_effect=patches),
        ):
            result = rpc("deploy", config, update=True)

        assert result == 0
        # build branch (dockerfile set) — extra_args=home.docker.build (empty when no home file)
        mock_update.assert_called_once_with("qarium/goga:latest", "Dockerfile", extra_args=[])
        # launch happened with the run command + port + afm-config mount
        assert popen_cmds, "DockerRunner.run never launched the container"
        cmd = popen_cmds[-1]
        assert "run" in cmd
        assert "deploy" in cmd
        assert "--port" in cmd
        assert "50321" in cmd
        assert any(arg.endswith(":/home/goga/.afm/config.yaml:ro") for arg in cmd)

    def test_pipeline_run_signal_unlinks_secret_files_persistent_dir_survives(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """D7 (run mode): a SystemExit(143) raised after the tmpfile/env-file write
        (simulated by making docker_update raise) unwinds through the caller finally
        → tmpfile + env-file unlinked + handlers restored; the persistent afm-state
        dir survives the signal-exit path."""
        config = _make_config(dockerfile="Dockerfile")
        runtime_dir = tmp_path / "afm-state-survives"
        patches = _patch_pipeline_common(monkeypatch, runtime_dir)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.chdir(tmp_path)

        created_tmp: list[Path] = []
        created_env: list[Path] = []
        real_afm = _rpc_mod._write_afm_config_tmpfile
        real_env = _rpc_mod._write_env_file

        def track_afm(wrapper_path: str) -> Path:
            path = real_afm(wrapper_path)
            created_tmp.append(path)
            return path

        def track_env(env: dict[str, str], extra_env: tuple[str, ...] = ()) -> Path:
            path = real_env(env, extra_env)
            created_env.append(path)
            return path

        monkeypatch.setattr(_rpc_mod, "_write_afm_config_tmpfile", track_afm)
        monkeypatch.setattr(_rpc_mod, "_write_env_file", track_env)

        # Record signal calls so the restore can be verified.
        sig_calls: list[tuple[int, object]] = []

        def fake_signal(sig: int, handler: object) -> object:
            sig_calls.append((sig, handler))
            return signal.SIG_DFL

        monkeypatch.setattr(_rpc_mod.signal, "signal", mock.MagicMock(side_effect=fake_signal))

        with (
            mock.patch.object(_rpc_mod, "docker_update", side_effect=SystemExit(143)),
            mock.patch.object(subprocess, "Popen") as mock_popen,
            mock.patch.object(subprocess, "run", side_effect=patches),
            pytest.raises(SystemExit) as exc,
        ):
            rpc("deploy", config, update=True)

        # the signal-exit code propagated (128 + SIGTERM)
        assert exc.value.code == 143
        # launch never reached (docker_update raised before DockerRunner.run)
        mock_popen.assert_not_called()
        # both secret files were created then unlinked (no leak)
        assert created_tmp
        assert created_env
        assert all(not p.exists() for p in created_tmp)
        assert all(not p.exists() for p in created_env)
        # the persistent afm-state dir survives every exit path
        assert runtime_dir.exists()
        # both handlers restored in the caller finally
        sigterm = [s for s, _ in sig_calls if s == signal.SIGTERM]
        sigint = [s for s, _ in sig_calls if s == signal.SIGINT]
        assert len(sigterm) == 2
        assert len(sigint) == 2

    def test_pipeline_discovery_fatal_build_surfaces_clickexception_and_skips_launch(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """D5 (discovery): a fatal build surfaces as click.ClickException (not a raw
        traceback) and DockerRunner.run is never reached."""
        config = _make_config(dockerfile="Dockerfile")
        runtime_dir = tmp_path / "afm-state-discovery-fatal"
        patches = _patch_pipeline_common(monkeypatch, runtime_dir)
        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(_rpc_mod, "docker_update", side_effect=RuntimeError("pipeline build failed")),
            mock.patch.object(subprocess, "Popen") as mock_popen,
            mock.patch.object(subprocess, "run", side_effect=patches),
            pytest.raises(click.ClickException) as exc,
        ):
            rpc(None, config, update=True)

        assert "pipeline build failed" in exc.value.message
        # launch skipped on build failure
        mock_popen.assert_not_called()

    def test_pipeline_run_fatal_build_surfaces_clickexception_and_skips_launch(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """D5 (run): a fatal build surfaces as click.ClickException (not a raw
        traceback), DockerRunner.run is never reached, and the secret tmpfile +
        env-file are unlinked by the caller finally."""
        config = _make_config(dockerfile="Dockerfile")
        runtime_dir = tmp_path / "afm-state-run-fatal"
        patches = _patch_pipeline_common(monkeypatch, runtime_dir)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.chdir(tmp_path)

        created_tmp: list[Path] = []
        created_env: list[Path] = []
        real_afm = _rpc_mod._write_afm_config_tmpfile
        real_env = _rpc_mod._write_env_file

        def track_afm(wrapper_path: str) -> Path:
            path = real_afm(wrapper_path)
            created_tmp.append(path)
            return path

        def track_env(env: dict[str, str], extra_env: tuple[str, ...] = ()) -> Path:
            path = real_env(env, extra_env)
            created_env.append(path)
            return path

        monkeypatch.setattr(_rpc_mod, "_write_afm_config_tmpfile", track_afm)
        monkeypatch.setattr(_rpc_mod, "_write_env_file", track_env)

        with (
            mock.patch.object(_rpc_mod, "docker_update", side_effect=RuntimeError("pipeline build failed")),
            mock.patch.object(subprocess, "Popen") as mock_popen,
            mock.patch.object(subprocess, "run", side_effect=patches),
            pytest.raises(click.ClickException) as exc,
        ):
            rpc("deploy", config, update=True)

        assert "pipeline build failed" in exc.value.message
        # launch skipped on build failure
        mock_popen.assert_not_called()
        # the secret tmpfile + env-file were created then unlinked (no leak)
        assert created_tmp
        assert created_env
        assert all(not p.exists() for p in created_tmp)
        assert all(not p.exists() for p in created_env)


# ===========================================================================
# build: first-run auto-build via docker_build_if_not_exist (no --update)
# ===========================================================================


class TestBuildFirstRunAutoBuildIntegration:
    """``goga build`` (no --update) auto-builds a missing local image via
    ``docker_build_if_not_exist`` when ``dockerfile`` is declared — the
    first-run safety net that closes the corner case where ``docker run`` would
    otherwise fail with "No such image"."""

    def test_build_without_update_calls_safety_net_with_config_primitives(self, tmp_path: Path, monkeypatch) -> None:
        """No --update + dockerfile set -> docker_build_if_not_exist is called
        unconditionally at launch entry; docker_update is NOT called (still gated
        by --update); launch proceeds normally."""
        _write_goga_yml(tmp_path, dockerfile="Dockerfile")
        monkeypatch.setattr(_build_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_build_mod, "_read_git_config", lambda: {})

        with (
            mock.patch.object(_build_mod, "docker_build_if_not_exist") as mock_ensure,
            mock.patch.object(_build_mod, "docker_update") as mock_update,
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            result = _run_build(tmp_path, monkeypatch, ["plan.md"])  # NO --update

        assert result.exit_code == 0
        # safety net called unconditionally — it decides internally whether to build
        # (home.docker.build extra_args forwarded — empty list when home is absent).
        mock_ensure.assert_called_once_with("qarium/goga:latest", "Dockerfile", extra_args=[])
        # docker_update stays gated by --update (not called here)
        mock_update.assert_not_called()
        # launch proceeded
        mock_runner.return_value.run.assert_called_once()

    def test_build_without_update_calls_safety_net_even_when_dockerfile_none(self, tmp_path: Path, monkeypatch) -> None:
        """No --update + dockerfile None -> safety net still called (it is a no-op
        inside the docker cell when dockerfile is None); docker_update NOT called;
        launch proceeds."""
        _write_goga_yml(tmp_path, dockerfile=None)
        monkeypatch.setattr(_build_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_build_mod, "_read_git_config", lambda: {})

        with (
            mock.patch.object(_build_mod, "docker_build_if_not_exist") as mock_ensure,
            mock.patch.object(_build_mod, "docker_update") as mock_update,
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            result = _run_build(tmp_path, monkeypatch, ["plan.md"])  # NO --update

        assert result.exit_code == 0
        mock_ensure.assert_called_once_with("qarium/goga:latest", None, extra_args=[])
        mock_update.assert_not_called()
        mock_runner.return_value.run.assert_called_once()

    def test_build_with_update_calls_ensure_before_update_before_launch(self, tmp_path: Path, monkeypatch) -> None:
        """--update + dockerfile set -> docker_build_if_not_exist runs FIRST (may
        no-op if the image is present, or build if absent), then docker_update
        (force refresh), then launch. Order: ensure -> update -> launch."""
        _write_goga_yml(tmp_path, dockerfile="Dockerfile")
        monkeypatch.setattr(_build_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_build_mod, "_read_git_config", lambda: {})

        order: list[str] = []

        def ensure_se(*_a, **_kw):
            order.append("ensure")

        def update_se(*_a, **_kw):
            order.append("update")

        with (
            mock.patch.object(_build_mod, "docker_build_if_not_exist", side_effect=ensure_se),
            mock.patch.object(_build_mod, "docker_update", side_effect=update_se),
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.side_effect = lambda *_a, **_k: order.append("launch") or 0
            result = _run_build(tmp_path, monkeypatch, ["--update", "plan.md"])

        assert result.exit_code == 0
        assert order == ["ensure", "update", "launch"]

    def test_build_safety_net_fatal_surfaces_clickexception_skips_update_and_launch(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """A fatal build inside docker_build_if_not_exist surfaces as ClickException
        (exit 1); docker_update is NOT called; DockerRunner.run is NOT called; the
        secret env-file is unlinked (D7 invariant covers the safety-net window —
        it runs inside the try after the env-file write)."""
        _write_goga_yml(tmp_path, dockerfile="Dockerfile")
        monkeypatch.setattr(_build_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_build_mod, "_read_git_config", lambda: {})

        created_env, track_write = _track_env_file_writes()
        monkeypatch.setattr(_build_mod, "_write_env_file", track_write)

        ensure_se = RuntimeError("first-run build failed")

        with (
            mock.patch.object(_build_mod, "docker_build_if_not_exist", side_effect=ensure_se),
            mock.patch.object(_build_mod, "docker_update") as mock_update,
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            result = _run_build(tmp_path, monkeypatch, ["plan.md"])  # NO --update

        # D5: fatal build surfaces as a clean message + exit 1 (no traceback)
        assert result.exit_code == 1
        assert "first-run build failed" in result.output
        # update skipped (ensure raised before reaching the if update: block)
        mock_update.assert_not_called()
        # launch skipped
        mock_runner.return_value.run.assert_not_called()
        # the secret env-file was created then unlinked (D7 leak prevention)
        assert created_env
        assert all(not p.exists() for p in created_env)


# ===========================================================================
# pipeline: first-run auto-build via docker_build_if_not_exist (no --update)
# ===========================================================================


class TestPipelineFirstRunAutoBuildIntegration:
    """``goga pipeline`` (no --update) auto-builds a missing local image via
    ``docker_build_if_not_exist`` in BOTH modes — discovery and run."""

    def test_pipeline_discovery_without_update_calls_safety_net_with_primitives(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Discovery + no --update + dockerfile set -> safety net called; docker_update
        NOT called; launch proceeds with the list command."""
        config = _make_config(dockerfile="Dockerfile")
        runtime_dir = tmp_path / "afm-state-discovery-ensure"
        patches = _patch_pipeline_common(monkeypatch, runtime_dir)
        # Reset docker_build_if_not_exist to a tracking mock — _patch_pipeline_common
        # stubs it to a plain no-op lambda; here we need call assertions.
        monkeypatch.setattr(_rpc_mod, "docker_build_if_not_exist", mock.Mock())
        monkeypatch.setattr(_rpc_mod, "docker_update", mock.Mock())
        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(subprocess, "Popen") as mock_popen,
            mock.patch.object(subprocess, "run", side_effect=patches),
        ):
            mock_popen.return_value.wait.return_value = 0
            result = rpc(None, config, update=False)  # NO --update

        assert result == 0
        _rpc_mod.docker_build_if_not_exist.assert_called_once_with("qarium/goga:latest", "Dockerfile", extra_args=[])
        _rpc_mod.docker_update.assert_not_called()
        # launch happened
        mock_popen.assert_called_once()

    def test_pipeline_run_without_update_calls_safety_net_with_primitives(self, tmp_path: Path, monkeypatch) -> None:
        """Run + no --update + dockerfile set -> safety net called; docker_update
        NOT called; launch proceeds with the run command + port."""
        config = _make_config(dockerfile="Dockerfile")
        runtime_dir = tmp_path / "afm-state-run-ensure"
        patches = _patch_pipeline_common(monkeypatch, runtime_dir)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "docker_build_if_not_exist", mock.Mock())
        monkeypatch.setattr(_rpc_mod, "docker_update", mock.Mock())
        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(subprocess, "Popen") as mock_popen,
            mock.patch.object(subprocess, "run", side_effect=patches),
        ):
            mock_popen.return_value.wait.return_value = 0
            result = rpc("deploy", config, update=False)  # NO --update

        assert result == 0
        _rpc_mod.docker_build_if_not_exist.assert_called_once_with("qarium/goga:latest", "Dockerfile", extra_args=[])
        _rpc_mod.docker_update.assert_not_called()
        mock_popen.assert_called_once()

    def test_pipeline_run_safety_net_fatal_surfaces_clickexception_skips_update_and_launch(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """D5 (run): a fatal build inside docker_build_if_not_exist surfaces as
        click.ClickException (not a raw traceback), docker_update is NOT called,
        DockerRunner.run is NOT reached, and the secret tmpfile + env-file are
        unlinked by the caller finally (D7 covers the safety-net window)."""
        config = _make_config(dockerfile="Dockerfile")
        runtime_dir = tmp_path / "afm-state-run-ensure-fatal"
        patches = _patch_pipeline_common(monkeypatch, runtime_dir)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "docker_update", mock.Mock())
        monkeypatch.chdir(tmp_path)

        created_tmp: list[Path] = []
        created_env: list[Path] = []
        real_afm = _rpc_mod._write_afm_config_tmpfile
        real_env = _rpc_mod._write_env_file

        def track_afm(wrapper_path: str) -> Path:
            path = real_afm(wrapper_path)
            created_tmp.append(path)
            return path

        def track_env(env: dict[str, str], extra_env: tuple[str, ...] = ()) -> Path:
            path = real_env(env, extra_env)
            created_env.append(path)
            return path

        monkeypatch.setattr(_rpc_mod, "_write_afm_config_tmpfile", track_afm)
        monkeypatch.setattr(_rpc_mod, "_write_env_file", track_env)

        ensure_se = RuntimeError("first-run build failed")

        with (
            mock.patch.object(_rpc_mod, "docker_build_if_not_exist", side_effect=ensure_se),
            mock.patch.object(subprocess, "Popen") as mock_popen,
            mock.patch.object(subprocess, "run", side_effect=patches),
            pytest.raises(click.ClickException) as exc,
        ):
            rpc("deploy", config, update=False)  # NO --update

        assert "first-run build failed" in exc.value.message
        # update skipped (ensure raised before reaching the if update: block)
        _rpc_mod.docker_update.assert_not_called()
        # launch skipped
        mock_popen.assert_not_called()
        # the secret tmpfile + env-file were created then unlinked (D7 leak prevention)
        assert created_tmp
        assert created_env
        assert all(not p.exists() for p in created_tmp)
        assert all(not p.exists() for p in created_env)
