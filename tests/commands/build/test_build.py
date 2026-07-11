"""Contract and logic tests for ``goga/commands/build`` runtime isolation.

Covers the ``--clean`` flag, the ``resolve_build_runtime_dir`` /
``clean_build_runtime_dir`` facades, and the nested bind-mount at
``/workspace/.ralphex`` — the contract added in the ralphex-runtime-isolation
design (Task 3).
"""

from __future__ import annotations

import inspect
import subprocess
import typing
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner
from goga.commands import build as build_cmd
from goga.commands.build.build import (
    _cleanup_ralphex_in_project,
    clean_build_runtime_dir,
    resolve_build_runtime_dir,
)
from goga.config import BuildConfig, Config, PipelineConfig, TaskExecutorConfig

_build_mod = __import__("goga.commands.build.build", fromlist=["build"])


def _valid_config(*, image: str | None = "qarium/goga:latest") -> Config:
    """Return a minimal valid Config for the build flow."""
    return Config(
        lang="python",
        image=image,
        dockerfile=None,
        build=BuildConfig(task_executor=TaskExecutorConfig(agent="claude")),
        pipeline=PipelineConfig(agent="claude"),
    )


# --- Contract tests ---


class TestBuildRuntimeIsolationContract:
    def test_facade_imports_succeed(self) -> None:
        from goga.commands.build.build import build, clean_build_runtime_dir, resolve_build_runtime_dir

        assert build is not None
        assert callable(resolve_build_runtime_dir)
        assert callable(clean_build_runtime_dir)

    def test_build_signature_includes_clean_param(self) -> None:
        sig = inspect.signature(build_cmd.callback)
        assert "clean" in sig.parameters
        hints = typing.get_type_hints(build_cmd.callback)
        assert hints["clean"] is bool

    def test_build_has_clean_option(self) -> None:
        clean_param = next(p for p in build_cmd.params if p.name == "clean")
        assert clean_param.is_flag is True
        assert clean_param.default is False
        assert "--clean" in clean_param.opts

    def test_resolve_build_runtime_dir_signature(self) -> None:
        sig = inspect.signature(resolve_build_runtime_dir)
        assert list(sig.parameters) == []
        hints = typing.get_type_hints(resolve_build_runtime_dir)
        assert hints["return"] is Path

    def test_clean_build_runtime_dir_signature(self) -> None:
        sig = inspect.signature(clean_build_runtime_dir)
        assert list(sig.parameters) == ["host_dir"]
        hints = typing.get_type_hints(clean_build_runtime_dir)
        assert hints["host_dir"] is Path
        assert hints["return"] in (None, type(None))

    def test_resolve_build_runtime_dir_delegates_to_builds_no_suffix(self) -> None:
        with mock.patch.object(_build_mod, "resolve_runtime_dir") as mock_rrd:
            mock_rrd.return_value = Path("/fake/builds/path")
            result = resolve_build_runtime_dir()
        assert result == Path("/fake/builds/path")
        assert mock_rrd.call_args == mock.call("builds")

    def test_clean_build_runtime_dir_idempotent_on_empty_dir(self, tmp_path: Path) -> None:
        host_dir = tmp_path / "rt"
        host_dir.mkdir()
        clean_build_runtime_dir(host_dir)  # no exception
        clean_build_runtime_dir(host_dir)  # idempotent — still no exception
        assert host_dir.exists()


# --- Logic tests (positive) ---


class TestResolveBuildRuntimeDir:
    def test_delegates_without_suffix(self) -> None:
        with mock.patch.object(_build_mod, "resolve_runtime_dir") as mock_rrd:
            mock_rrd.return_value = Path("/fake/builds/path")
            result = resolve_build_runtime_dir()
        assert result == Path("/fake/builds/path")
        assert mock_rrd.call_args == mock.call("builds")


class TestCleanBuildRuntimeDir:
    def test_wipes_and_recreates(self, tmp_path: Path) -> None:
        host_dir = tmp_path / "rt"
        host_dir.mkdir()
        (host_dir / "a.txt").write_text("a")
        (host_dir / "sub").mkdir()
        (host_dir / "sub" / "b.txt").write_text("b")

        clean_build_runtime_dir(host_dir)

        assert host_dir.exists()
        assert list(host_dir.iterdir()) == []

    def test_idempotent_on_empty_dir(self, tmp_path: Path) -> None:
        host_dir = tmp_path / "rt"
        host_dir.mkdir()
        clean_build_runtime_dir(host_dir)
        clean_build_runtime_dir(host_dir)
        assert host_dir.exists()

    def test_creates_when_absent(self, tmp_path: Path) -> None:
        host_dir = tmp_path / "rt"
        assert not host_dir.exists()
        clean_build_runtime_dir(host_dir)
        assert host_dir.exists()

    def test_propagates_partial_removal_failure(self, tmp_path: Path) -> None:
        # The wipe is total per the CODEMANIFEST constraint: a partial-removal
        # failure (e.g. a file written under a different UID by a prior container
        # run) must surface, not be silently swallowed into a stale mount.
        host_dir = tmp_path / "rt"
        host_dir.mkdir()
        (host_dir / "locked.txt").write_text("stale")
        with (
            mock.patch.object(_build_mod.shutil, "rmtree", side_effect=PermissionError("denied")),
            pytest.raises(PermissionError),
        ):
            clean_build_runtime_dir(host_dir)

    def test_tolerates_concurrent_removal(self, tmp_path: Path) -> None:
        # A directory that vanishes between the existence check and rmtree
        # (a concurrent --clean) is tolerated; the dir is recreated.
        host_dir = tmp_path / "rt"
        host_dir.mkdir()
        with mock.patch.object(_build_mod.shutil, "rmtree", side_effect=FileNotFoundError):
            clean_build_runtime_dir(host_dir)  # does not raise
        assert host_dir.exists()


# --- Logic tests: build command runtime isolation flow ---


class TestBuildRuntimeIsolationFlow:
    def test_build_clean_flag_wipes_runtime_dir_before_launch(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        # Pin the git branch so the runtime path is deterministic regardless of
        # subprocess mocking (resolve_git_branch normally shells out to git).
        monkeypatch.setattr("goga.runtime.paths.resolve_git_branch", lambda: "test-branch")

        runtime_dir = resolve_build_runtime_dir()
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "old-state.json").write_text("{}")

        captured: dict = {}

        def _fake_popen(cmd, *args, **kwargs):
            captured["cmd"] = list(cmd)
            proc = mock.Mock()
            proc.wait.return_value = 0
            return proc

        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "_read_git_config", return_value={}),
            mock.patch.object(_build_mod, "load_config", return_value=_valid_config()),
            mock.patch.object(_build_mod, "resolve_credential_mounts", return_value=[]),
            mock.patch.object(_build_mod, "_write_env_file", return_value=tmp_path / "env"),
            mock.patch.object(subprocess, "Popen", side_effect=_fake_popen),
            mock.patch.object(subprocess, "run"),
        ):
            result = CliRunner().invoke(build_cmd, ["plan.md", "--clean"])

        assert result.exit_code == 0, result.output
        assert not (runtime_dir / "old-state.json").exists()
        cmd = captured["cmd"]
        assert "-v" in cmd
        assert any(arg.endswith(":/workspace/.ralphex") for arg in cmd)

    def test_build_without_clean_preserves_runtime_dir(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        monkeypatch.setattr("goga.runtime.paths.resolve_git_branch", lambda: "test-branch")

        runtime_dir = resolve_build_runtime_dir()
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "progress.json").write_text("{}")

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "_read_git_config", return_value={}),
            mock.patch.object(_build_mod, "load_config", return_value=_valid_config()),
            mock.patch.object(_build_mod, "resolve_credential_mounts", return_value=[]),
            mock.patch.object(_build_mod, "_write_env_file", return_value=tmp_path / "env"),
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            result = CliRunner().invoke(build_cmd, ["plan.md"])

        assert result.exit_code == 0, result.output
        assert (runtime_dir / "progress.json").exists()

    def test_build_nested_bind_mount_present_in_runner_params(self, tmp_path: Path, monkeypatch) -> None:
        """The resolved runtime dir reaches params['v'] as the /workspace/.ralphex mount."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        monkeypatch.setattr("goga.runtime.paths.resolve_git_branch", lambda: "test-branch")

        runtime_dir = resolve_build_runtime_dir()

        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "_read_git_config", return_value={}),
            mock.patch.object(_build_mod, "load_config", return_value=_valid_config()),
            mock.patch.object(_build_mod, "resolve_credential_mounts", return_value=[]),
            mock.patch.object(_build_mod, "_write_env_file", return_value=tmp_path / "env"),
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            result = CliRunner().invoke(build_cmd, ["plan.md"])

        assert result.exit_code == 0, result.output
        mounts = mock_runner.return_value.run.call_args.kwargs["v"]
        assert f"{runtime_dir}:/workspace/.ralphex" in mounts

    def test_build_host_path_does_not_leak_into_container_env(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        monkeypatch.setattr("goga.runtime.paths.resolve_git_branch", lambda: "test-branch")

        runtime_dir = resolve_build_runtime_dir()

        captured_cmd: dict = {}
        captured_env: dict = {}

        def _fake_popen(cmd, *args, **kwargs):
            captured_cmd["cmd"] = list(cmd)
            proc = mock.Mock()
            proc.wait.return_value = 0
            return proc

        def _fake_write_env(env, extra_env):
            captured_env["env"] = dict(env)
            captured_env["extra"] = tuple(extra_env)
            return tmp_path / "env"

        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "_read_git_config", return_value={}),
            mock.patch.object(_build_mod, "load_config", return_value=_valid_config()),
            mock.patch.object(_build_mod, "resolve_credential_mounts", return_value=[]),
            mock.patch.object(_build_mod, "_write_env_file", side_effect=_fake_write_env),
            mock.patch.object(subprocess, "Popen", side_effect=_fake_popen),
            mock.patch.object(subprocess, "run"),
        ):
            result = CliRunner().invoke(build_cmd, ["plan.md"])

        assert result.exit_code == 0, result.output
        # The host runtime path must NOT leak into the env-file contents (the
        # container sees only /workspace/.ralphex, never ~/.goga/runtime/builds/...).
        assert str(runtime_dir) not in str(captured_env["env"])
        assert not any(str(runtime_dir) in pair for pair in captured_env["extra"])
        cmd = captured_cmd["cmd"]
        assert "/workspace/.ralphex" in " ".join(cmd)


# --- Logic tests (negative) ---


class TestBuildRuntimeIsolationNegative:
    def test_build_raises_when_image_is_none(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "load_config", return_value=_valid_config(image=None)),
        ):
            result = CliRunner().invoke(build_cmd, ["plan.md"])
        assert result.exit_code == 1


# --- Docker-created mount point cleanup tests ---
#
# Docker Engine, when applying the nested bind-mount
# ``runtime_dir:/workspace/.ralphex`` on top of the ``/workspace`` project
# mount, creates the ``/workspace/.ralphex`` target directory inside the
# bind-mount source — i.e. physically inside the user's project directory. The
# directory is empty (in-container writes land in the nested mount = host
# runtime dir), but it survives container exit. The CODEMANIFEST contract
# forbids ``.ralphex/`` in the project directory under any exit path, so the
# host launcher removes it unconditionally in ``finally``.


class TestCleanupRalphexInProject:
    """``_cleanup_ralphex_in_project`` removes the Docker-created mount point."""

    def test_removes_existing_ralphex_dir(self, tmp_path: Path) -> None:
        ralphex_dir = tmp_path / ".ralphex"
        ralphex_dir.mkdir()

        _cleanup_ralphex_in_project(tmp_path)

        assert not ralphex_dir.exists()

    def test_removes_non_empty_ralphex_dir(self, tmp_path: Path) -> None:
        """The contract forbids ``.ralphex/`` in the project directory —
        removal is unconditional, so non-empty content is removed too (it is
        never legitimate user data per the CODEMANIFEST constraint)."""
        ralphex_dir = tmp_path / ".ralphex"
        ralphex_dir.mkdir()
        (ralphex_dir / "stale_file.txt").write_text("stale")
        (ralphex_dir / "subdir").mkdir()

        _cleanup_ralphex_in_project(tmp_path)

        assert not ralphex_dir.exists()

    def test_noop_when_ralphex_absent(self, tmp_path: Path) -> None:
        # No .ralphex/ in the project dir — cleanup must be a no-op.
        _cleanup_ralphex_in_project(tmp_path)  # no exception

        assert not (tmp_path / ".ralphex").exists()

    def test_tolerates_ralphex_vanishing_during_cleanup(self, tmp_path: Path) -> None:
        """A race where the directory vanishes between the rmtree call and the
        actual removal (concurrent process, crash) must not raise."""
        ralphex_dir = tmp_path / ".ralphex"
        ralphex_dir.mkdir()

        # Simulate a concurrent removal: rmtree will find nothing to remove.
        with mock.patch("shutil.rmtree", side_effect=FileNotFoundError):
            _cleanup_ralphex_in_project(tmp_path)  # no exception


class TestBuildCleansUpRalphexInProjectOnExit:
    """``build()`` removes Docker-created ``.ralphex/`` on every exit path."""

    def test_dry_run_does_not_create_ralphex_in_project(self, tmp_path: Path, monkeypatch) -> None:
        """On --dry-run the host launcher exits before Popen, so Docker never
        creates a mount point. Cleanup runs unconditionally but is a no-op —
        the project dir must be clean after the run."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        monkeypatch.setattr("goga.runtime.paths.resolve_git_branch", lambda: "test-branch")

        runtime_dir = resolve_build_runtime_dir()
        runtime_dir.mkdir(parents=True, exist_ok=True)

        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "_read_git_config", return_value={}),
            mock.patch.object(_build_mod, "load_config", return_value=_valid_config()),
            mock.patch.object(_build_mod, "resolve_credential_mounts", return_value=[]),
            mock.patch.object(_build_mod, "_write_env_file", return_value=tmp_path / "env"),
        ):
            result = CliRunner().invoke(build_cmd, ["plan.md", "--dry-run"])

        assert result.exit_code == 0, result.output
        # No Docker run on dry-run, so no mount point — the project dir stays clean.
        assert not (tmp_path / ".ralphex").exists()

    def test_cleans_up_ralphex_after_docker_run_exit(self, tmp_path: Path, monkeypatch) -> None:
        """When Docker creates a ``.ralphex/`` mount point in the project dir
        during the run, the finally block removes it after container exit."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        monkeypatch.setattr("goga.runtime.paths.resolve_git_branch", lambda: "test-branch")

        runtime_dir = resolve_build_runtime_dir()
        runtime_dir.mkdir(parents=True, exist_ok=True)

        # Simulate Docker creating the empty mount point inside the project dir
        # at Popen time (this is the bug — Docker mutates the bind-mount source).
        def _fake_popen(cmd, *args, **kwargs):
            (tmp_path / ".ralphex").mkdir()  # Docker-created mount point
            proc = mock.Mock()
            proc.wait.return_value = 0
            return proc

        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "_read_git_config", return_value={}),
            mock.patch.object(_build_mod, "load_config", return_value=_valid_config()),
            mock.patch.object(_build_mod, "resolve_credential_mounts", return_value=[]),
            mock.patch.object(_build_mod, "_write_env_file", return_value=tmp_path / "env"),
            mock.patch.object(subprocess, "Popen", side_effect=_fake_popen),
            mock.patch.object(subprocess, "run"),
        ):
            result = CliRunner().invoke(build_cmd, ["plan.md"])

        assert result.exit_code == 0, result.output
        # The Docker-created mount point MUST be removed — the CODEMANIFEST
        # contract forbids ``.ralphex/`` in the project directory.
        assert not (tmp_path / ".ralphex").exists()

    def test_cleans_up_ralphex_on_signal_exit(self, tmp_path: Path, monkeypatch) -> None:
        """Even on a non-zero exit path, the finally block still removes the
        Docker-created mount point — the contract forbids ``.ralphex/`` under
        any exit condition, including crash/SIGKILL."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        monkeypatch.setattr("goga.runtime.paths.resolve_git_branch", lambda: "test-branch")

        runtime_dir = resolve_build_runtime_dir()
        runtime_dir.mkdir(parents=True, exist_ok=True)

        def _fake_popen(cmd, *args, **kwargs):
            (tmp_path / ".ralphex").mkdir()  # Docker-created mount point
            proc = mock.Mock()
            proc.wait.return_value = 137  # SIGKILL exit code
            return proc

        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "_read_git_config", return_value={}),
            mock.patch.object(_build_mod, "load_config", return_value=_valid_config()),
            mock.patch.object(_build_mod, "resolve_credential_mounts", return_value=[]),
            mock.patch.object(_build_mod, "_write_env_file", return_value=tmp_path / "env"),
            mock.patch.object(subprocess, "Popen", side_effect=_fake_popen),
            mock.patch.object(subprocess, "run"),
        ):
            result = CliRunner().invoke(build_cmd, ["plan.md"])

        # Non-zero exit propagated, but finally still ran cleanup.
        assert result.exit_code == 137
        # The Docker-created mount point MUST be removed even on a non-zero
        # exit path — the CODEMANIFEST contract forbids ``.ralphex/`` in the
        # project directory under any exit condition.
        assert not (tmp_path / ".ralphex").exists()
