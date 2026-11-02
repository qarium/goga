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
import yaml
from click.testing import CliRunner
from goga.commands import build as build_cmd
from goga.commands.build.build import (
    _cleanup_ralphex_in_project,
    clean_build_runtime_dir,
    resolve_build_runtime_dir,
)
from goga.config import BuildConfig, PipelineConfig, ProjectConfig
from goga.docker import decode_extra_env, decode_home_profiles, encode_extra_env

_build_mod = __import__("goga.commands.build.build", fromlist=["build"])


def _valid_config(*, image: str | None = "qarium/goga:latest", agent: str | None = "claude") -> ProjectConfig:
    """Return a minimal valid ProjectConfig for the build flow (two-part build)."""
    return ProjectConfig(
        language="python",
        image=image,
        dockerfile=None,
        build=BuildConfig(agent=agent),
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


class TestBuildCleanShortAliasContract:
    """``-c/--clean`` short alias and the ``--skip`` guard (skip is pipeline-only).

    The ``--clean`` option gains a short ``-c`` alias (same flag, same default);
    ``--skip`` must NOT be added to ``goga build`` (skip is a pipeline-only flag).
    """

    def test_build_has_short_clean_option(self) -> None:
        clean_param = next(p for p in build_cmd.params if p.name == "clean")
        assert "-c" in clean_param.opts
        assert "--clean" in clean_param.opts
        assert clean_param.is_flag is True

    def test_build_has_no_skip_option(self) -> None:
        # skip is a pipeline-only flag; goga build must not declare --skip.
        assert not any(p.name == "skip" for p in build_cmd.params)


class TestRetiredFlagSurfaceContract:
    """The retired flags are unknown options: click rejects them with exit 2.

    ``--worktree`` and ``--skip-finalize`` were removed with no replacement
    (major-version window, no compatibility shims). Parsing either flag must
    fail at the argparse/click layer — the rejection message names the option,
    and no docker run ever happens for such an invocation.
    """

    @pytest.mark.parametrize("retired_flag", ["--worktree", "--skip-finalize"])
    def test_retired_flag_is_unknown_option(self, retired_flag: str, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        result = CliRunner().invoke(build_cmd, ["plan.md", retired_flag])

        assert result.exit_code == 2
        assert "No such option" in result.output
        assert retired_flag in result.output

    @pytest.mark.parametrize("retired_flag", ["--worktree", "--skip-finalize"])
    def test_no_worktree_or_skip_finalize_param_declared(self, retired_flag: str) -> None:
        param_names = {p.name for p in build_cmd.params}
        retired_name = retired_flag.removeprefix("--").replace("-", "_")

        assert retired_name not in param_names

    def test_no_worktree_handling_on_the_surface(self) -> None:
        """No flag, no guard, no worktree-related rejection: the callback
        signature and the cli_flags channel carry no worktree/skip_finalize keys."""
        import inspect

        from goga.commands.build.build import _cli_flags_to_args

        param_names = set(inspect.signature(build_cmd.callback).parameters)
        assert "worktree" not in param_names
        assert "skip_finalize" not in param_names
        # The forwarding helper renders nothing for the retired keys either.
        assert _cli_flags_to_args({"worktree": True, "skip_finalize": True, "dry_run": False}) == []


class TestHostLauncherGuardSplitContract:
    """Guards split by nature — only the structural guard stays host-side.

    The agent VALUE guard lives in the in-container build domain
    (``goga/build``), where an amendment can supply the agent; the retired
    host guard (old step 2.2) must be gone from the launcher module, and the
    CLI entries payload carrier must be referenced by it.
    """

    def test_host_agent_guard_message_absent_from_launcher_source(self) -> None:
        assert "build.agent is required" not in inspect.getsource(_build_mod)

    def test_launcher_references_encode_extra_env(self) -> None:
        assert "encode_extra_env" in dir(_build_mod)
        assert _build_mod.encode_extra_env is encode_extra_env


class TestHostCommandSurfaceAndEnvFile:
    """Logic test — the host surface forwards, the env-file carries base layers only.

    The forwarded container args carry ``-m goga.build <plan>`` plus the review
    knobs exactly when set (the host performs no precedence resolution — neither
    the tri-state nor base-ref); the env-file receives home/git/CLI layers and
    NEVER the ``build.env`` values (secret boundary: the task env reaches the
    container through the mounted config, applied in-container).
    """

    @staticmethod
    def _write_two_part_config(tmp_path: Path, *, build_env: dict[str, str] | None = None) -> None:
        build_block: dict = {"agent": "claude"}
        if build_env is not None:
            build_block["env"] = build_env
        (tmp_path / ".goga").mkdir(exist_ok=True)
        (tmp_path / ".goga" / "config.yml").write_text(
            yaml.dump(
                {
                    "language": "python",
                    "image": "qarium/goga:latest",
                    "build": build_block,
                    "pipeline": {"agent": "claude"},
                }
            )
        )

    def test_host_command_surface_and_env_file(self, tmp_path: Path, monkeypatch) -> None:
        self._write_two_part_config(tmp_path, build_env={"API_KEY": "task-secret"})

        # home.env base layer under the isolated HOME (autouse _isolate_home).
        home_goga = Path.home() / ".goga"
        home_goga.mkdir(parents=True, exist_ok=True)
        (home_goga / "config.yml").write_text(yaml.dump({"env": {"HOME_KEY": "home-val"}}))

        monkeypatch.chdir(tmp_path)
        captured: dict = {}

        def _fake_write_env(lines):
            captured["lines"] = list(lines)
            return tmp_path / "env"

        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "_read_git_config", return_value={"GIT_AUTHOR_NAME": "User"}),
            mock.patch.object(_build_mod, "_write_env_file", side_effect=_fake_write_env),
            mock.patch.object(_build_mod, "docker_build_if_not_exist"),
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            result = CliRunner().invoke(
                build_cmd,
                [
                    "--skip-manifest-check",
                    "--base-ref",
                    "x",
                    "--review-patience",
                    "2",
                    "--skip-review",
                    "-e",
                    "CLI_KEY=cli-val",
                    "plan.md",
                ],
            )

        assert result.exit_code == 0, result.output

        # docker args carry -m goga.build <plan> and the set review knobs only.
        args = mock_runner.return_value.run.call_args.args[0]
        assert args[:3] == ["-m", "goga.build", "plan.md"]
        assert "--base-ref" in args
        assert "x" in args
        assert "--review-patience" in args
        assert "2" in args
        assert "--skip-review" in args
        assert "--no-skip-review" not in args

        # env-file layers: home.env, git identity, CLI -e — never build.env.
        assert "HOME_KEY=home-val" in captured["lines"]
        assert "GIT_AUTHOR_NAME=User" in captured["lines"]
        assert "CLI_KEY=cli-val" in captured["lines"]
        assert not any(line.startswith("API_KEY=") for line in captured["lines"])
        assert not any("task-secret" in line for line in captured["lines"])

        # Unset knobs forward nothing: the bare invocation adds no review tokens.
        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "_read_git_config", return_value={}),
            mock.patch.object(_build_mod, "_write_env_file", side_effect=_fake_write_env),
            mock.patch.object(_build_mod, "docker_build_if_not_exist"),
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            result = CliRunner().invoke(build_cmd, ["--skip-manifest-check", "plan.md"])

        assert result.exit_code == 0, result.output
        args = mock_runner.return_value.run.call_args.args[0]
        for token in ("--base-ref", "--review-patience", "--skip-review", "--no-skip-review"):
            assert token not in args


class TestHostBuildGuardSplitAndLadder:
    """Logic tests — the guard split and the env-file ladder of the host launcher.

    The agent VALUE guard lives in-container: a config without ``build.agent``
    still launches. The env-file carries the ladder (base layers → raw CLI
    lines → engine lines with the CLI skip rule → the payload line) composed
    from the same parsed CLI values.
    """

    def test_host_build_no_agent_guard_launches_container_with_payload(self, tmp_path: Path, monkeypatch) -> None:
        """No ``build.agent`` in the authored config: the launch proceeds (the
        value guard is in-container), and the CLI entries travel as both the
        raw lines and the payload — one source, two carriers."""
        (tmp_path / ".goga").mkdir()
        (tmp_path / ".goga" / "config.yml").write_text(
            yaml.dump(
                {
                    "language": "python",
                    "image": "qarium/goga:latest",
                    "build": {"proxy": "http://launcher-proxy:3128"},
                    "pipeline": {"agent": "claude"},
                }
            )
        )
        monkeypatch.chdir(tmp_path)

        captured: dict = {}
        real_write = _build_mod._write_env_file

        def _capture_lines(lines: list[str]) -> Path:
            captured["lines"] = list(lines)
            return real_write(lines)

        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "_read_git_config", return_value={}),
            mock.patch.object(_build_mod, "_write_env_file", side_effect=_capture_lines),
            mock.patch.object(_build_mod, "docker_build_if_not_exist"),
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            result = CliRunner().invoke(
                build_cmd,
                ["-e", "KEY=V", "-e", "HTTP_PROXY=user-proxy", "plan.md"],
            )

        assert result.exit_code == 0, result.output
        assert "build.agent is required" not in result.output
        mock_runner.return_value.run.assert_called_once()

        lines = captured["lines"]
        # The raw CLI lines travel verbatim.
        assert "KEY=V" in lines
        assert "HTTP_PROXY=user-proxy" in lines
        # Exactly ONE HTTP_PROXY line — the CLI one; the launcher's own engine
        # line for that key was skipped (the -e escape hatch keeps winning).
        assert [line for line in lines if line.startswith("HTTP_PROXY=")] == ["HTTP_PROXY=user-proxy"]
        # Engine keys the CLI did not supply still land after the CLI lines.
        assert "HTTPS_PROXY=http://launcher-proxy:3128" in lines
        assert "NO_PROXY=localhost,127.0.0.1" in lines
        assert lines.index("KEY=V") < lines.index("HTTPS_PROXY=http://launcher-proxy:3128")
        # The payload composes from the same parsed values and closes the file.
        payload = next(line for line in lines if line.startswith("GOGA_EXTRA_ENV="))
        assert lines[-1] == payload
        assert decode_extra_env(payload.partition("=")[2]) == {"KEY": "V", "HTTP_PROXY": "user-proxy"}

    def test_build_host_structural_guard_still_fires(self, tmp_path: Path, monkeypatch) -> None:
        """The structural build-section guard stays host-side on the
        host-effective configuration: a build-less config is a clean
        ClickException (exit 1) with no docker run."""
        (tmp_path / ".goga").mkdir()
        (tmp_path / ".goga" / "config.yml").write_text(
            yaml.dump(
                {
                    "language": "python",
                    "image": "qarium/goga:latest",
                    "pipeline": {"agent": "claude"},
                }
            )
        )
        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            result = CliRunner().invoke(build_cmd, ["plan.md"])

        assert result.exit_code == 1
        assert "build section is required in .goga/config.yml to run 'goga build'" in result.output
        mock_runner.return_value.run.assert_not_called()


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
            mock.patch.object(_build_mod, "load_project_config", return_value=_valid_config()),
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

    def test_build_accepts_short_clean_alias(self, tmp_path: Path, monkeypatch) -> None:
        # The short -c alias is equivalent to --clean: it must drive the same
        # clean_build_runtime_dir wipe before docker launch.
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        monkeypatch.setattr("goga.runtime.paths.resolve_git_branch", lambda: "test-branch")

        runtime_dir = resolve_build_runtime_dir()
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "old-state.json").write_text("{}")

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "_read_git_config", return_value={}),
            mock.patch.object(_build_mod, "load_project_config", return_value=_valid_config()),
            mock.patch.object(_build_mod, "_write_env_file", return_value=tmp_path / "env"),
            mock.patch.object(_build_mod, "clean_build_runtime_dir", wraps=clean_build_runtime_dir) as mock_clean,
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            result = CliRunner().invoke(build_cmd, ["plan.md", "-c"])

        assert result.exit_code == 0, result.output
        # -c drives the same wipe as --clean.
        assert mock_clean.call_args == mock.call(runtime_dir)
        assert not (runtime_dir / "old-state.json").exists()

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
            mock.patch.object(_build_mod, "load_project_config", return_value=_valid_config()),
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
            mock.patch.object(_build_mod, "load_project_config", return_value=_valid_config()),
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

        def _fake_write_env(lines):
            captured_env["lines"] = list(lines)
            return tmp_path / "env"

        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "_read_git_config", return_value={}),
            mock.patch.object(_build_mod, "load_project_config", return_value=_valid_config()),
            mock.patch.object(_build_mod, "_write_env_file", side_effect=_fake_write_env),
            mock.patch.object(subprocess, "Popen", side_effect=_fake_popen),
            mock.patch.object(subprocess, "run"),
        ):
            result = CliRunner().invoke(build_cmd, ["plan.md"])

        assert result.exit_code == 0, result.output
        # The host runtime path must NOT leak into the env-file contents (the
        # container sees only /workspace/.ralphex, never ~/.goga/runtime/builds/...).
        assert not any(str(runtime_dir) in line for line in captured_env["lines"])
        assert not any(".goga/runtime/builds" in line for line in captured_env["lines"])
        cmd = captured_cmd["cmd"]
        assert "/workspace/.ralphex" in " ".join(cmd)


class TestBuildNoCredentialMounts:
    """The launcher adds no credential mounts — params['v'] is exactly two entries.

    Credential provisioning is user-owned (``home.docker.run`` / ``-e``); the
    launcher mounts exactly the project dir and the ralphex runtime dir.
    """

    def test_no_credential_mounts_in_build_launcher(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        monkeypatch.setattr("goga.runtime.paths.resolve_git_branch", lambda: "test-branch")
        # A decoy credential under the isolated home: a reintroduced credential
        # loop would detect it, append a read-only mount, and fail the
        # exact-two assertion below.
        monkeypatch.setenv("HOME", str(tmp_path / "home"))
        decoy = tmp_path / "home" / ".codex" / "auth.json"
        decoy.parent.mkdir(parents=True, exist_ok=True)
        decoy.write_text("{}")

        runtime_dir = resolve_build_runtime_dir()

        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "_read_git_config", return_value={}),
            mock.patch.object(_build_mod, "load_project_config", return_value=_valid_config()),
            mock.patch.object(_build_mod, "_write_env_file", return_value=tmp_path / "env"),
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            result = CliRunner().invoke(build_cmd, ["plan.md"])

        assert result.exit_code == 0, result.output
        mounts = mock_runner.return_value.run.call_args.kwargs["v"]
        assert mounts == [
            f"{tmp_path.resolve()}:/workspace",
            f"{runtime_dir}:/workspace/.ralphex",
        ]


# --- Logic tests (negative) ---


class TestBuildRuntimeIsolationNegative:
    def test_build_raises_when_image_is_none(self, tmp_path: Path, monkeypatch) -> None:
        monkeypatch.chdir(tmp_path)
        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "load_project_config", return_value=_valid_config(image=None)),
        ):
            result = CliRunner().invoke(build_cmd, ["plan.md"])
        assert result.exit_code == 1


# --- Profile/workflow host-launcher surface (contributor-profile Task 18) ---


class TestBuildProfileWorkflowOptionsContract:
    """``-w/--workflow`` and ``-p/--profile`` on the build command surface.

    Both are plain optional string options (None default, not flags) carrying
    the short and long forms the contract fixes; the callback signature
    declares both channels as ``str | None``.
    """

    def test_build_has_workflow_option_with_short_alias(self) -> None:
        param = next(p for p in build_cmd.params if p.name == "workflow")
        assert "--workflow" in param.opts
        assert "-w" in param.opts
        assert param.is_flag is False
        assert param.default is None

    def test_build_has_profile_option_with_short_alias(self) -> None:
        param = next(p for p in build_cmd.params if p.name == "profile")
        assert "--profile" in param.opts
        assert "-p" in param.opts
        assert param.is_flag is False
        assert param.default is None

    def test_build_callback_signature_carries_both_channels(self) -> None:
        sig = inspect.signature(build_cmd.callback)
        hints = typing.get_type_hints(build_cmd.callback)

        for name in ("workflow", "profile"):
            assert name in sig.parameters
            assert hints[name] in (str | None, typing.Optional[str])

    def test_cli_flags_render_workflow_and_profile_when_set(self) -> None:
        from goga.commands.build.build import _cli_flags_to_args

        args = _cli_flags_to_args({"workflow": "hard", "profile": "mixa", "dry_run": False})
        assert "--workflow" in args
        assert "hard" in args
        assert "--profile" in args
        assert "mixa" in args

    def test_cli_flags_render_neither_when_unset(self) -> None:
        from goga.commands.build.build import _cli_flags_to_args

        args = _cli_flags_to_args({"workflow": None, "profile": None, "dry_run": False})
        assert "--workflow" not in args
        assert "--profile" not in args


class TestBuildCommandProfileCarriage:
    """The profile/workflow flow of the host launcher.

    The bundle loads once under the isolated HOME before any docker activity;
    the env-file gains the two engine lines after ``GOGA_EXTRA_ENV`` under the
    engine-skip rule; the argv forwards both long flags only when set;
    ``GOGA_WORKFLOW`` is never written and no host feedback line prints.
    """

    @staticmethod
    def _write_launch_config(tmp_path: Path) -> None:
        (tmp_path / ".goga").mkdir(exist_ok=True)
        (tmp_path / ".goga" / "config.yml").write_text(
            yaml.dump(
                {
                    "language": "python",
                    "image": "qarium/goga:latest",
                    "build": {"agent": "claude"},
                    "pipeline": {"agent": "claude"},
                }
            )
        )

    @staticmethod
    def _write_home_profile(name: str = "mixa") -> None:
        profiles = Path.home() / ".goga" / "profiles"
        profiles.mkdir(parents=True, exist_ok=True)
        (profiles / f"{name}.yml").write_text(yaml.dump({"worker": {"agent": "codex"}}))

    def test_build_command_writes_profile_envfile_lines(self, tmp_path: Path, monkeypatch) -> None:
        """Positive — home profile + ambient GOGA_PROFILE + -e K=V: the env-file
        carries K=V, GOGA_EXTRA_ENV, GOGA_PROFILE, GOGA_HOME_PROFILES in order;
        the argv carries --workflow/--profile; GOGA_WORKFLOW is absent; docker
        run is called exactly once; no host feedback line prints."""
        self._write_launch_config(tmp_path)
        workflows = tmp_path / ".goga" / "workflows"
        workflows.mkdir()
        (workflows / "hard.yml").write_text("prompt: p\n")
        self._write_home_profile()

        monkeypatch.setenv("GOGA_PROFILE", "ambient")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("goga.runtime.paths.resolve_git_branch", lambda: "test-branch")

        captured: dict = {}

        def _fake_write_env(lines):
            captured["lines"] = list(lines)
            return tmp_path / "env"

        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "_read_git_config", return_value={}),
            mock.patch.object(_build_mod, "_write_env_file", side_effect=_fake_write_env),
            mock.patch.object(_build_mod, "docker_build_if_not_exist"),
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            result = CliRunner().invoke(build_cmd, ["-e", "K=V", "-w", "hard", "-p", "mixa", "plan.md"])

        assert result.exit_code == 0, result.output

        lines = captured["lines"]
        assert "K=V" in lines
        payload_idx = next(i for i, line in enumerate(lines) if line.startswith("GOGA_EXTRA_ENV="))
        profile_idx = lines.index("GOGA_PROFILE=ambient")
        bundle_idx = next(i for i, line in enumerate(lines) if line.startswith("GOGA_HOME_PROFILES="))
        assert payload_idx < profile_idx < bundle_idx

        payload_value = lines[bundle_idx].partition("=")[2]
        assert decode_home_profiles(payload_value) == {"mixa": {"worker": {"agent": "codex"}}}
        assert not any(line.startswith("GOGA_WORKFLOW=") for line in lines)
        assert "Build running with workflow" not in result.output

        args = mock_runner.return_value.run.call_args.args[0]
        assert "--workflow" in args
        assert "hard" in args
        assert "--profile" in args
        assert "mixa" in args
        mock_runner.return_value.run.assert_called_once()

    def test_build_command_engine_skip_keeps_explicit_dash_e_winning(self, tmp_path: Path, monkeypatch) -> None:
        """An explicit -e GOGA_PROFILE / -e GOGA_HOME_PROFILES entry suppresses
        the launcher's own engine line for that key — exactly one line per key,
        the CLI one."""
        self._write_launch_config(tmp_path)
        self._write_home_profile()

        monkeypatch.setenv("GOGA_PROFILE", "ambient")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("goga.runtime.paths.resolve_git_branch", lambda: "test-branch")

        captured: dict = {}

        def _fake_write_env(lines):
            captured["lines"] = list(lines)
            return tmp_path / "env"

        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "_read_git_config", return_value={}),
            mock.patch.object(_build_mod, "_write_env_file", side_effect=_fake_write_env),
            mock.patch.object(_build_mod, "docker_build_if_not_exist"),
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            result = CliRunner().invoke(
                build_cmd,
                ["-e", "GOGA_PROFILE=custom", "-e", "GOGA_HOME_PROFILES=custom-payload", "plan.md"],
            )

        assert result.exit_code == 0, result.output
        lines = captured["lines"]
        assert [line for line in lines if line.startswith("GOGA_PROFILE=")] == ["GOGA_PROFILE=custom"]
        assert [line for line in lines if line.startswith("GOGA_HOME_PROFILES=")] == [
            "GOGA_HOME_PROFILES=custom-payload"
        ]

    def test_build_command_no_cargo_writes_no_profile_lines(self, tmp_path: Path, monkeypatch) -> None:
        """No ambient GOGA_PROFILE and an empty bundle: neither engine line is
        written — GOGA_EXTRA_ENV stays the closing line of the env-file."""
        self._write_launch_config(tmp_path)
        monkeypatch.delenv("GOGA_PROFILE", raising=False)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setattr("goga.runtime.paths.resolve_git_branch", lambda: "test-branch")

        captured: dict = {}

        def _fake_write_env(lines):
            captured["lines"] = list(lines)
            return tmp_path / "env"

        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "_read_git_config", return_value={}),
            mock.patch.object(_build_mod, "_write_env_file", side_effect=_fake_write_env),
            mock.patch.object(_build_mod, "docker_build_if_not_exist"),
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            result = CliRunner().invoke(build_cmd, ["plan.md"])

        assert result.exit_code == 0, result.output
        lines = captured["lines"]
        assert not any(line.startswith("GOGA_PROFILE=") for line in lines)
        assert not any(line.startswith("GOGA_HOME_PROFILES=") for line in lines)
        assert lines[-1].startswith("GOGA_EXTRA_ENV=")

        args = mock_runner.return_value.run.call_args.args[0]
        assert "--workflow" not in args
        assert "--profile" not in args

    @pytest.mark.parametrize(
        ("flag", "value"),
        [("-w", "-x"), ("--workflow", "-x"), ("-p", "-x"), ("--profile", "-x")],
    )
    def test_build_command_rejects_leading_dash_values(
        self, tmp_path: Path, monkeypatch, flag: str, value: str
    ) -> None:
        """A dash-leading -w/-p value parses on the host (click swallows the
        next token) but would die in-container after the launch ceremony — a
        clean error, exit 1, and no docker activity."""
        self._write_launch_config(tmp_path)
        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "docker_build_if_not_exist") as mock_build,
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            result = CliRunner().invoke(build_cmd, [flag, value, "plan.md"])

        assert result.exit_code == 1
        assert "invalid" in result.output
        assert value in result.output
        mock_runner.return_value.run.assert_not_called()
        mock_build.assert_not_called()

    def test_build_command_malformed_home_profile_clean_error_before_docker(self, tmp_path: Path, monkeypatch) -> None:
        """A malformed home profile under the isolated HOME is one clean
        ClickException before any docker activity — no image build, no launch."""
        self._write_launch_config(tmp_path)
        profiles = Path.home() / ".goga" / "profiles"
        profiles.mkdir(parents=True)
        (profiles / "broken.yml").write_text("- just\n- a list\n")
        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "docker_build_if_not_exist") as mock_build,
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            result = CliRunner().invoke(build_cmd, ["plan.md"])

        assert result.exit_code == 1
        assert "home profile" in result.output
        mock_runner.return_value.run.assert_not_called()
        mock_build.assert_not_called()

    def test_build_command_workflow_host_side_diagnostics(self, tmp_path: Path, monkeypatch) -> None:
        """-w is validated host-side: a missing file under .goga/workflows/ and
        an escaping name are clean exit-1 diagnostics naming the workflow; the
        file itself is never read (a directory entry is enough)."""
        self._write_launch_config(tmp_path)
        workflows = tmp_path / ".goga" / "workflows"
        workflows.mkdir()
        (workflows / "hard.yml").write_text("prompt: p\n")
        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            missing = CliRunner().invoke(build_cmd, ["plan.md", "-w", "missing"])
            escape = CliRunner().invoke(build_cmd, ["plan.md", "-w", "../escape"])
            present = CliRunner().invoke(build_cmd, ["plan.md", "-w", "hard", "--dry-run"])

        assert missing.exit_code == 1
        assert "workflow 'missing' not found" in missing.output
        assert escape.exit_code == 1
        assert "invalid workflow name" in escape.output
        assert present.exit_code == 0, present.output
        mock_runner.return_value.run.assert_not_called()

    def test_build_command_dry_run_prints_assembled_command(self, tmp_path: Path, monkeypatch) -> None:
        """--dry-run prints the assembled docker run line — the same param→flag
        translation and argv order a launch would use — to stderr, then exits 0
        without launching (the ralphex launcher's dry-run pattern)."""
        self._write_launch_config(tmp_path)
        workflows = tmp_path / ".goga" / "workflows"
        workflows.mkdir()
        (workflows / "hard.yml").write_text("prompt: p\n")
        monkeypatch.chdir(tmp_path)

        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "docker_build_if_not_exist") as mock_build,
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            result = CliRunner().invoke(build_cmd, ["plan.md", "-w", "hard", "--dry-run"])

        assert result.exit_code == 0, result.output
        assert result.stderr, "the assembled command prints to stderr"
        printed = result.stderr.strip().splitlines()[-1]
        # The assembled launch line: docker run <params-flags> <image> <args>.
        assert printed.startswith("docker run ")
        assert "--entrypoint python3" in printed
        assert "--env-file " in printed
        assert "qarium/goga:latest" in printed
        assert printed.endswith(" -m goga.build plan.md --dry-run --workflow hard")
        mock_runner.return_value.run.assert_not_called()
        mock_build.assert_not_called()


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


# --- Direct substrate (GOGA_DOCKER=1) tests: step 1a / 14a ---
#
# Inside the goga image the command executes the SAME composed in-container
# command line and env contract as a direct child process through
# ``run_direct`` (per ``direct-runner``) instead of through docker run. The
# docker-CLI check, the image guard, the host ralphex runtime-dir machinery,
# the env-file write, and DockerRunner are substrate-scoped to the host path;
# the host-only options (-e/--env, --add-host, --proxy, -u/--update) are
# rejected with an error naming the option BEFORE any other work.


def _write_direct_config(tmp_path: Path, *, image: str | None = "qarium/goga:latest") -> None:
    """Materialize the minimal build-project ``.goga/config.yml`` under ``tmp_path``.

    ``image=None`` models a config the host substrate's image guard would
    reject — used to pin that the guard is substrate-scoped to the host path.
    """
    (tmp_path / ".goga").mkdir(exist_ok=True)
    (tmp_path / ".goga" / "config.yml").write_text(
        yaml.dump(
            {
                "language": "python",
                "image": image,
                "build": {"agent": "claude"},
                "pipeline": {"agent": "claude"},
            }
        )
    )


class TestBuildDirectSubstrate:
    """The direct substrate (GOGA_DOCKER=1): the same composed child, host-only options rejected.

    Step 1a contract: with the marker set, each of the four host-only options
    is rejected with an error naming it BEFORE any other work (SC2 — the
    docker-CLI check and the config load never run, nothing is silently
    ignored, no child spawns). Step 14a contract: the direct run spawns the
    SAME composed in-container argv with the SAME env ladder parsed into the
    child env layer (SC1 build form), the direct dry-run prints the child
    command and exits 0, and --clean wipes ``<cwd>/.ralphex`` before launch.
    """

    @pytest.mark.parametrize(
        ("argv", "flag"),
        [
            (["plan.md", "-e", "K=V"], "--env/-e"),
            (["plan.md", "--add-host", "h:ip"], "--add-host"),
            (["plan.md", "--proxy", "http://p"], "--proxy"),
            (["plan.md", "-u"], "--update/-u"),
        ],
        ids=["env", "add-host", "proxy", "update"],
    )
    def test_build_direct_rejects_each_host_only_option(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, argv: list[str], flag: str
    ) -> None:
        """Each host-only option exits 1 naming the option, before any spawn or docker check."""
        import goga.docker.runner

        from tests.commands.pipeline.conftest import DirectSpawnPopen

        _write_direct_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("GOGA_DOCKER", "1")

        spawn = DirectSpawnPopen(returncode=0)
        monkeypatch.setattr(goga.docker.runner.subprocess, "Popen", spawn)

        result = CliRunner().invoke(build_cmd, argv)

        assert result.exit_code == 1
        assert flag in result.stderr
        assert "is host-only" in result.stderr
        # Nothing was silently ignored and nothing ran — no child, no docker
        # activity.
        assert spawn.calls == []

    def test_build_direct_host_only_rejection_precedes_config_load(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Step 1a runs BEFORE the docker check and the config load (contract: 1a before 1).

        A config-less project with ``-e`` still reports the host-only error —
        not the config error, and not the docker-CLI error.
        """
        import goga.docker.runner

        from tests.commands.pipeline.conftest import DirectSpawnPopen

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("GOGA_DOCKER", "1")

        spawn = DirectSpawnPopen(returncode=0)
        monkeypatch.setattr(goga.docker.runner.subprocess, "Popen", spawn)

        with (
            mock.patch.object(_build_mod, "_check_docker") as mock_check,
            mock.patch.object(_build_mod, "load_project_config") as mock_config,
        ):
            result = CliRunner().invoke(build_cmd, ["plan.md", "-e", "K=V"])

        assert result.exit_code == 1
        assert "is host-only" in result.stderr
        # The rejection precedes both the docker-CLI check and the config load.
        mock_check.assert_not_called()
        mock_config.assert_not_called()
        assert spawn.calls == []

    def test_build_direct_spawns_child_with_env_overlay(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A direct run spawns the composed argv with the parsed ladder as the env layer.

        The child argv is the SAME post-image command the docker substrate
        hands to the image entrypoint, prefixed with the program token; the
        env overlay carries the ``GOGA_EXTRA_ENV`` payload line composed from
        the same (empty) parsed CLI entries; no docker machinery runs; the
        project directory keeps no ``.ralphex/`` (the finally cleanup ran).
        """
        import goga.docker.runner

        from tests.commands.pipeline.conftest import DirectSpawnPopen

        _write_direct_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("GOGA_DOCKER", "1")
        monkeypatch.setattr(_build_mod, "_read_git_config", lambda: {})

        spawn = DirectSpawnPopen(returncode=0)
        monkeypatch.setattr(goga.docker.runner.subprocess, "Popen", spawn)

        runner_cls = mock.Mock()
        with (
            mock.patch.object(_build_mod, "DockerRunner", runner_cls),
            mock.patch.object(_build_mod, "docker_build_if_not_exist") as mock_build,
            mock.patch.object(_build_mod, "docker_update") as mock_refresh,
        ):
            result = CliRunner().invoke(build_cmd, ["plan.md"])

        assert result.exit_code == 0
        assert len(spawn.calls) == 1
        argv, env = spawn.calls[0]
        assert argv == ["python3", "-m", "goga.build", "plan.md"]
        assert env["GOGA_EXTRA_ENV"] == encode_extra_env([])
        # The project-directory invariant holds under the direct exit path.
        assert not (tmp_path / ".ralphex").exists()
        # The docker substrate is fully bypassed.
        runner_cls.assert_not_called()
        mock_build.assert_not_called()
        mock_refresh.assert_not_called()

    def test_build_direct_dry_run_prints_child_command_and_exits_zero(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The direct dry-run prints the DIRECT child command — never a docker run line."""
        import goga.docker.runner

        from tests.commands.pipeline.conftest import DirectSpawnPopen

        _write_direct_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("GOGA_DOCKER", "1")
        monkeypatch.setattr(_build_mod, "_read_git_config", lambda: {})

        spawn = DirectSpawnPopen(returncode=0)
        monkeypatch.setattr(goga.docker.runner.subprocess, "Popen", spawn)

        with mock.patch.object(_build_mod, "DockerRunner") as runner_cls:
            result = CliRunner().invoke(build_cmd, ["plan.md", "--dry-run"])

        assert result.exit_code == 0
        assert "python3 -m goga.build plan.md --dry-run" in result.stderr
        # The DIRECT line, never the docker line — and nothing executed.
        assert "docker run" not in result.stderr
        assert spawn.calls == []
        runner_cls.assert_not_called()

    @pytest.mark.parametrize("clean", [True, False], ids=["clean", "no-clean"])
    def test_build_direct_clean_wipes_before_launch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, clean: bool
    ) -> None:
        """--clean wipes ``<cwd>/.ralphex`` BEFORE the spawn; the finally cleanup owns every exit path.

        The spawn fake records the stale-marker state at call time: with
        ``--clean`` the marker is already gone when the child spawns; without
        it the marker survives the launch (no wipe) and only the finally
        cleanup removes the directory afterwards — the no-.ralphex-in-project
        invariant holds on both arms.
        """
        import goga.docker.runner

        from tests.commands.pipeline.conftest import DirectSpawnPopen

        _write_direct_config(tmp_path)
        stale = tmp_path / ".ralphex" / "stale"
        stale.parent.mkdir(parents=True)
        stale.write_text("old-state")
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("GOGA_DOCKER", "1")
        monkeypatch.setattr(_build_mod, "_read_git_config", lambda: {})

        observed: dict[str, bool] = {}

        class _RecordingPopen(DirectSpawnPopen):
            def __call__(self, argv: list[str], env: dict[str, str] | None = None) -> object:
                observed["stale_at_spawn"] = stale.exists()

                return super().__call__(argv, env)

        monkeypatch.setattr(goga.docker.runner.subprocess, "Popen", _RecordingPopen(returncode=0))

        argv = ["plan.md", "--clean"] if clean else ["plan.md"]
        result = CliRunner().invoke(build_cmd, argv)

        assert result.exit_code == 0
        # The launch happened, and the wipe (or its absence) preceded it.
        assert observed["stale_at_spawn"] is not clean
        # The no-.ralphex-in-project invariant holds under every exit path.
        assert not stale.exists()
        assert not (tmp_path / ".ralphex").exists()

    def test_build_direct_child_exit_code_propagates_verbatim(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The child's exit code returns through ``ctx.exit`` verbatim — no remapping."""
        import goga.docker.runner

        from tests.commands.pipeline.conftest import DirectSpawnPopen

        _write_direct_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("GOGA_DOCKER", "1")
        monkeypatch.setattr(_build_mod, "_read_git_config", lambda: {})

        spawn = DirectSpawnPopen(returncode=7)
        monkeypatch.setattr(goga.docker.runner.subprocess, "Popen", spawn)

        result = CliRunner().invoke(build_cmd, ["plan.md"])

        assert result.exit_code == 7
        assert len(spawn.calls) == 1

    def test_build_direct_skips_docker_check_and_image_guard(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A failing docker-CLI check and an unset image both pass on the direct substrate.

        Mirrors the pipeline surface's twin: ``_check_docker`` resolving
        ``False`` (no docker on the machine) and a config the host image
        guard would reject must neither stop the direct run nor spawn any
        docker activity — both gates are substrate-scoped to the host path.
        """
        import goga.docker.runner

        from tests.commands.pipeline.conftest import DirectSpawnPopen

        _write_direct_config(tmp_path, image=None)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("GOGA_DOCKER", "1")
        monkeypatch.setattr(_build_mod, "_read_git_config", lambda: {})
        monkeypatch.setattr(_build_mod, "_check_docker", lambda: False)

        spawn = DirectSpawnPopen(returncode=0)
        monkeypatch.setattr(goga.docker.runner.subprocess, "Popen", spawn)

        result = CliRunner().invoke(build_cmd, ["plan.md"])

        assert result.exit_code == 0
        assert len(spawn.calls) == 1

    def test_build_direct_spawn_failure_is_clean_click_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A raw OSError from the spawn is wrapped by the caller (D5) — clean message, exit 1.

        ``run_direct`` propagates a spawn ``OSError`` raw (its own contract
        test pins that); the command owns the wrapping, so a missing program
        token is the same clean error surface as every other failure of
        ``goga build`` — never a traceback — and the no-.ralphex-in-project
        cleanup still runs on that exit path.
        """
        import goga.docker.runner

        _write_direct_config(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("GOGA_DOCKER", "1")
        monkeypatch.setattr(_build_mod, "_read_git_config", lambda: {})

        def _raising_popen(argv: list[str], env: dict[str, str] | None = None) -> object:
            raise FileNotFoundError(f"No such file or directory: {argv[0]}")

        monkeypatch.setattr(goga.docker.runner.subprocess, "Popen", _raising_popen)

        result = CliRunner().invoke(build_cmd, ["plan.md"])

        assert result.exit_code == 1
        assert "No such file or directory" in result.stderr
        assert not isinstance(result.exception, FileNotFoundError)
        # The finally cleanup ran on the spawn-failure exit path too.
        assert not (tmp_path / ".ralphex").exists()

    def test_build_direct_env_overlay_parses_the_same_ladder_lines(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """D1 parity: the direct child env layer is the parse of the SAME composed lines.

        The host substrate writes the composed ladder into the private
        env-file; the direct substrate parses the SAME lines into the child
        env layer — one composition, two sinks (divergence between the
        surfaces is a defect per ``direct-runner``).
        """
        import goga.docker.runner

        from tests.commands.pipeline.conftest import DirectSpawnPopen

        _write_direct_config(tmp_path)
        monkeypatch.setattr(_build_mod, "_read_git_config", lambda: {"GIT_AUTHOR_NAME": "User"})
        monkeypatch.setenv("GOGA_PROFILE", "ambient")
        monkeypatch.chdir(tmp_path)

        def _parse(lines: list[str]) -> dict[str, str]:
            return dict(line.split("=", 1) for line in lines)

        # Host substrate: capture the env-file lines the ladder composes.
        host_lines: dict[str, list[str]] = {}

        def _capture(lines: list[str]) -> Path:
            host_lines["lines"] = list(lines)

            return tmp_path / "env"

        with (
            mock.patch.object(_build_mod, "_check_docker", return_value=True),
            mock.patch.object(_build_mod, "_write_env_file", side_effect=_capture),
            mock.patch.object(_build_mod, "docker_build_if_not_exist"),
            mock.patch.object(_build_mod, "DockerRunner") as mock_runner,
        ):
            mock_runner.return_value.run.return_value = 0
            monkeypatch.delenv("GOGA_DOCKER", raising=False)
            CliRunner().invoke(build_cmd, ["plan.md"])

        # Direct substrate: capture the child env layer of the same project.
        spawn = DirectSpawnPopen(returncode=0)
        monkeypatch.setattr(goga.docker.runner.subprocess, "Popen", spawn)
        monkeypatch.setenv("GOGA_DOCKER", "1")

        with mock.patch.object(_build_mod, "_write_env_file") as mock_write:
            CliRunner().invoke(build_cmd, ["plan.md"])

        mock_write.assert_not_called()
        assert len(spawn.calls) == 1
        _argv, direct_env = spawn.calls[0]
        assert direct_env is not None
        # The overlay applies OVER the inherited environment (run_direct's
        # merge): every ladder key lands with its composed value, and the
        # composed values are exactly the parse of the SAME lines the host
        # path wrote (docker --env-file semantics mirrored by first-= split).
        expected_overlay = _parse(host_lines["lines"])
        assert set(expected_overlay) <= set(direct_env)

        for key, value in expected_overlay.items():
            assert direct_env[key] == value

        assert direct_env["GIT_AUTHOR_NAME"] == "User"
        assert direct_env["GOGA_PROFILE"] == "ambient"


class TestComposeEnvLines:
    """The extracted ladder composer — one composition shared by both substrate sinks.

    The host sink writes the lines into the private env-file; the direct sink
    parses them through ``_env_overlay`` into the child env layer.
    """

    def test_compose_env_lines_ladder_order(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The ladder: home.env base < git identity < raw CLI lines < engine proxy triple < payload < carriage."""
        monkeypatch.setenv("GOGA_PROFILE", "ambient")
        lines = _build_mod._compose_env_lines(
            home_env={"HOME_KEY": "home-val", "SHARED": "home"},
            git_env={"GIT_AUTHOR_NAME": "User", "SHARED": "git"},
            extra_env=("CLI_KEY=cli-val",),
            proxy="http://p:3128",
            home_profiles={"mixa": {"worker": {"agent": "codex"}}},
        )

        assert lines[0] == "HOME_KEY=home-val"
        assert "SHARED=git" in lines  # git identity overrides home.env on conflict
        assert lines.index("HOME_KEY=home-val") < lines.index("CLI_KEY=cli-val")
        assert lines.index("CLI_KEY=cli-val") < lines.index("HTTP_PROXY=http://p:3128")
        assert lines.index("HTTP_PROXY=http://p:3128") < lines.index("HTTPS_PROXY=http://p:3128")
        assert "NO_PROXY=localhost,127.0.0.1" in lines
        # The payload line, then the two carriage engine lines, close the file.
        payload_idx = next(i for i, line in enumerate(lines) if line.startswith("GOGA_EXTRA_ENV="))
        assert decode_extra_env(lines[payload_idx].partition("=")[2]) == {"CLI_KEY": "cli-val"}
        assert payload_idx < lines.index("GOGA_PROFILE=ambient")
        assert lines.index("GOGA_PROFILE=ambient") < next(
            i for i, line in enumerate(lines) if line.startswith("GOGA_HOME_PROFILES=")
        )
        assert not any(line.startswith("GOGA_WORKFLOW=") for line in lines)

    def test_compose_env_lines_no_proxy_omits_triple(self) -> None:
        """No resolved proxy — no proxy triple in the lines."""
        lines = _build_mod._compose_env_lines(
            home_env={},
            git_env={},
            extra_env=(),
            proxy=None,
            home_profiles={},
        )

        assert lines == [f"GOGA_EXTRA_ENV={encode_extra_env([])}"]

    def test_compose_env_lines_engine_skip_rule(self) -> None:
        """An explicit -e key suppresses the launcher's own engine line for that key."""
        lines = _build_mod._compose_env_lines(
            home_env={},
            git_env={},
            extra_env=("HTTP_PROXY=user-proxy",),
            proxy="http://launcher:3128",
            home_profiles={},
        )

        assert [line for line in lines if line.startswith("HTTP_PROXY=")] == ["HTTP_PROXY=user-proxy"]
        assert "HTTPS_PROXY=http://launcher:3128" in lines

    def test_env_overlay_splits_first_equals_last_write_wins(self) -> None:
        """The overlay parse: split on the FIRST ``=``, later lines win — mirroring --env-file."""
        overlay = _build_mod._env_overlay(["A=1", "B=x=y", "A=2"])

        assert overlay == {"A": "2", "B": "x=y"}


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
            mock.patch.object(_build_mod, "load_project_config", return_value=_valid_config()),
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
            mock.patch.object(_build_mod, "load_project_config", return_value=_valid_config()),
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
            mock.patch.object(_build_mod, "load_project_config", return_value=_valid_config()),
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
