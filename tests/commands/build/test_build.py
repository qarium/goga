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
    _build_docker_cmd,
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

    def test_build_nested_bind_mount_present_in_docker_cmd(self) -> None:
        cmd = _build_docker_cmd(
            "plan.md",
            "goga:latest",
            Path("/tmp/env"),
            {},
            "test-build",
            {},
            Path("/host/rt"),
        )
        assert "-v" in cmd
        assert "/host/rt:/workspace/.ralphex" in cmd

    def test_build_nested_bind_mount_omitted_when_runtime_dir_none(self) -> None:
        cmd = _build_docker_cmd(
            "plan.md",
            "goga:latest",
            Path("/tmp/env"),
            {},
            "test-build",
            {},
            None,
        )
        assert not any(arg.endswith(":/workspace/.ralphex") for arg in cmd)

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
        assert "image" in result.output
