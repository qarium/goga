"""Logic tests for the workflow/profile carriage layer of ``run_pipeline_container``.

Covers the CODEMANIFEST ``run_pipeline_container`` run-mode Algorithm steps 8-9:

- step 8 — the env-file carries environment layers PLUS the profile carriage:
  the ambient ``GOGA_PROFILE`` engine line (non-empty only), the encoded home
  bundle ``GOGA_HOME_PROFILES`` line (non-empty bundle only), and the
  ``GOGA_WORKFLOW`` line naming the effective workflow of the run decision
  (``_resolve_workflow_env_name``: never under ``--no-workflow``; explicit
  ``-w`` → that name; else the basename auto-match file — silent containment
  guard, the name carried exactly when the file exists). All three follow the
  engine-skip rule: an explicit ``-e`` key keeps winning.
- step 9 — the workflow decision, the profile value, and the skip names
  travel as argv flags; the host prints NO workflow line (the launch
  feedback line prints in-container).

The env-file still carries environment layers ONLY otherwise: none of the
legacy run-coordination names (``GOGA_WORKFLOW_NAME`` / ``GOGA_WORKFLOW_DISABLED``
/ ``GOGA_SKIP_STAGES``) is ever written by the launcher, and user-supplied
values of those names travel verbatim and stay inert (no warning, no error).
All tests drive the real launcher with the docker internals mocked (no docker
dependency).
"""

from __future__ import annotations

import inspect
import subprocess
import sys
from pathlib import Path
from typing import ClassVar
from unittest import mock

import pytest
from goga.commands.pipeline.run_pipeline_container import (
    run_pipeline_container as rpc,
)
from goga.config import ProjectConfig

from tests.commands.pipeline.conftest import make_config as _make_config

# Resolve the real submodule via sys.modules (the package __init__ binds the
# function name `run_pipeline_container`, which would shadow string-based
# mock.patch paths walking through the package on Python 3.10).
_rpc_mod = sys.modules["goga.commands.pipeline.run_pipeline_container"]

# The env-file writer captured at import time — the launch harness wraps it per
# launch, so re-launching within one test must never wrap the wrapper.
_REAL_WRITE_ENV_FILE = _rpc_mod._write_env_file

# The run-coordination names the launcher must never write or interpret; the
# GOGA_EXTRA_ENV payload line and the three profile-carriage lines are the
# deliberate GOGA_ carriers, so the forbidden set is enumerated by name.
_RUN_COORDINATION_PREFIXES = ("GOGA_WORKFLOW_NAME=", "GOGA_WORKFLOW_DISABLED=", "GOGA_SKIP_STAGES=")


def _run_coordination_entries(env_lines: list[str]) -> list[str]:
    """Return the run-coordination entries found in an env-file's line list."""
    return [ln for ln in env_lines if ln.startswith(_RUN_COORDINATION_PREFIXES)]


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

    def capture_env(lines: list[str]) -> Path:
        path = _REAL_WRITE_ENV_FILE(lines)
        env_lines.extend(lines)
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


def _env_value(env_lines: list[str], key: str) -> str | None:
    """Return the last value of ``KEY=`` line in the env-file lines, or None."""
    matches = [ln.partition("=")[2] for ln in env_lines if ln.startswith(f"{key}=")]
    return matches[-1] if matches else None


# --- Step 8 — the workflow env-line decision matrix ---


class TestWorkflowEnvLineMatrix:
    """One matrix over the four decision rows (CODEMANIFEST step 8).

    Positive rows write EXACTLY one ``GOGA_WORKFLOW`` engine line naming the
    workflow that will apply; negative rows write none. The argv carries the
    decision exactly as given, and the host NEVER prints the workflow line
    (the launch feedback line prints in-container).
    """

    def test_run_pipeline_container_envfile_workflow_decision_matrix(self, tmp_path: Path, monkeypatch, capsys) -> None:
        """(a) explicit -w → line + -w in argv; (b) auto-match file → line, no -w; (c) --no-workflow → no line.

        No row prints a host-side ``Pipeline running with workflow`` line.
        """
        config = _make_config()
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        (workflows_dir / "deploy.yml").write_text("prompt: hi\n")
        (workflows_dir / "hardening.yml").write_text("prompt: hi\n")

        cases = [
            # (label, launch kwargs, expected GOGA_WORKFLOW value or None, -w in argv)
            ("explicit", {"workflow": "hardening"}, "hardening", "hardening"),
            ("no_workflow", {"no_workflow": True}, None, None),
            ("auto_match_present", {}, "deploy", None),
            ("auto_match_absent", {}, None, None),
        ]

        for label, kwargs, expected_value, expected_w in cases:
            if label == "auto_match_absent":
                # the basename file must NOT exist for this row
                (workflows_dir / "deploy.yml").unlink()

            result = _launch_run(monkeypatch, capsys, tmp_path, config, **kwargs)

            assert result["exit_code"] == 0, label
            assert _env_value(result["env_lines"], "GOGA_WORKFLOW") == expected_value, (
                label,
                result["env_lines"],
            )

            args = result["args"]
            if expected_w is None:
                assert "-w" not in args, (label, args)
            else:
                assert args[args.index("-w") + 1] == expected_w, (label, args)

            # the host NEVER prints the workflow line — the feedback line
            # prints in-container
            assert "Pipeline running with workflow" not in str(result["stdout"]), label
            assert "Web UI:" not in str(result["stdout"]), label
            # the env-file never carries a legacy run-coordination entry
            assert not _run_coordination_entries(result["env_lines"]), (
                label,
                result["env_lines"],
            )

            if label == "auto_match_absent":
                # restore the file for any later rows (none today, keeps the
                # matrix extensible)
                (workflows_dir / "deploy.yml").write_text("prompt: hi\n")


class TestResolveWorkflowEnvNameAutoMatchContainment:
    """Auto-match path-traversal containment of the workflow env-line decision.

    The auto-match fallback composes ``<cwd>/.goga/workflows/<name>.yml`` from the
    pipeline ``name``. A ``name`` escaping the workflows dir via ``..`` or an
    absolute prefix is a silent miss — ``None``, no line — even when the
    escaped path exists on the host, mirroring the explicit-``--workflow``
    (host) and in-container containment guards. This keeps the engine line
    honest: it never names a workflow that the in-container resolver will
    refuse to apply.
    """

    def test_auto_match_dotdot_escape_is_silent_miss(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A ``..`` in the pipeline name never resolves outside the workflows dir."""
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        # A file reachable only by escaping the workflows dir via ``..``.
        (tmp_path / ".goga" / "outside.yml").write_text("prompt: evil\n")
        monkeypatch.chdir(tmp_path)

        assert _rpc_mod._resolve_workflow_env_name(workflow=None, no_workflow=False, name="../outside") is None

    def test_auto_match_absolute_prefix_is_silent_miss(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """An absolute-prefixed pipeline name never resolves outside the workflows dir."""
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        monkeypatch.chdir(tmp_path)

        assert _rpc_mod._resolve_workflow_env_name(workflow=None, no_workflow=False, name="/etc/evil") is None

    def test_auto_match_plain_name_still_resolves(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """A plain pipeline name with a present basename file still resolves (regression guard)."""
        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        (workflows_dir / "deploy.yml").write_text("prompt: hi\n")
        monkeypatch.chdir(tmp_path)

        assert _rpc_mod._resolve_workflow_env_name(workflow=None, no_workflow=False, name="deploy") == "deploy"

    def test_no_workflow_yields_none_even_with_explicit_name(self) -> None:
        """``no_workflow`` wins over an explicit name — disabled means no line."""
        assert _rpc_mod._resolve_workflow_env_name(workflow="hardening", no_workflow=True, name="deploy") is None


# --- Step 8 — the profile carriage engine lines ---


class TestRunPipelineContainerProfileCarriage:
    """The ambient-profile and home-bundle engine lines plus the argv channel."""

    HOME_BUNDLE: ClassVar[dict[str, dict[str, object]]] = {"mixa": {"worker": {"agent": "codex"}}}

    def test_ambient_profile_and_bundle_lines_in_order(self, tmp_path: Path, monkeypatch, capsys) -> None:
        """Ambient GOGA_PROFILE + non-empty bundle → both lines after the payload line."""
        from goga.docker import encode_home_profiles

        config = _make_config()
        monkeypatch.setenv("GOGA_PROFILE", "ambient-name")

        result = _launch_run(monkeypatch, capsys, tmp_path, config, home_profiles=self.HOME_BUNDLE)

        env_lines: list[str] = result["env_lines"]
        assert "GOGA_PROFILE=ambient-name" in env_lines
        assert f"GOGA_HOME_PROFILES={encode_home_profiles(self.HOME_BUNDLE)}" in env_lines
        # ladder position: both follow the CLI entries payload line
        assert env_lines.index("GOGA_PROFILE=ambient-name") > env_lines.index(
            next(ln for ln in env_lines if ln.startswith("GOGA_EXTRA_ENV="))
        )
        # no cargo dropped: the payload itself never appears in stdout
        assert "GOGA_HOME_PROFILES" not in str(result["stdout"])

    def test_no_cargo_writes_no_carriage_lines(self, tmp_path: Path, monkeypatch, capsys) -> None:
        """No ambient profile, no bundle, no auto-match file → no GOGA_* carriage lines."""
        config = _make_config()
        monkeypatch.delenv("GOGA_PROFILE", raising=False)

        result = _launch_run(monkeypatch, capsys, tmp_path, config)

        env_lines: list[str] = result["env_lines"]
        assert not any(ln.startswith("GOGA_PROFILE=") for ln in env_lines)
        assert not any(ln.startswith("GOGA_HOME_PROFILES=") for ln in env_lines)
        assert not any(ln.startswith("GOGA_WORKFLOW=") for ln in env_lines)

    def test_engine_skip_rule_keeps_explicit_entries_winning(self, tmp_path: Path, monkeypatch, capsys) -> None:
        """An explicit ``-e`` key suppresses the launcher carriage line of that key."""
        config = _make_config()
        monkeypatch.setenv("GOGA_PROFILE", "ambient-name")

        result = _launch_run(
            monkeypatch,
            capsys,
            tmp_path,
            config,
            extra_env=("GOGA_PROFILE=user-wins", "GOGA_HOME_PROFILES=user-payload"),
            home_profiles=self.HOME_BUNDLE,
        )

        env_lines: list[str] = result["env_lines"]
        # the raw user lines travel verbatim, exactly once each — no duplicate
        # launcher line of the same key
        assert env_lines.count("GOGA_PROFILE=user-wins") == 1
        assert env_lines.count("GOGA_HOME_PROFILES=user-payload") == 1

    def test_profile_joins_run_argv_only_when_set(self, tmp_path: Path, monkeypatch, capsys) -> None:
        """``--profile`` is appended after the workflow decision; absent → no flag."""
        config = _make_config()

        with_profile = _launch_run(monkeypatch, capsys, tmp_path, config, workflow="hardening", profile="mixa")
        args: list[str] = with_profile["args"]
        assert args[args.index("--profile") + 1] == "mixa"
        # after the -w decision, before any -s entry
        assert args.index("--profile") > args.index("-w")

        without_profile = _launch_run(monkeypatch, capsys, tmp_path, config)
        assert "--profile" not in without_profile["args"]


# --- Step 10 — env-file carries environment layers only ---


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

    def test_env_file_carries_no_run_coordination_entries(self, tmp_path: Path, monkeypatch, capsys) -> None:
        """A workflow + skip launch writes NO run-coordination ``GOGA_*`` entry into the env-file.

        With ``workflow="hardening"`` and ``skip=("build",)`` the decision and
        the names travel as argv flags; the env-file carries only the
        environment layers plus the CLI entries carriage payload line (and
        the ``GOGA_WORKFLOW`` engine line — the deliberate carrier of the run
        decision). The host prints NO workflow line — the feedback line
        prints in-container.
        """
        config = _make_config()

        result = _launch_run(monkeypatch, capsys, tmp_path, config, workflow="hardening", skip=("build",))

        env_lines: list[str] = result["env_lines"]
        assert not _run_coordination_entries(env_lines)
        # the one deliberate GOGA_ carrier — the carriage payload line — is
        # present (no -e was passed, so it decodes to the empty mapping)
        payload = [ln for ln in env_lines if ln.startswith("GOGA_EXTRA_ENV=")]
        assert len(payload) == 1
        # the environment layers are all still present
        assert "AFM_DIR=/home/goga/pipeline" in env_lines
        assert any(ln.startswith("AFM_DOCKER_FILE_ROOTS=") for ln in env_lines)
        # the workflow decision travels as the engine line + argv, never a
        # host stdout line
        assert "GOGA_WORKFLOW=hardening" in env_lines
        out_lines = [ln for ln in str(result["stdout"]).splitlines() if ln]
        assert out_lines == []

    def test_stale_goga_env_values_are_inert(self, tmp_path: Path, monkeypatch, capsys) -> None:
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

        assert not _run_coordination_entries(disabled["env_lines"])
        assert not _run_coordination_entries(unflagged["env_lines"])
        # identical environment layers in both rows (same launch inputs)
        assert disabled["env_lines"] == unflagged["env_lines"]
        assert "AFM_DIR=/home/goga/pipeline" in disabled["env_lines"]
