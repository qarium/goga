from __future__ import annotations

import signal
import subprocess
import sys
from pathlib import Path
from unittest import mock

import click
import pytest
from goga.commands.pipeline import run_pipeline_container
from goga.commands.pipeline.run_pipeline_container import run_pipeline_container as rpc
from goga.config import BuildConfig, PipelineConfig, ProjectConfig, TaskExecutorConfig

# Resolve the real submodule via sys.modules (the package __init__ binds the
# function name `run_pipeline_container`, which would shadow string-based
# mock.patch paths walking through the package on Python 3.10).
_rpc_mod = sys.modules["goga.commands.pipeline.run_pipeline_container"]


def _make_config(
    *,
    image: str | None = "qarium/goga:latest",
    pipeline_agent: str = "claude",
    pipeline_env: dict[str, str] | None = None,
) -> ProjectConfig:
    """Build a minimal ProjectConfig satisfying the new schema (top-level image, pipeline block)."""
    return ProjectConfig(
        lang="python",
        image=image,
        dockerfile=None,
        build=BuildConfig(task_executor=TaskExecutorConfig(agent="claude")),
        pipeline=PipelineConfig(agent=pipeline_agent, env=pipeline_env or {}),
    )


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


# --- Run mode docker command shape ---


class TestPipelineRunCommand:
    def test_pipeline_run_launches_container_with_port_and_afm_config(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        """Run mode publishes the port, mounts the afm config, passes env-file, no dashboard URL."""
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
        # afm config mounted read-only at the in-container path
        assert any(arg.endswith(":/home/goga/.afm/config.yaml:ro") for arg in cmd)
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


# --- afm config tmpfile ---


class TestAfmConfigTmpfile:
    def test_pipeline_run_writes_afm_config_tmpfile_with_client_command(self) -> None:
        """The afm-config tmpfile carries the resolved wrapper path and static constants.

        The overlay carries five static launcher-side fields: ``client.command``
        (the absolute wrapper path returned by ``resolve_wrapper_path`` — never
        a bare agent name), ``theme: goga`` (dashboard theme),
        ``open_browser: false`` (the dashboard is reached via the host-printed
        http://localhost:<port> URL; afm must not attempt to open a browser
        inside the container), ``proxy.enabled: false`` (afm's own internal
        outbound proxy provider is disabled — goga manages the outbound proxy
        via the container env-file; ``proxy`` is a nested YAML map), and
        ``prompts_dir`` (the fixed ``/home/goga/pipeline/prompts`` path afm
        reads the four agent prompt files from). See the CODEMANIFEST
        Requirement/Constraint for ``run_pipeline_container``. The writer is
        value-agnostic, so a realistic resolved path is passed here to pin the
        documented contract.
        """
        wrapper_path = "/home/goga/bin/claude-as-claude.sh"
        afm_path = _rpc_mod._write_afm_config_tmpfile(wrapper_path)
        try:
            content = afm_path.read_text()
            mode = afm_path.stat().st_mode & 0o777
        finally:
            afm_path.unlink(missing_ok=True)

        assert content == (
            f"client:\n  command: {wrapper_path}\ntheme: goga\nopen_browser: false\n"
            "proxy:\n  enabled: false\nprompts_dir: /home/goga/pipeline/prompts\n"
        )
        assert mode == 0o600

    def test_write_afm_config_tmpfile_includes_prompts_dir(self) -> None:
        """The afm-config tmpfile carries the fifth static field ``prompts_dir``.

        Structural YAML validation (not substring search): the overlay parses to
        a dict where ``prompts_dir`` is the fixed in-container path
        ``/home/goga/pipeline/prompts`` (the ``AFM_DIR`` constant + ``prompts``,
        where ``run_pipeline`` materializes the four agent prompt files), and
        ``proxy`` remains a nested map (``{"enabled": False}``) rather than a
        flat dotted-key. The tmpfile is private (mode 0600).
        """
        import yaml

        wrapper_path = "/home/goga/bin/codex-as-claude.sh"
        afm_path = _rpc_mod._write_afm_config_tmpfile(wrapper_path)
        try:
            content = afm_path.read_text()
            mode = afm_path.stat().st_mode & 0o777
        finally:
            afm_path.unlink(missing_ok=True)

        parsed = yaml.safe_load(content)
        assert parsed["client"] == {"command": "/home/goga/bin/codex-as-claude.sh"}
        assert parsed["theme"] == "goga"
        assert parsed["open_browser"] is False
        assert parsed["prompts_dir"] == "/home/goga/pipeline/prompts"
        # proxy is a nested map, not a flat dotted-key
        assert parsed["proxy"] == {"enabled": False}
        # anti-regression: a flat dotted-key must not appear as a top-level key
        assert "client.command" not in parsed
        assert "proxy.enabled" not in parsed
        assert mode == 0o600

    def test_run_pipeline_container_run_mode_propagates_prompts_dir_via_config_tmpfile(
        self, tmp_path: Path, monkeypatch
    ) -> None:
        """Run mode mounts a tmpfile whose YAML carries ``prompts_dir`` to the container.

        The launcher-side afm-config tmpfile (mounted read-only at the fixed
        in-container path ``/home/goga/.afm/config.yaml``) must carry
        ``prompts_dir: /home/goga/pipeline/prompts`` as a valid YAML key, and
        ``proxy`` must remain a nested map — this is what afm actually reads to
        locate the four agent prompt files materialized in-container.
        """
        import yaml

        config = _make_config(pipeline_agent="claude")
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)

        # The launcher's finally block unlinks the afm-config tmpfile, so the
        # writer is wrapped to copy the bytes to a path under tmp_path before
        # the return — the captured copy survives the unlink.
        captured_afm = tmp_path / "captured-afm-config.yaml"
        real_afm = _rpc_mod._write_afm_config_tmpfile

        def capture_afm(wrapper_path: str) -> Path:
            path = real_afm(wrapper_path)
            captured_afm.write_bytes(path.read_bytes())
            return path

        monkeypatch.setattr(_rpc_mod, "_write_afm_config_tmpfile", capture_afm)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            result = run_pipeline_container("deploy", config)

        assert result == 0
        docker_argv = mock_popen.call_args[0][0]
        # the tmpfile is mounted read-only at the fixed in-container path; this
        # raises StopIteration if the mount is absent (the contract under test).
        config_mount = next(a for a in docker_argv if "/home/goga/.afm/config.yaml:ro" in a)
        # the mounted tmpfile is unlinked by the launcher's finally block; the
        # captured copy holds the same bytes, so validate it as YAML.
        assert config_mount.split(":")[0]  # the tmpfile path was non-empty
        content = captured_afm.read_text()
        parsed = yaml.safe_load(content)
        assert parsed["prompts_dir"] == "/home/goga/pipeline/prompts"
        assert parsed["proxy"] == {"enabled": False}


# --- env file combination ---


class TestPipelineEnvFile:
    def test_pipeline_env_file_combines_pipeline_env_and_git(self, tmp_path: Path, monkeypatch) -> None:
        """The env file merges config.pipeline.env and git identity (non-overlapping keys)."""
        config = _make_config(pipeline_env={"FOO": "1"})
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {"GIT_AUTHOR_NAME": "u"})
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.chdir(tmp_path)

        captured_env: dict[str, str] = {}
        real_write = _rpc_mod._write_env_file

        def capture(env: dict[str, str], extra_env: tuple[str, ...] = ()) -> Path:
            captured_env.update(env)
            return real_write(env, extra_env)

        monkeypatch.setattr(_rpc_mod, "_write_env_file", capture)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config)

        # pipeline.env + git identity are merged into the env dict.
        assert captured_env["FOO"] == "1"
        assert captured_env["GIT_AUTHOR_NAME"] == "u"

    def test_pipeline_env_overrides_git_on_conflict(self, tmp_path: Path, monkeypatch) -> None:
        """config.pipeline.env wins over git identity when the same key is set in both.

        Mirrors goga/commands/build where task_executor.env overrides git env
        (env = {**git_env, **config.pipeline.env}).
        """
        config = _make_config(pipeline_env={"GIT_AUTHOR_NAME": "from-pipeline"})
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {"GIT_AUTHOR_NAME": "from-git"})
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.chdir(tmp_path)

        captured_env: dict[str, str] = {}
        real_write = _rpc_mod._write_env_file

        def capture(env: dict[str, str], extra_env: tuple[str, ...] = ()) -> Path:
            captured_env.update(env)
            return real_write(env, extra_env)

        monkeypatch.setattr(_rpc_mod, "_write_env_file", capture)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config)

        assert captured_env["GIT_AUTHOR_NAME"] == "from-pipeline"

    def test_pipeline_env_file_appends_extra_env_lines(self, tmp_path: Path, monkeypatch) -> None:
        """`extra_env` KEY=VALUE strings are appended to the env-file verbatim.

        Mirrors `goga/commands/build._write_env_file`: no validation, later
        duplicates override earlier ones inside the container (Docker
        `--env-file` semantics). Default empty tuple writes the same content as
        before the option existed.
        """
        env_path = _rpc_mod._write_env_file({"FOO": "1"}, ("BAR=2", "BAZ=qux"))
        try:
            content = env_path.read_text()
        finally:
            env_path.unlink(missing_ok=True)

        lines = content.splitlines()
        assert "FOO=1" in lines
        assert "BAR=2" in lines
        assert "BAZ=qux" in lines
        # extra_env lines come after the dict lines
        assert lines.index("BAR=2") > lines.index("FOO=1")

    def test_pipeline_env_file_default_extra_env_is_empty(self, tmp_path: Path, monkeypatch) -> None:
        """Default `extra_env=()` writes the same content as before the option."""
        env_path = _rpc_mod._write_env_file({"FOO": "1"})
        try:
            content = env_path.read_text()
        finally:
            env_path.unlink(missing_ok=True)

        assert content == "FOO=1\n"

    def test_pipeline_run_forwards_extra_env_to_write_env_file(self, tmp_path: Path, monkeypatch) -> None:
        """Run mode forwards extra_env to _write_env_file in run mode."""
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)

        captured: dict[str, object] = {}
        real_write = _rpc_mod._write_env_file

        def capture(env: dict[str, str], extra_env: tuple[str, ...] = ()) -> Path:
            captured["env"] = dict(env)
            captured["extra_env"] = extra_env
            return real_write(env, extra_env)

        monkeypatch.setattr(_rpc_mod, "_write_env_file", capture)

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

        assert captured["extra_env"] == ("ANTHROPIC_API_KEY=sk-xxx", "MODEL=claude-sonnet-4-6")


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


# --- cleanup on setup failure ---


class TestRunModeCleanup:
    def test_run_mode_unlinks_afm_tmpfile_when_env_write_fails(self, tmp_path: Path, monkeypatch) -> None:
        """A failure after the afm tmpfile is written still unlinks it.

        The temp files are created inside the try whose finally unlinks them, so
        an exception from ``_write_env_file`` (disk error, etc.) cannot leak the
        afm-config tmpfile — and, symmetrically, the env file with secrets.
        """
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)

        created_afm: list[Path] = []
        real_afm = _rpc_mod._write_afm_config_tmpfile

        def track_afm(agent: str) -> Path:
            path = real_afm(agent)
            created_afm.append(path)
            return path

        monkeypatch.setattr(_rpc_mod, "_write_afm_config_tmpfile", track_afm)

        def raising_write(env: dict[str, str], extra_env: tuple[str, ...] = ()) -> Path:
            raise OSError("disk full")

        monkeypatch.setattr(_rpc_mod, "_write_env_file", raising_write)

        with (
            mock.patch.object(_rpc_mod.signal, "signal"),
            mock.patch.object(subprocess, "run"),
            pytest.raises(OSError, match="disk full"),
        ):
            run_pipeline_container("deploy", config)

        # the afm tmpfile was unlinked despite the failure in _write_env_file
        assert created_afm
        assert all(not p.exists() for p in created_afm)


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
        # redirect HOME so both the runtime dir and credential detection stay
        # under tmp_path.
        monkeypatch.setattr("goga.runtime.paths.resolve_git_branch", lambda: "default")
        monkeypatch.setattr(_rpc_mod, "resolve_credential_mounts", lambda: [])
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
        files are written) and ``DockerRunner`` installs its OWN handler that
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
    def test_caller_handler_installed_before_secret_files(self, tmp_path: Path, monkeypatch) -> None:
        """D7: the caller SIGTERM/SIGINT handler is installed BEFORE the afm-config
        tmpfile and env-file are written.

        Run mode installs a caller-side handler before writing the secret files so
        a signal during the setup window — including the docker_update build —
        unwinds to the caller finally and unlinks the secret files. The runner's
        own handler is installed later (inside DockerRunner.run, after both files
        are written), so at each write the caller has already installed BOTH
        handlers (2 signal calls).
        """
        config = _make_config()
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
        monkeypatch.chdir(tmp_path)

        install_count = {"n": 0}

        def fake_signal(_sig: int, _handler: object) -> object:
            install_count["n"] += 1
            return mock.DEFAULT

        monkeypatch.setattr(_rpc_mod.signal, "signal", mock.MagicMock(side_effect=fake_signal))

        writes: list[tuple[str, int]] = []
        real_afm = _rpc_mod._write_afm_config_tmpfile
        real_env = _rpc_mod._write_env_file

        def afm_wrap(wrapper_path: str) -> Path:
            writes.append(("afm", install_count["n"]))
            return real_afm(wrapper_path)

        def env_wrap(env: dict[str, str], extra_env: tuple[str, ...] = ()) -> Path:
            writes.append(("env", install_count["n"]))
            return real_env(env, extra_env)

        monkeypatch.setattr(_rpc_mod, "_write_afm_config_tmpfile", afm_wrap)
        monkeypatch.setattr(_rpc_mod, "_write_env_file", env_wrap)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(subprocess, "Popen", return_value=mock_proc),
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", config)

        # both secret files were written; the caller handler (2 installs) ran first
        assert [name for name, _ in writes] == ["afm", "env"]
        assert all(n >= 2 for _name, n in writes)
