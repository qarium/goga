from __future__ import annotations

import inspect
import sys
from unittest import mock

import pytest
from goga.ralphex import run_ralphex

# goga.ralphex.run_ralphex is shadowed in the package __init__ by the
# run_ralphex function, so `import goga.ralphex.run_ralphex as ...` returns the
# function, not the module. Resolve the real module via sys.modules — mock.patch
# paths that walk through the shadowed name fail on Python 3.10 (its
# _dot_lookup __import__s the full dotted path first, which can't cross a
# non-package module boundary). Mirror of tests/afm/test_run_flow.py.
_run_ralphex_module = sys.modules["goga.ralphex.run_ralphex"]
_build_command = _run_ralphex_module._build_command


class TestRunRalphexContract:
    def test_run_ralphex_importable_from_facade(self) -> None:
        """run_ralphex is importable from the goga.ralphex facade."""
        assert run_ralphex is not None

    def test_run_ralphex_signature_matches_contract(self) -> None:
        """run_ralphex exposes the (plan, options, dry_run) -> int signature."""
        signature = inspect.signature(run_ralphex)
        parameters = list(signature.parameters)

        assert parameters == ["plan", "options", "dry_run"]
        assert signature.return_annotation in ("int", int)


class TestBuildCommand:
    def test_build_command_basic_has_plan_and_config_dir(self) -> None:
        """plan and --config-dir .ralphex/ are always present, even with no options."""
        assert _build_command("plan.md", {}) == ["ralphex", "plan.md", "--config-dir", ".ralphex/"]

    def test_bool_option_true_emits_bare_flag(self) -> None:
        """A True bool option emits the bare flag (no value)."""
        cmd = _build_command("plan.md", {"worktree": True, "skip_finalize": True})

        assert "--worktree" in cmd
        assert "--skip-finalize" in cmd

    def test_bool_option_false_or_absent_omits_flag(self) -> None:
        """False or absent bool options are omitted."""
        assert "--worktree" not in _build_command("plan.md", {"worktree": False})
        assert "--worktree" not in _build_command("plan.md", {})

    def test_scalar_option_emits_flag_with_value(self) -> None:
        """A scalar option emits --<flag> <value>."""
        cmd = _build_command("plan.md", {"session_timeout": "30m", "max_iterations": 10})

        assert "--session-timeout" in cmd
        assert "30m" in cmd
        assert "--max-iterations" in cmd
        assert "10" in cmd

    def test_scalar_option_zero_and_empty_omitted(self) -> None:
        """Scalar values of None/""/0 are omitted (guards against 0==False regression)."""
        assert _build_command("plan.md", {"max_iterations": 0, "session_timeout": ""}) == [
            "ralphex",
            "plan.md",
            "--config-dir",
            ".ralphex/",
        ]


class TestRunRalphexLogic:
    def test_run_ralphex_dry_run_prints_command_and_returns_0(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """dry_run prints the assembled command to stderr and returns 0 without launching."""
        result = run_ralphex("plan.md", {"worktree": True}, dry_run=True)

        assert result == 0
        captured = capsys.readouterr()
        assert "ralphex" in captured.err
        assert "plan.md" in captured.err

    def test_run_ralphex_returns_0_on_success(self) -> None:
        """A successful (exit 0) ralphex invocation returns 0."""
        with mock.patch.object(_run_ralphex_module.subprocess, "call", return_value=0), \
             mock.patch.object(_run_ralphex_module.shutil, "which", return_value="/usr/local/bin/ralphex"):
            result = run_ralphex("plan.md", {}, False)

        assert result == 0

    def test_run_ralphex_propagates_nonzero_ralphex_exit(self) -> None:
        """A non-zero ralphex exit code is propagated unchanged (not collapsed to 1)."""
        with mock.patch.object(_run_ralphex_module.subprocess, "call", return_value=42), \
             mock.patch.object(_run_ralphex_module.shutil, "which", return_value="/usr/local/bin/ralphex"):
            result = run_ralphex("plan.md", {}, False)

        assert result == 42

    def test_run_ralphex_returns_1_when_binary_missing(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A missing ralphex binary (not on PATH) yields exit code 1 and a clear message."""
        with mock.patch.object(_run_ralphex_module.shutil, "which", return_value=None):
            result = run_ralphex("plan.md", {}, False)

        assert result == 1
        captured = capsys.readouterr()
        assert "ralphex" in captured.err
