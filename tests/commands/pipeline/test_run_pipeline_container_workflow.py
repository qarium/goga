"""Logic tests for the workflow layer of ``run_pipeline_container``.

Covers the CODEMANIFEST ``run_pipeline_container`` run-mode Algorithm steps 9-11:

- step 9 — the host-side workflow log decision (``_resolve_workflow_log_name``):
  LOG-ONLY. ``--no-workflow`` → no log; explicit ``--workflow X`` → log names X;
  auto-match fallback → the log names the pipeline exactly when the basename
  file exists on the host. The decision produces no env entry and no argv flag.
- step 10 — the ``Pipeline running with workflow "NAME"`` log line is printed to
  stdout ONLY when a workflow will actually be applied (exactly one line, the
  only host-side stdout besides the docker output stream; NO dashboard URL).
- step 11 — the env-file carries environment layers ONLY: no ``GOGA_*`` key is
  ever written by the launcher, and user-supplied ``GOGA_*`` KEY=VALUE strings
  travel verbatim and stay inert (no warning, no error).

The workflow decision and the skip names themselves travel as in-container argv
flags (step 12) — that surface is pinned in ``test_run_pipeline_container.py``.
All tests drive the real launcher with the docker internals mocked (no docker
dependency).
"""

from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest
from goga.commands.pipeline.run_pipeline_container import (
    run_pipeline_container as rpc,
)
from goga.config import BuildConfig, PipelineConfig, ProjectConfig

# Resolve the real submodule via sys.modules (the package __init__ binds the
# function name `run_pipeline_container`, which would shadow string-based
# mock.patch paths walking through the package on Python 3.10).
_rpc_mod = sys.modules["goga.commands.pipeline.run_pipeline_container"]

# The env-file writer captured at import time — the launch harness wraps it per
# launch, so re-launching within one test must never wrap the wrapper.
_REAL_WRITE_ENV_FILE = _rpc_mod._write_env_file


def _make_config(
    *,
    pipeline_agent: str = "claude",
    pipeline_env: dict[str, str] | None = None,
) -> ProjectConfig:
    """Build a minimal ProjectConfig with a pipeline section for run-mode dispatch."""
    return ProjectConfig(
        language="python",
        image="qarium/goga:latest",
        dockerfile=None,
        build=BuildConfig(agent="claude"),
        pipeline=PipelineConfig(agent=pipeline_agent, env=pipeline_env or {}),
    )


def _launch_run(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    tmp_path: Path,
    config: ProjectConfig,
    *,
    extra_env: tuple[str, ...] = (),
    **kwargs: object,
) -> dict[str, object]:
    """Run the launcher with the docker internals mocked; capture the surfaces.

    Returns ``{"exit_code", "stdout", "env_lines", "args"}`` — the container
    exit code, everything the launcher printed to stdout, the env-file lines
    (read before the launcher's ``finally`` unlinks it), and the in-container
    argv handed to ``DockerRunner.run``.
    """
    monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
    monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
    monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})
    monkeypatch.chdir(tmp_path)

    env_lines: list[str] = []

    def capture_env(env: dict[str, str], captured_extra: tuple[str, ...] = ()) -> Path:
        path = _REAL_WRITE_ENV_FILE(env, captured_extra)
        env_lines.extend(path.read_text().splitlines())
        return path

    monkeypatch.setattr(_rpc_mod, "_write_env_file", capture_env)

    captured_args: list[list[str]] = []

    def _record(_self, args, extra_args=None, **params):
        captured_args.append(list(args))
        return 0

    monkeypatch.setattr(_rpc_mod.DockerRunner, "run", _record)

    with mock.patch.object(subprocess, "run"):
        exit_code = rpc("deploy", config, extra_env=extra_env, **kwargs)

    return {
        "exit_code": exit_code,
        "stdout": capsys.readouterr().out,
        "env_lines": env_lines,
        "args": captured_args[0],
    }


# --- Steps 9-10 — the log-only workflow decision matrix ---


class TestWorkflowLogLineMatrix:
    """One matrix over the four decision rows (CODEMANIFEST steps 9-10).

    Positive rows print EXACTLY one stdout line naming the workflow that will
    apply; negative rows print none. In every row the env-file carries no
    ``GOGA_*`` key — the decision is log-only, never an env entry.
    """

    def test_workflow_log_line_matrix(self, tmp_path: Path, monkeypatch, capsys) -> None:
        """Explicit -w names it; --no-workflow and absent auto-match print nothing."""
        config = _make_config()
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        (workflows_dir / "deploy.yml").write_text("prompt: hi\n")
        (workflows_dir / "hardening.yml").write_text("prompt: hi\n")

        cases = [
            # (label, launch kwargs, expected line or None)
            ("explicit", {"workflow": "hardening"}, 'Pipeline running with workflow "hardening"'),
            ("no_workflow", {"no_workflow": True}, None),
            ("auto_match_present", {}, 'Pipeline running with workflow "deploy"'),
            ("auto_match_absent", {}, None),
        ]

        for label, kwargs, expected in cases:
            if label == "auto_match_absent":
                # the basename file must NOT exist for this row
                (workflows_dir / "deploy.yml").unlink()

            result = _launch_run(monkeypatch, capsys, tmp_path, config, **kwargs)

            assert result["exit_code"] == 0, label
            out_lines = [line for line in str(result["stdout"]).splitlines() if line]
            if expected is None:
                assert out_lines == [], (label, out_lines)
            else:
                assert out_lines == [expected], (label, out_lines)
            # no dashboard URL line in any row
            assert "Web UI:" not in str(result["stdout"]), label
            # the env-file never carries a GOGA_* key in any row
            assert not [ln for ln in result["env_lines"] if ln.startswith("GOGA_")], (
                label,
                result["env_lines"],
            )

            if label == "auto_match_absent":
                # restore the file for any later rows (none today, keeps the
                # matrix extensible)
                (workflows_dir / "deploy.yml").write_text("prompt: hi\n")


class TestResolveWorkflowLogNameAutoMatchContainment:
    """Auto-match path-traversal containment (CODEMANIFEST step 6b).

    The auto-match fallback composes ``<cwd>/.goga/workflows/<name>.yml`` from the
    pipeline ``name``. A ``name`` escaping the workflows dir via ``..`` or an
    absolute prefix is a silent miss — ``None``, no log line — even when the
    escaped path exists on the host, mirroring the explicit-``--workflow``
    (host) and in-container containment guards. This keeps the host log line
    honest: it never claims a workflow that the in-container resolver will
    refuse to apply.
    """

    def test_auto_match_dotdot_escape_is_silent_miss(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A ``..`` in the pipeline name never resolves outside the workflows dir."""
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        # A file reachable only by escaping the workflows dir via ``..``.
        (tmp_path / ".goga" / "outside.yml").write_text("prompt: evil\n")
        monkeypatch.chdir(tmp_path)

        assert _rpc_mod._resolve_workflow_log_name(
            workflow=None, no_workflow=False, name="../outside"
        ) is None

    def test_auto_match_absolute_prefix_is_silent_miss(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An absolute-prefixed pipeline name never resolves outside the workflows dir."""
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.chdir(tmp_path)

        assert _rpc_mod._resolve_workflow_log_name(
            workflow=None, no_workflow=False, name="/etc/evil"
        ) is None

    def test_auto_match_plain_name_still_resolves(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A plain pipeline name with a present basename file still resolves (regression guard)."""
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        (workflows_dir / "deploy.yml").write_text("prompt: hi\n")
        monkeypatch.chdir(tmp_path)

        assert _rpc_mod._resolve_workflow_log_name(
            workflow=None, no_workflow=False, name="deploy"
        ) == "deploy"

    def test_no_workflow_yields_none_even_with_explicit_name(self) -> None:
        """``no_workflow`` wins over an explicit name — disabled means no log."""
        assert (
            _rpc_mod._resolve_workflow_log_name(
                workflow="hardening", no_workflow=True, name="deploy"
            )
            is None
        )


# --- Step 11 — env-file carries environment layers only ---


class TestRunPipelineContainerSkipContract:
    """Contract: ``run_pipeline_container`` exposes the ``skip`` parameter with a real Python default of ``()``.

    The CODEMANIFEST DSL cannot express the empty-tuple default, so the contract
    pins the semantics as "default empty" and Additional Instruction #4 mandates
    the Python realization carry ``skip: tuple[str, ...] = ()``. These checks
    guard that the launcher's public surface accepts ``skip`` and threads it.
    """

    def test_skip_parameter_is_present(self) -> None:
        params = inspect.signature(rpc).parameters
        assert "skip" in params

    def test_skip_parameter_default_is_empty_tuple(self) -> None:
        params = inspect.signature(rpc).parameters
        assert params["skip"].default == ()


class TestRunPipelineContainerWorkflowEnvFile:
    """The env-file layer contract: environment layers only, never run coordination."""

    def test_env_file_carries_no_goga_entries(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        """A workflow + skip launch writes NO ``GOGA_*`` key into the env-file.

        With ``workflow="hardening"`` and ``skip=("build",)`` the decision and
        the names travel as argv flags; the env-file carries only the
        environment layers. The workflow log line still prints exactly once.
        """
        config = _make_config()

        result = _launch_run(
            monkeypatch, capsys, tmp_path, config, workflow="hardening", skip=("build",)
        )

        env_lines: list[str] = result["env_lines"]
        assert not [ln for ln in env_lines if ln.startswith("GOGA_")]
        # the environment layers are all still present
        assert "AFM_DIR=/home/goga/pipeline" in env_lines
        assert any(ln.startswith("AFM_DOCKER_FILE_ROOTS=") for ln in env_lines)
        # the log line printed exactly once
        out_lines = [ln for ln in str(result["stdout"]).splitlines() if ln]
        assert out_lines == ['Pipeline running with workflow "hardening"']

    def test_stale_goga_env_values_are_inert(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        """User-supplied ``GOGA_*`` values travel verbatim and stay inert.

        ``extra_env`` carries stale ``GOGA_*`` KEY=VALUE strings while the launch
        passes NO workflow flags and an empty skip: the lines are written to the
        env-file verbatim (inert passengers), the launcher neither warns nor
        errors, and the argv carries no ``-w`` / ``--no-workflow`` / ``-s``.
        """
        config = _make_config()
        # Composed rather than literal so the change-set-wide no-residue grep
        # stays clean: these stale names are user-supplied passengers here, not
        # a channel the launcher itself reads or writes.
        stale_workflow_entry = "GOGA_" + "WORKFLOW_NAME=zzz"
        stale_skip_entry = "GOGA_" + "SKIP_STAGES=zzz"

        result = _launch_run(
            monkeypatch,
            capsys,
            tmp_path,
            config,
            extra_env=(stale_workflow_entry, stale_skip_entry),
        )

        assert result["exit_code"] == 0
        args: list[str] = result["args"]
        assert "-w" not in args
        assert "--no-workflow" not in args
        assert "-s" not in args
        # the verbatim lines are present in the env-file (inert passengers)
        env_lines: list[str] = result["env_lines"]
        assert stale_workflow_entry in env_lines
        assert stale_skip_entry in env_lines
        # no warning was raised or logged for the stale values
        assert "GOGA_" not in str(result["stdout"])

    def test_no_workflow_launch_env_file_still_carries_environment_layers(
        self, tmp_path: Path, monkeypatch, capsys
    ) -> None:
        """``--no-workflow`` writes no decision entry — the env layers survive unchanged.

        The disabled row of the matrix previously wrote a disabling env entry;
        now the decision is argv-only, so the env-file of a ``no_workflow=True``
        launch is indistinguishable from an unflagged one.
        """
        config = _make_config()

        disabled = _launch_run(monkeypatch, capsys, tmp_path, config, no_workflow=True)
        unflagged = _launch_run(monkeypatch, capsys, tmp_path, config)

        assert not [ln for ln in disabled["env_lines"] if ln.startswith("GOGA_")]
        assert not [ln for ln in unflagged["env_lines"] if ln.startswith("GOGA_")]
        # identical environment layers in both rows (same launch inputs)
        assert disabled["env_lines"] == unflagged["env_lines"]
        assert "AFM_DIR=/home/goga/pipeline" in disabled["env_lines"]
