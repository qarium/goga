from __future__ import annotations

import base64
import json
import signal
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest import mock

import click
import pytest
from goga.commands.pipeline import run_pipeline_container
from goga.commands.pipeline.run_pipeline_container import run_pipeline_container as rpc
from goga.config import (
    DockerArgsConfig,
    HomeConfig,
)
from goga.docker import decode_extra_env

from tests.commands.pipeline.conftest import apply_run_mode_common_mocks as _apply_run_mode_common_mocks
from tests.commands.pipeline.conftest import make_config as _make_config

# Resolve the real submodule via sys.modules (the package __init__ binds the
# function name `run_pipeline_container`, which would shadow string-based
# mock.patch paths walking through the package on Python 3.10).
_rpc_mod = sys.modules["goga.commands.pipeline.run_pipeline_container"]

_ENGINE_LINE_PREFIXES = ("AFM_DIR=", "AFM_DOCKER_FILE_ROOTS=", "HTTP_PROXY=", "HTTPS_PROXY=", "NO_PROXY=")


# --- Contract tests ---


class TestRunPipelineContainerContract:
    def test_importable_from_facade(self) -> None:
        """run_pipeline_container is importable from goga.commands.pipeline."""
        assert run_pipeline_container is rpc

    def test_signature_name_config_extra_env(self) -> None:
        """Signature exposes name/config/extra_env/proxy/hosts/clean/update/workflow/no_workflow/skip/parallel."""
        import inspect

        params = list(inspect.signature(rpc).parameters)
        assert params == [
            "name",
            "config",
            "extra_env",
            "proxy",
            "hosts",
            "clean",
            "update",
            "workflow",
            "no_workflow",
            "skip",
            "parallel",
        ]

    def test_extra_env_has_empty_tuple_default(self) -> None:
        """`extra_env` defaults to an empty tuple for backward compatibility."""
        import inspect

        sig = inspect.signature(rpc).parameters["extra_env"]
        assert sig.default == ()

    def test_module_does_not_resolve_agent(self) -> None:
        """The launcher module references no resolve_wrapper_path (host resolves no agent).

        The order-independent module-object form (per the plan): the afm
        configuration file is authored in-container, so the host cell carries no
        agents import at all.
        """
        assert "resolve_wrapper_path" not in dir(_rpc_mod)

    def test_module_does_not_define_afm_config_tmpfile(self) -> None:
        """The retired _write_afm_config_tmpfile helper is gone from the module."""
        assert "_write_afm_config_tmpfile" not in dir(_rpc_mod)
        assert "_write_afm_config_tmpfile" not in Path(_rpc_mod.__file__).read_text()


# --- Run mode docker command shape ---


class TestPipelineRunCommand:
    def test_pipeline_run_launches_container_with_port_and_env_file(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        """Run mode publishes the port, forwards the env-file, no afm-config mount, no dashboard URL."""
        config = _make_config(pipeline_agent="claude")
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config)

        cmd = mock_popen.call_args[0][0]
        # same port reaches -p and --port
        assert "-p" in cmd
        assert "50321:50321" in cmd
        assert "run" in cmd
        assert "deploy" in cmd
        assert "--port" in cmd
        assert "50321" in cmd
        # no afm-config overlay exists on any launch — the config.yaml is
        # authored in-container by the run coordination
        assert not any("/home/goga/.afm/config.yaml" in arg for arg in cmd)
        assert "--env-file" in cmd

        out = capsys.readouterr().out
        # This cell surfaces NO dashboard URL line — only the workflow log line
        # (when applicable) and the docker output stream. With no workflow flags
        # and no .goga/workflows/deploy.yml auto-match file, no log is emitted.
        assert "Web UI:" not in out

    def test_pipeline_run_does_not_mount_afm_state_under_workspace(self, tmp_path: Path, monkeypatch) -> None:
        """afm state is never mounted under /workspace."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config)

        cmd = mock_popen.call_args[0][0]
        assert not any(arg.endswith(":/workspace/.afm") for arg in cmd)
        assert not any(arg.endswith(":/workspace/.afm/config.yaml") for arg in cmd)

    def test_pipeline_run_does_not_mount_host_user_pipelines(self, tmp_path: Path, monkeypatch) -> None:
        """Run mode never bind-mounts the host's ~/.goga/pipelines into the container.

        The image is populated at build time via `RUN goga connect ...` in the
        Dockerfile; in-container /home/goga/.goga/pipelines reflects the image's
        user pipelines. Bind-mounting the host directory overwrites the image's
        pipelines with the host's, breaking in-container isolation.
        """
        config = _make_config()
        fake_home = tmp_path / "home"
        (fake_home / ".goga" / "pipelines").mkdir(parents=True)
        monkeypatch.setattr(Path, "home", lambda: fake_home)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config)

        cmd = mock_popen.call_args[0][0]
        assert not any(arg.endswith(":/home/goga/.goga/pipelines:ro") for arg in cmd)
        assert not any(arg.endswith(":/home/goga/.goga/pipelines") for arg in cmd)


# --- env file combination ---


def _capture_env_file(monkeypatch) -> dict[str, object]:
    """Wrap ``_write_env_file`` to capture the ladder lines and the written path.

    The real writer still runs (its Path is returned to the launcher so the
    ``finally`` unlink stays observable); the captured ``lines`` are read as
    passed, before any unlink.
    """
    captured: dict[str, object] = {"lines": [], "path": None}
    real_write = _rpc_mod._write_env_file

    def capture(lines: list[str]) -> Path:
        path = real_write(lines)
        captured["lines"] = list(lines)
        captured["path"] = path
        return path

    monkeypatch.setattr(_rpc_mod, "_write_env_file", capture)
    return captured


def _payload_line(lines: list[str]) -> str:
    """Return the single GOGA_EXTRA_ENV payload line of a captured env-file."""
    payload_lines = [line for line in lines if line.startswith("GOGA_EXTRA_ENV=")]
    assert len(payload_lines) == 1
    return payload_lines[0]


class TestPipelineEnvFile:
    def test_write_env_file_writes_lines_verbatim_at_mode_0600(self) -> None:
        """_write_env_file writes the assembled ladder lines verbatim in a private file."""
        env_path = _rpc_mod._write_env_file(["FOO=1", "BAR=2", "BAZ=qux"])
        try:
            content = env_path.read_text()
            mode = env_path.stat().st_mode & 0o777
        finally:
            env_path.unlink(missing_ok=True)

        assert content == "FOO=1\nBAR=2\nBAZ=qux\n"
        assert mode == 0o600

    def test_pipeline_env_file_appends_extra_env_lines_after_base_before_engine(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """`extra_env` KEY=VALUE strings land after the home/git base lines, before the engine lines.

        Mirrors `goga/commands/build._write_env_file`: no validation, later
        duplicates override earlier ones inside the container (Docker
        `--env-file` semantics); the engine lines follow the CLI lines so the
        env-file itself respects the ladder.
        """
        config = _make_config()
        _apply_run_mode_common_mocks(tmp_path, monkeypatch)
        monkeypatch.setattr(
            _rpc_mod,
            "load_home_config",
            lambda: HomeConfig(env={"FOO": "1"}, docker=DockerArgsConfig(run=[])),
        )
        captured = _capture_env_file(monkeypatch)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config, extra_env=("BAR=2", "BAZ=qux"))

        lines = captured["lines"]
        assert "FOO=1" in lines
        assert "BAR=2" in lines
        assert "BAZ=qux" in lines
        # the CLI lines come after the base lines and before the engine lines
        assert lines.index("BAR=2") > lines.index("FOO=1")
        assert lines.index("BAR=2") < next(i for i, line in enumerate(lines) if line.startswith("AFM_DIR="))

    def test_pipeline_env_file_default_extra_env_is_empty_payload_line(self, tmp_path: Path, monkeypatch) -> None:
        """Default `extra_env=()` writes no CLI line but STILL writes the payload line."""
        config = _make_config()
        _apply_run_mode_common_mocks(tmp_path, monkeypatch)
        captured = _capture_env_file(monkeypatch)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config)

        lines = captured["lines"]
        # one payload line on every launch, decoding to the empty mapping
        payload = _payload_line(lines)
        assert decode_extra_env(payload.split("=", 1)[1]) == {}
        # no CLI lines and no other non-engine line (home env and git are empty)
        assert all(line.startswith(_ENGINE_LINE_PREFIXES) or line.startswith("GOGA_EXTRA_ENV=") for line in lines)

    def test_pipeline_run_forwards_extra_env_to_write_env_file(self, tmp_path: Path, monkeypatch) -> None:
        """Run mode forwards the raw CLI lines and the payload composed from the same values."""
        config = _make_config()
        _apply_run_mode_common_mocks(tmp_path, monkeypatch)
        captured = _capture_env_file(monkeypatch)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container(
                "deploy",
                config,
                ("ANTHROPIC_API_KEY=sk-xxx", "MODEL=claude-sonnet-4-6"),
            )

        lines = captured["lines"]
        # the raw lines travel verbatim
        assert "ANTHROPIC_API_KEY=sk-xxx" in lines
        assert "MODEL=claude-sonnet-4-6" in lines
        # the payload composes from the SAME parsed values (one source)
        payload = _payload_line(lines)
        assert decode_extra_env(payload.split("=", 1)[1]) == {
            "ANTHROPIC_API_KEY": "sk-xxx",
            "MODEL": "claude-sonnet-4-6",
        }


# --- afm file-manager roots (AFM_DOCKER_FILE_ROOTS layer) ---


class TestPipelineFileRoots:
    """Run mode produces the afm file-manager roots env layer (the `afm` practice).

    The launcher is the PRODUCER of the ``AFM_DOCKER_FILE_ROOTS`` payload: the
    value is composed from the ACTUAL launch mounts — the project root plus one
    extra root per ``home.docker.run`` directory mount — and written into the
    env-file on EVERY run launch as an ENGINE line, after the CLI lines. A raw
    ``-e AFM_DOCKER_FILE_ROOTS=...`` entry is the documented escape hatch: the
    launcher engine line is then SKIPPED entirely, so the user value is the only
    occurrence and wins trivially.
    """

    def _run_with_home_mount(self, tmp_path: Path, monkeypatch, extra_env: tuple[str, ...] = ()) -> dict[str, object]:
        """Launch once with one ``-v <tmp>/data:/home/goga/data`` home token; capture the lines."""
        (tmp_path / "data").mkdir()
        config = _make_config()
        _apply_run_mode_common_mocks(tmp_path, monkeypatch)
        monkeypatch.setattr(
            _rpc_mod,
            "load_home_config",
            lambda: HomeConfig(
                env={},
                docker=DockerArgsConfig(run=["-v", f"{tmp_path}/data:/home/goga/data"]),
            ),
        )
        captured = _capture_env_file(monkeypatch)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config, extra_env=extra_env)
        return captured

    def test_env_file_writes_file_roots_after_afm_dir(self, tmp_path: Path, monkeypatch) -> None:
        """AFM_DOCKER_FILE_ROOTS lands right after AFM_DIR, composed from the launch tokens."""
        captured = self._run_with_home_mount(tmp_path, monkeypatch)
        lines = captured["lines"]

        assert "AFM_DIR=/home/goga/pipeline" in lines
        roots_lines = [line for line in lines if line.startswith("AFM_DOCKER_FILE_ROOTS=")]
        assert len(roots_lines) == 1
        assert lines.index(roots_lines[0]) > lines.index("AFM_DIR=/home/goga/pipeline")
        # the value decodes to the roots composed from the actual launch tokens
        payload = json.loads(base64.b64decode(roots_lines[0].split("=", 1)[1]))
        assert payload["roots"][0]["container_path"] == "/workspace"
        assert payload["roots"][1]["container_path"] == "/home/goga/data"

    def test_env_file_writes_file_roots_even_without_mounts(self, tmp_path: Path, monkeypatch) -> None:
        """The roots layer is written on EVERY run launch — no mounts leaves the project-only list."""
        config = _make_config()
        _apply_run_mode_common_mocks(tmp_path, monkeypatch)
        monkeypatch.setattr(
            _rpc_mod,
            "load_home_config",
            lambda: HomeConfig(env={}, docker=DockerArgsConfig(run=[])),
        )
        captured = _capture_env_file(monkeypatch)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config)

        roots_lines = [line for line in captured["lines"] if line.startswith("AFM_DOCKER_FILE_ROOTS=")]
        assert len(roots_lines) == 1
        payload = json.loads(base64.b64decode(roots_lines[0].split("=", 1)[1]))
        assert [root["container_path"] for root in payload["roots"]] == ["/workspace"]

    def test_extra_env_file_roots_cli_key_skips_launcher_line(self, tmp_path: Path, monkeypatch) -> None:
        """A raw -e AFM_DOCKER_FILE_ROOTS entry is the ONLY such line (the launcher's is skipped).

        The inverted semantics of the retired append-after behavior: the engine
        layer skips a key the CLI explicitly supplied, so the user's line keeps
        winning under docker ``--env-file`` last-write-wins without any
        duplicate launcher line.
        """
        captured = self._run_with_home_mount(tmp_path, monkeypatch, extra_env=("AFM_DOCKER_FILE_ROOTS=custom",))
        lines = captured["lines"]

        # exactly one occurrence — the CLI one, verbatim; the launcher wrote none
        assert [line for line in lines if line.startswith("AFM_DOCKER_FILE_ROOTS=")] == [
            "AFM_DOCKER_FILE_ROOTS=custom"
        ]

    def test_home_env_roots_key_lands_before_the_composed_engine_line(self, tmp_path: Path, monkeypatch) -> None:
        """A stale AFM_DOCKER_FILE_ROOTS key in home.env is superseded by the later engine line.

        home.env is a BASE layer: its lines precede the engine lines, so the
        launcher-composed value — mirroring the launch's actual mounts — is the
        last occurrence and wins under docker ``--env-file`` last-write-wins
        (only the raw ``-e`` channel wins against it, per the skip rule).
        """
        (tmp_path / "data").mkdir()
        config = _make_config()
        _apply_run_mode_common_mocks(tmp_path, monkeypatch)
        monkeypatch.setattr(
            _rpc_mod,
            "load_home_config",
            lambda: HomeConfig(
                env={"AFM_DOCKER_FILE_ROOTS": "stale-from-home"},
                docker=DockerArgsConfig(run=["-v", f"{tmp_path}/data:/home/goga/data"]),
            ),
        )
        captured = _capture_env_file(monkeypatch)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config)

        lines = captured["lines"]
        roots_lines = [line for line in lines if line.startswith("AFM_DOCKER_FILE_ROOTS=")]
        # the stale base line and the composed engine line both appear …
        assert "AFM_DOCKER_FILE_ROOTS=stale-from-home" in roots_lines
        # … and the composed one is LAST — the value that survives inside the
        # container decodes to the roots composed from the actual launch tokens
        last = roots_lines[-1]
        assert last != "AFM_DOCKER_FILE_ROOTS=stale-from-home"
        payload = json.loads(base64.b64decode(last.split("=", 1)[1]))
        assert [r["container_path"] for r in payload["roots"]] == ["/workspace", "/home/goga/data"]


# --- the CLI env carriage ladder + payload line (Task 8 scenarios) ---


class TestRunPipelineContainerEnvLadder:
    """The env-file ladder order, the payload line, the mount reduction, and the cleanup."""

    def test_run_pipeline_container_env_file_ladder_and_payload_no_pipeline_env(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """CLI before engine, pipeline.env never in the file, payload from the same source, 2 mounts, unlink."""
        config = _make_config(pipeline_agent="codex", pipeline_env={"T": "cfg"})
        runtime_dir = _apply_run_mode_common_mocks(tmp_path, monkeypatch)
        (tmp_path / "data").mkdir()
        monkeypatch.setattr(
            _rpc_mod,
            "load_home_config",
            lambda: HomeConfig(env={"H": "1"}, docker=DockerArgsConfig(run=["-v", f"{tmp_path}/data:/data"])),
        )
        captured = _capture_env_file(monkeypatch)

        recorded: dict[str, object] = {}

        def _record(_self, args, extra_args=None, **params):
            recorded["params"] = params
            return 0

        monkeypatch.setattr(_rpc_mod.DockerRunner, "run", _record)

        with mock.patch.object(subprocess, "run"):
            result = rpc(
                "deploy",
                config=config,
                extra_env=("T=cli",),
                proxy="http://p:1",
            )

        assert result == 0
        lines = captured["lines"]
        # CLI lines precede the engine lines (ladder order)
        afm_dir_idx = next(i for i, line in enumerate(lines) if line.startswith("AFM_DIR="))
        assert lines.index("T=cli") < afm_dir_idx
        # the home.env base line survives where unconflicted
        assert "H=1" in lines
        # pipeline.env NEVER enters the env-file (it applies in-container)
        assert "T=cfg" not in "\n".join(lines)
        # the payload line composes from the same parsed CLI values alone
        payload = _payload_line(lines)
        assert decode_extra_env(payload.split("=", 1)[1]) == {"T": "cli"}
        # the proxy engine lines land after the CLI line (proxy was set)
        assert lines.index("HTTP_PROXY=http://p:1") > lines.index("T=cli")
        # mounts: exactly the project and the afm state — no tmpfile mount
        mounts = recorded["params"]["v"]
        assert mounts == [
            f"{tmp_path.resolve()}:/workspace",
            f"{runtime_dir}:/home/goga/pipeline",
        ]
        assert not any("/home/goga/.afm/config.yaml" in m for m in mounts)
        # the env-file is unlinked in finally
        assert isinstance(captured["path"], Path)
        assert not captured["path"].exists()

    def test_run_pipeline_container_escape_hatch_cli_engine_key_wins(self, tmp_path: Path, monkeypatch) -> None:
        """An explicit -e AFM_DOCKER_FILE_ROOTS entry is the only such line — the launcher's is skipped."""
        config = _make_config()
        _apply_run_mode_common_mocks(tmp_path, monkeypatch)
        captured = _capture_env_file(monkeypatch)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config, extra_env=("AFM_DOCKER_FILE_ROOTS=dXNlcg==",))

        lines = captured["lines"]
        # the CLI line travels verbatim and NO second launcher-written line exists
        assert [line for line in lines if line.startswith("AFM_DOCKER_FILE_ROOTS=")] == [
            "AFM_DOCKER_FILE_ROOTS=dXNlcg=="
        ]

    def test_run_pipeline_container_payload_line_present_with_no_cli_entries(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """extra_env=() still writes exactly one payload line — the one-source rule holds on every launch.

        A regression that skips the payload line when no ``-e`` is given breaks
        the carriage silently (the container half would read an absent variable
        instead of the empty mapping), so the line is asserted on every launch.
        """
        config = _make_config()
        _apply_run_mode_common_mocks(tmp_path, monkeypatch)
        captured = _capture_env_file(monkeypatch)

        run_calls: list[object] = []

        def _record(_self, args, extra_args=None, **params):
            run_calls.append(params)
            return 0

        monkeypatch.setattr(_rpc_mod.DockerRunner, "run", _record)

        with mock.patch.object(subprocess, "run"):
            result = rpc("deploy", config=config, extra_env=())

        assert result == 0
        lines = captured["lines"]
        payload = _payload_line(lines)
        assert decode_extra_env(payload.split("=", 1)[1]) == {}
        # no non-engine KEY=VALUE line is present (extra_env was empty, home/git empty)
        assert all(line.startswith(_ENGINE_LINE_PREFIXES) or line.startswith("GOGA_EXTRA_ENV=") for line in lines)
        # the runner launched exactly once
        assert len(run_calls) == 1

    def test_run_pipeline_container_no_tmpfile_and_agent_not_resolved(self, tmp_path: Path, monkeypatch) -> None:
        """No afm-config tmpfile exists at any moment, no agent is resolved, exactly 2 engine mounts."""
        config = _make_config(pipeline_agent="codex")
        runtime_dir = _apply_run_mode_common_mocks(tmp_path, monkeypatch)

        system_tmp = Path(tempfile.gettempdir())
        seen_at_launch: list[Path] = []
        recorded: dict[str, object] = {}

        def _record(_self, args, extra_args=None, **params):
            seen_at_launch.extend(system_tmp.glob("goga-afm-config-*"))
            recorded["params"] = params
            return 0

        monkeypatch.setattr(_rpc_mod.DockerRunner, "run", _record)

        with mock.patch.object(subprocess, "run"):
            result = rpc("deploy", config=config)

        assert result == 0
        mounts = recorded["params"]["v"]
        # exactly 2 mounts: project + afm state
        assert len(mounts) == 2
        assert mounts[0] == f"{tmp_path.resolve()}:/workspace"
        assert mounts[1] == f"{runtime_dir}:/home/goga/pipeline"
        # no afm-config tmpfile existed during the run or survives it
        assert seen_at_launch == []
        assert list(system_tmp.glob("goga-afm-config-*")) == []
        # the module carries no agents import (order-independent module form)
        assert "resolve_wrapper_path" not in dir(_rpc_mod)


# --- parallel cap (run mode only) ---


class TestPipelineRunParallel:
    """Run mode threads the optional ``parallel`` cap into the in-container argv.

    ``parallel`` (int | None) is appended to the in-container run argv as
    ``--parallel <N>`` ONLY in run mode and ONLY when not None. Discovery mode
    never receives it; the Docker ``-p <port>:<port>`` port-publish token stays
    isolated from it.
    """

    def _capture_docker(self, monkeypatch) -> dict[str, object]:
        """Replace ``DockerRunner.run`` with a recorder of (args, params).

        Returns the dict populated with the captured in-container ``args`` list
        and the docker-run ``params`` dict (minus the separate ``extra_args``
        keyword). The recorded ``args`` are the post-image command — exactly the
        ``-m goga.pipeline run|list ...`` in-container argv.
        """
        captured: dict[str, object] = {"args": None, "params": None}

        def _record(_self, args, extra_args=None, **params):
            captured["args"] = list(args)
            captured["params"] = {k: v for k, v in params.items() if k != "extra_args"}
            return 0

        monkeypatch.setattr(_rpc_mod.DockerRunner, "run", _record)
        return captured

    def test_run_pipeline_container_run_appends_parallel(self, tmp_path: Path, monkeypatch) -> None:
        """Run mode appends ``--parallel <N>`` after ``--port`` (params["p"] isolated)."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)
        captured = self._capture_docker(monkeypatch)

        with mock.patch.object(subprocess, "run"):
            result = run_pipeline_container("deploy", config, parallel=4)

        assert result == 0
        args = captured["args"]
        assert "--parallel" in args
        # --parallel follows the port value (appended after --port, before launch)
        assert args.index("--parallel") > args.index("50321")
        assert args[args.index("--parallel") + 1] == "4"
        # the Docker -p <port>:<port> port-publish token is isolated from parallel
        assert captured["params"]["p"] == "50321:50321"

    def test_pipeline_container_parallel_none_omitted_in_run(self, tmp_path: Path, monkeypatch) -> None:
        """``parallel=None`` (default) omits ``--parallel`` entirely (backward compat)."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)
        captured = self._capture_docker(monkeypatch)

        with mock.patch.object(subprocess, "run"):
            result = run_pipeline_container("deploy", config, parallel=None)

        assert result == 0
        assert "--parallel" not in captured["args"]


# --- workflow decision + skip names on the in-container argv channel ---


def _record_docker_run(monkeypatch) -> dict[str, object]:
    """Replace ``DockerRunner.run`` with a recorder of (args, params).

    Returns the dict populated with the captured in-container ``args`` list and
    the docker-run ``params`` dict (minus the separate ``extra_args`` keyword).
    The recorded ``args`` are the post-image command — exactly the
    ``-m goga.pipeline run ...`` in-container argv.
    """
    captured: dict[str, object] = {"args": None, "params": None}

    def _record(_self, args, extra_args=None, **params):
        captured["args"] = list(args)
        captured["params"] = {k: v for k, v in params.items() if k != "extra_args"}
        return 0

    monkeypatch.setattr(_rpc_mod.DockerRunner, "run", _record)
    return captured


class TestRunArgvWorkflowSkipChannel:
    """The workflow decision and the skip names travel as in-container argv flags.

    Step 11: ``["-m","goga.pipeline","run",name,"--port",port]`` then ``-w`` /
    ``--no-workflow`` (never both), then one ``-s`` per skip name, then
    ``--parallel``. The exact ORDER is asserted — it prevents flag drift such
    as ``--parallel`` jumping ahead of the ``-s`` entries — and no run
    coordination reaches the env-file (see test_run_pipeline_container_workflow).
    """

    def test_run_argv_carries_workflow_flags_skip_and_parallel(self, tmp_path: Path, monkeypatch) -> None:
        """Explicit workflow + two skips + parallel produce that exact argv tail."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)
        captured = _record_docker_run(monkeypatch)

        with mock.patch.object(subprocess, "run"):
            result = run_pipeline_container(
                "deploy", config, workflow="hardening", no_workflow=False, skip=("build", "test"), parallel=2
            )

        assert result == 0
        assert captured["args"] == [
            "-m",
            "goga.pipeline",
            "run",
            "deploy",
            "--port",
            "50321",
            "-w",
            "hardening",
            "-s",
            "build",
            "-s",
            "test",
            "--parallel",
            "2",
        ]

    def test_run_argv_no_workflow_flag_when_disabled(self, tmp_path: Path, monkeypatch) -> None:
        """``no_workflow=True`` carries ``--no-workflow`` and never ``-w``."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)
        captured = _record_docker_run(monkeypatch)

        with mock.patch.object(subprocess, "run"):
            result = run_pipeline_container("deploy", config, no_workflow=True, skip=("build",))

        assert result == 0
        assert captured["args"] == [
            "-m",
            "goga.pipeline",
            "run",
            "deploy",
            "--port",
            "50321",
            "--no-workflow",
            "-s",
            "build",
        ]

    def test_run_argv_auto_match_carries_neither_workflow_flag(self, tmp_path: Path, monkeypatch) -> None:
        """No workflow flags carries neither ``-w`` nor ``--no-workflow`` (in-container auto-match)."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)
        captured = _record_docker_run(monkeypatch)

        with mock.patch.object(subprocess, "run"):
            result = run_pipeline_container("deploy", config)

        assert result == 0
        assert captured["args"] == ["-m", "goga.pipeline", "run", "deploy", "--port", "50321"]


# --- no credential mounts (user-owned provisioning) ---


class TestNoCredentialMounts:
    """The launcher mounts exactly the two engine mounts — nothing else.

    Credential provisioning is user-owned (``home.docker.run`` / ``-e``): the
    docker-run mount list is the project and the persistent afm state. Decoy
    credential files are planted under an isolated HOME so any reintroduced
    credential loop would surface as a third mount.
    """

    def test_no_credential_mounts_in_run_launcher(self, tmp_path: Path, monkeypatch) -> None:
        """Run mode mounts exactly the two engine mounts — no credential entries."""
        config = _make_config()
        # Decoy credential files under an isolated HOME: a reintroduced
        # credential-detection loop would find and mount them.
        monkeypatch.setenv("HOME", str(tmp_path))
        (tmp_path / ".claude").mkdir()
        (tmp_path / ".claude" / ".credentials.json").write_text("{}")
        (tmp_path / ".codex").mkdir()
        (tmp_path / ".codex" / "auth.json").write_text("{}")
        monkeypatch.setattr("goga.runtime.paths.resolve_git_branch", lambda: "default")
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)
        captured = _record_docker_run(monkeypatch)

        with mock.patch.object(subprocess, "run"):
            result = run_pipeline_container("deploy", config)

        assert result == 0
        runtime_dir = _rpc_mod.resolve_pipeline_runtime_dir("deploy")
        mounts = captured["params"]["v"]
        # exactly the two engine mounts, in order
        assert len(mounts) == 2
        assert mounts[0] == f"{tmp_path.resolve()}:/workspace"
        assert mounts[1] == f"{runtime_dir}:/home/goga/pipeline"
        # no credential entries anywhere in the mount list; no read-only mount
        # exists at all (the retired tmpfile was the only one)
        assert not any("/home/goga/.claude" in m for m in mounts)
        assert not any("/home/goga/.codex" in m for m in mounts)
        assert not any("/home/goga/.local" in m for m in mounts)
        assert not any(m.endswith(":ro") for m in mounts)


# --- cleanup on setup failure ---


class TestRunModeCleanup:
    def test_run_mode_unlinks_env_file_when_launch_fails(self, tmp_path: Path, monkeypatch) -> None:
        """A failure after the env-file is written still unlinks it.

        The env-file is created inside the try whose finally unlinks it, so an
        exception from the image-acquisition window (the first-run build, the
        ``docker_update`` refresh) cannot leak the secret env-file.
        """
        config = _make_config()
        _apply_run_mode_common_mocks(tmp_path, monkeypatch)
        captured = _capture_env_file(monkeypatch)

        def _raising_ensure(*_args, **_kwargs) -> int:
            raise RuntimeError("first-run build failed")

        monkeypatch.setattr(_rpc_mod, "docker_build_if_not_exist", _raising_ensure)

        with (
            mock.patch.object(subprocess, "Popen"),
            mock.patch.object(subprocess, "run"),
            pytest.raises(click.ClickException, match="first-run build failed"),
        ):
            run_pipeline_container("deploy", config)

        # the env-file was created, then unlinked despite the failure
        assert isinstance(captured["path"], Path)
        assert not captured["path"].exists()


# --- failure modes ---


class TestPipelineFailureModes:
    def test_pipeline_raises_clickexception_when_docker_missing(self, monkeypatch) -> None:
        """Missing docker raises a ClickException mentioning docker."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: False)

        with pytest.raises(click.ClickException, match="docker"):
            run_pipeline_container("deploy", config)

    def test_pipeline_raises_clickexception_when_config_image_is_none(self, monkeypatch) -> None:
        """A None image raises a ClickException mentioning image."""
        config = _make_config(image=None)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)

        with pytest.raises(click.ClickException, match="image"):
            run_pipeline_container("deploy", config)


# --- image pull ---


class TestPipelinePullImage:
    def test_pipeline_pull_image_failure_warns_and_continues(self, tmp_path: Path, monkeypatch, caplog) -> None:
        """A failing `docker pull` is logged as a warning and the launch proceeds."""
        import logging

        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        # The new persistent-dir flow resolves the afm runtime dir (which calls
        # git); isolate it from the broadly-mocked subprocess.run below, and
        # redirect HOME so the runtime dir and the home config load stay under
        # tmp_path.
        monkeypatch.setattr("goga.runtime.paths.resolve_git_branch", lambda: "default")
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.chdir(tmp_path)

        def fake_run(cmd, *args, **kwargs):
            # `docker pull` fails; other docker calls (kill cleanup) succeed.
            if cmd[:2] == ["docker", "pull"]:
                return mock.Mock(returncode=1)
            return mock.Mock(returncode=0)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run", side_effect=fake_run),
            caplog.at_level(logging.WARNING, logger=_rpc_mod.logger.name),
        ):
            # update=True gates the image pull (no pull by default under the
            # extended contract); the failing pull must warn and continue.
            result = run_pipeline_container("deploy", config, (), None, {}, False, True)

        # a warning was emitted for the failed pull, and the launch still proceeded
        assert any("failed to pull image" in rec.message for rec in caplog.records)
        assert result == 0


# --- signal handling ---


class TestPipelineSignals:
    def test_pipeline_run_installs_and_restores_sigterm_handler(self, tmp_path: Path, monkeypatch) -> None:
        """SIGTERM handler is installed at start and restored at end (caller + runner).

        Run mode installs a CALLER-side SIGTERM handler (D7, before the secret
        env-file is written) and ``DockerRunner`` installs its OWN handler that
        nests under it. Both the pipeline module and the runner bind the same
        stdlib ``signal`` module, so patching ``_rpc_mod.signal.signal`` captures
        both layers: caller install/restore (2) + runner install/restore (2) =
        4 SIGTERM calls.
        """
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(_rpc_mod.signal, "signal") as mock_signal,
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config)

        sigterm_calls = [c for c in mock_signal.call_args_list if c.args and c.args[0] == signal.SIGTERM]
        # caller install + runner install + runner restore + caller restore
        assert len(sigterm_calls) == 4

    def test_pipeline_run_returns_130_on_sigint(self, tmp_path: Path, monkeypatch) -> None:
        """SIGINT during run results in exit code 130 and a docker kill."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)

        captured: dict[int, object] = {}

        def fake_signal(sig: int, handler: object) -> object:
            captured[sig] = handler
            return signal.SIG_DFL

        def fake_wait() -> int:
            # invoke the installed SIGINT handler inline, as a real signal would
            handler = captured[signal.SIGINT]
            handler(signal.SIGINT, None)
            return 0

        mock_proc = mock.Mock()
        mock_proc.wait = fake_wait

        with (
            mock.patch.object(_rpc_mod.signal, "signal", side_effect=fake_signal),
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run") as mock_run,
            pytest.raises(SystemExit) as exc,
        ):
            run_pipeline_container("deploy", config)

        assert exc.value.code == 130
        # the handler (and/or finally) ran `docker kill` via subprocess.run
        kill_calls = [c for c in mock_run.call_args_list if c.args and c.args[0][:2] == ["docker", "kill"]]
        assert kill_calls

    def test_pipeline_run_propagates_127_when_afm_missing_in_container(self, tmp_path: Path, monkeypatch) -> None:
        """afm missing inside the container propagates exit code 127."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 127
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            result = run_pipeline_container("deploy", config)

        assert result == 127


# --- D7 leak-prevention invariant ---


class TestRunModeCallerHandlerD7:
    def test_caller_handler_installed_before_secret_file(self, tmp_path: Path, monkeypatch) -> None:
        """D7: the caller SIGTERM/SIGINT handler is installed BEFORE the env-file is written.

        Run mode installs a caller-side handler before writing the secret file so
        a signal during the setup window — including the docker_update build —
        unwinds to the caller finally and unlinks the secret file. The runner's
        own handler is installed later (inside DockerRunner.run, after the file
        is written), so at the write the caller has already installed BOTH
        handlers (2 signal calls). The env-file is the ONLY secret file since
        the afm-config tmpfile flow was retired.
        """
        config = _make_config()
        _apply_run_mode_common_mocks(tmp_path, monkeypatch)

        install_count = {"n": 0}

        def fake_signal(_sig: int, _handler: object) -> object:
            install_count["n"] += 1
            return mock.DEFAULT

        monkeypatch.setattr(_rpc_mod.signal, "signal", mock.MagicMock(side_effect=fake_signal))

        writes: list[tuple[str, int]] = []
        real_env = _rpc_mod._write_env_file

        def env_wrap(lines: list[str]) -> Path:
            writes.append(("env", install_count["n"]))
            return real_env(lines)

        monkeypatch.setattr(_rpc_mod, "_write_env_file", env_wrap)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config)

        # the only secret file was written; the caller handler (2 installs) ran first
        assert [name for name, _ in writes] == ["env"]
        assert all(n >= 2 for _name, n in writes)
