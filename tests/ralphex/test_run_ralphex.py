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
        """run_ralphex exposes the (plan, options, dry_run, env) -> int signature."""
        signature = inspect.signature(run_ralphex)
        parameters = signature.parameters

        assert list(parameters) == ["plan", "options", "dry_run", "env"]
        assert parameters["env"].default is None
        assert signature.return_annotation in ("int", int)


class TestBuildCommand:
    def test_build_command_basic_has_plan_and_config_dir(self) -> None:
        """plan and --config-dir .ralphex/ are always present, even with no options."""
        assert _build_command("plan.md", {}) == ["ralphex", "plan.md", "--config-dir", ".ralphex/"]

    def test_bool_option_true_emits_bare_flag(self) -> None:
        """A True bool option emits the bare flag (no value)."""
        cmd = _build_command("plan.md", {"review": True, "external_only": True})

        assert "--review" in cmd
        assert "-e" in cmd

    def test_bool_option_false_or_absent_omits_flag(self) -> None:
        """False or absent bool options are omitted."""
        assert "-e" not in _build_command("plan.md", {"external_only": False})
        assert "-e" not in _build_command("plan.md", {})

    def test_scalar_option_emits_flag_with_value(self) -> None:
        """A scalar option emits --<flag> <value>."""
        cmd = _build_command("plan.md", {"session_timeout": "30m", "max_iterations": 10})

        assert "--session-timeout" in cmd
        assert "30m" in cmd
        assert "--max-iterations" in cmd
        assert "10" in cmd

    def test_scalar_option_zero_and_empty_omitted(self) -> None:
        """Historical scalar keys drop None/""/0 (guards against 0==False regression).

        The external flags are the documented exception to this rule and are
        covered by their own tests below."""
        assert _build_command("plan.md", {"max_iterations": 0, "session_timeout": ""}) == [
            "ralphex",
            "plan.md",
            "--config-dir",
            ".ralphex/",
        ]

    def test_external_scalar_zero_is_passed(self) -> None:
        """review_patience 0 (disabled) and max_external_iterations 0 (ralphex
        auto) are meaningful values and ARE emitted as 0."""
        cmd = _build_command("plan.md", {"review_patience": 0, "max_external_iterations": 0})

        assert cmd == [
            "ralphex",
            "plan.md",
            "--config-dir",
            ".ralphex/",
            "--review-patience",
            "0",
            "--max-external-iterations",
            "0",
        ]

    @pytest.mark.parametrize(
        "value",
        [None, ""],
        ids=["none", "empty_string"],
    )
    def test_external_scalar_unset_omits_flag(self, value: str | int | None) -> None:
        """Unset external scalars (None or empty string) add no token — only a
        meaningful 0 passes the wider external emission rule."""
        cmd = _build_command("plan.md", {"review_patience": value, "max_external_iterations": value})

        assert cmd == ["ralphex", "plan.md", "--config-dir", ".ralphex/"]

    # The option -> flag mapping is a fixed hand-maintained table (the
    # run_ralphex contract). These pin every literal so a typo in the table
    # (or a key/flag desync) cannot silently drop a user-supplied option.
    @pytest.mark.parametrize(
        ("key", "flag"),
        [
            ("review", "--review"),
            ("tasks_only", "--tasks-only"),
            ("external_only", "-e"),
        ],
    )
    def test_bool_flag_mapping_is_exact(self, key: str, flag: str) -> None:
        """Each bool option key maps to its exact ralphex flag literal."""
        cmd = _build_command("plan.md", {key: True})

        assert flag in cmd

    @pytest.mark.parametrize(
        ("key", "flag", "value"),
        [
            ("session_timeout", "--session-timeout", "30m"),
            ("idle_timeout", "--idle-timeout", "15m"),
            ("wait", "--wait", "60s"),
            ("max_iterations", "--max-iterations", 10),
            ("review_patience", "--review-patience", 3),
            ("max_external_iterations", "--max-external-iterations", 5),
            ("base_ref", "--base-ref", "origin/1.2.x"),
        ],
    )
    def test_scalar_flag_mapping_is_exact(self, key: str, flag: str, value: object) -> None:
        """Each scalar option key maps to its exact flag literal and value."""
        cmd = _build_command("plan.md", {key: value})

        assert flag in cmd
        assert str(value) in cmd

    @pytest.mark.parametrize(
        "value",
        [None, ""],
        ids=["none", "empty_string"],
    )
    def test_base_ref_unset_omits_flag(self, value: str | None) -> None:
        """An unset base_ref adds no token: neither --base-ref nor any value
        token reaches the argv (pins the scalar omit rule for the new key)."""
        cmd = _build_command("plan.md", {"base_ref": value})

        assert cmd == ["ralphex", "plan.md", "--config-dir", ".ralphex/"]
        assert "--base-ref" not in cmd

    @pytest.mark.parametrize(
        "options",
        [
            {"worktree": True, "skip_finalize": True},
            {"review": True, "worktree": True, "skip_finalize": True},
            {"tasks_only": True, "external_only": True, "worktree": False, "skip_finalize": False},
        ],
        ids=["retired_only", "mixed_with_live_keys", "retired_false"],
    )
    def test_retired_flags_absent_from_any_command(self, options: dict[str, str | int | bool]) -> None:
        """worktree/skip_finalize are retired table keys: no input produces
        --worktree or --skip-finalize (keys outside the table are ignored)."""
        cmd = _build_command("plan.md", options)

        assert "--worktree" not in cmd
        assert "--skip-finalize" not in cmd


class TestRunRalphexLogic:
    def test_run_ralphex_dry_run_prints_command_and_returns_0(self, capsys: pytest.CaptureFixture[str]) -> None:
        """dry_run prints the assembled command to stderr and returns 0 without launching."""
        result = run_ralphex("plan.md", {"review": True}, dry_run=True)

        assert result == 0
        captured = capsys.readouterr()
        # The full joined argv is printed (not a stub): plan, config-dir, and
        # the resolved flag all appear.
        assert "ralphex plan.md --config-dir .ralphex/ --review" in captured.err

    def test_run_ralphex_returns_0_on_success(self) -> None:
        """A successful (exit 0) ralphex invocation returns 0."""
        with (
            mock.patch.object(_run_ralphex_module.subprocess, "call", return_value=0),
            mock.patch.object(_run_ralphex_module.shutil, "which", return_value="/usr/local/bin/ralphex"),
        ):
            result = run_ralphex("plan.md", {}, False)

        assert result == 0

    def test_run_ralphex_propagates_nonzero_ralphex_exit(self) -> None:
        """A non-zero ralphex exit code is propagated unchanged (not collapsed to 1)."""
        with (
            mock.patch.object(_run_ralphex_module.subprocess, "call", return_value=42),
            mock.patch.object(_run_ralphex_module.shutil, "which", return_value="/usr/local/bin/ralphex"),
        ):
            result = run_ralphex("plan.md", {}, False)

        assert result == 42

    def test_run_ralphex_returns_1_when_binary_missing(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A missing ralphex binary (not on PATH) yields exit code 1 and a clear message."""
        with mock.patch.object(_run_ralphex_module.shutil, "which", return_value=None):
            result = run_ralphex("plan.md", {}, False)

        assert result == 1
        captured = capsys.readouterr()
        assert "ralphex" in captured.err

    def test_run_ralphex_inherits_env_no_env_kwarg(self) -> None:
        """run_ralphex invokes subprocess.call with the cmd only and never an env=
        kwarg — it inherits os.environ so the host launcher's env-file delivers
        the build env (replaces the deleted build-cell env-merge tests)."""
        with (
            mock.patch.object(_run_ralphex_module.subprocess, "call", return_value=0) as mock_call,
            mock.patch.object(_run_ralphex_module.shutil, "which", return_value="/usr/local/bin/ralphex"),
        ):
            run_ralphex("plan.md", {}, False)

        assert "env" not in mock_call.call_args.kwargs
        assert mock_call.call_args.args[0][0] == "ralphex"

    def test_run_ralphex_env_layer_overlays_inherited_environment(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A non-empty env layer overlays os.environ for the subprocess only:
        layer keys win, everything else is inherited, the parent is untouched."""
        monkeypatch.setenv("INHERITED_VAR", "base")
        monkeypatch.setenv("SHARED_VAR", "inherited")

        with (
            mock.patch.object(_run_ralphex_module.subprocess, "call", return_value=0) as mock_call,
            mock.patch.object(_run_ralphex_module.shutil, "which", return_value="/usr/bin/ralphex"),
        ):
            run_ralphex("plan.md", {}, False, env={"SHARED_VAR": "layer", "LAYER_ONLY": "x"})

        subprocess_env = mock_call.call_args.kwargs["env"]
        assert subprocess_env["SHARED_VAR"] == "layer"
        assert subprocess_env["LAYER_ONLY"] == "x"
        assert subprocess_env["INHERITED_VAR"] == "base"
        # The layer never mutates the parent environment.
        import os

        assert os.environ["SHARED_VAR"] == "inherited"

    def test_run_ralphex_dry_run_never_prints_env_values(self, capsys: pytest.CaptureFixture[str]) -> None:
        """dry_run prints the argv (built from options only) and never leaks
        env layer values; no subprocess machinery is touched."""
        with (
            mock.patch.object(_run_ralphex_module.subprocess, "call", return_value=0) as mock_call,
            mock.patch.object(_run_ralphex_module.shutil, "which", return_value="/usr/local/bin/ralphex") as mock_which,
        ):
            result = run_ralphex("plan.md", {"review": True}, True, env={"SECRET_TOKEN": "s3cr3t"})

        captured = capsys.readouterr()
        assert result == 0
        assert "s3cr3t" not in captured.err
        assert "ralphex plan.md" in captured.err
        mock_call.assert_not_called()
        mock_which.assert_not_called()

    @pytest.mark.parametrize("env", [None, {}], ids=["none", "empty"])
    def test_run_ralphex_env_none_and_empty_no_env_kwarg(self, env: dict[str, str] | None) -> None:
        """env=None and env={} both mean pure inheritance: subprocess.call is
        invoked without an env kwarg (invariant pinned alongside
        test_run_ralphex_inherits_env_no_env_kwarg)."""
        with (
            mock.patch.object(_run_ralphex_module.subprocess, "call", return_value=0) as mock_call,
            mock.patch.object(_run_ralphex_module.shutil, "which", return_value="/usr/local/bin/ralphex"),
        ):
            run_ralphex("p.md", {}, False, env=env)

        assert "env" not in mock_call.call_args.kwargs
        assert mock_call.call_args.args[0][0] == "ralphex"

    def test_run_ralphex_env_path_override_hiding_binary_returns_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        """An env layer whose PATH override hides the binary from the exec
        surfaces as the clean missing-binary message and exit 1 — not a
        FileNotFoundError traceback escaping to the caller."""
        with (
            mock.patch.object(
                _run_ralphex_module.subprocess,
                "call",
                side_effect=FileNotFoundError("[Errno 2] No such file or directory: 'ralphex'"),
            ),
            mock.patch.object(_run_ralphex_module.shutil, "which", return_value="/usr/bin/ralphex"),
        ):
            result = run_ralphex("plan.md", {}, False, env={"PATH": "/nonexistent-dir"})

        captured = capsys.readouterr()
        assert result == 1
        assert "ralphex binary not found in PATH" in captured.err

    def test_run_ralphex_env_path_override_non_executable_returns_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        """An env layer whose PATH override resolves a non-executable ralphex
        surfaces as the clean failed-invoke message and exit 1 — not a
        PermissionError traceback escaping to the caller."""
        with (
            mock.patch.object(
                _run_ralphex_module.subprocess,
                "call",
                side_effect=PermissionError("[Errno 13] Permission denied: 'ralphex'"),
            ),
            mock.patch.object(_run_ralphex_module.shutil, "which", return_value="/usr/bin/ralphex"),
        ):
            result = run_ralphex("plan.md", {}, False, env={"PATH": "/non-executable-dir"})

        captured = capsys.readouterr()
        assert result == 1
        assert "failed to invoke ralphex" in captured.err

    def test_run_ralphex_env_layer_illegal_variable_name_returns_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        """An env layer key that is not a legal environment variable name
        (contains "=") is rejected by exec before the launch — a clean message
        and exit 1, not a ValueError traceback escaping to the caller."""
        with (
            mock.patch.object(
                _run_ralphex_module.subprocess,
                "call",
                side_effect=ValueError("illegal environment variable name"),
            ),
            mock.patch.object(_run_ralphex_module.shutil, "which", return_value="/usr/local/bin/ralphex"),
        ):
            result = run_ralphex("plan.md", {}, False, env={"A=B": "x"})

        captured = capsys.readouterr()
        assert result == 1
        assert "failed to invoke ralphex" in captured.err

    def test_run_ralphex_env_path_override_not_a_directory_returns_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        """An env layer whose PATH override contains a file component resolves
        a ralphex path that is not a directory — the clean failed-invoke
        message and exit 1, not a NotADirectoryError traceback."""
        with (
            mock.patch.object(
                _run_ralphex_module.subprocess,
                "call",
                side_effect=NotADirectoryError("[Errno 20] Not a directory: 'ralphex'"),
            ),
            mock.patch.object(_run_ralphex_module.shutil, "which", return_value="/usr/bin/ralphex"),
        ):
            result = run_ralphex("plan.md", {}, False, env={"PATH": "/etc/hosts/bin"})

        captured = capsys.readouterr()
        assert result == 1
        assert "failed to invoke ralphex" in captured.err

    def test_run_ralphex_env_layer_oversized_value_returns_1(self, capsys: pytest.CaptureFixture[str]) -> None:
        """An env layer value too large to exec (e.g. a pasted secret) is
        rejected before the launch — the clean failed-invoke message and
        exit 1, not an OSError (E2BIG) traceback. The message carries argv
        only, never the layer value."""
        with (
            mock.patch.object(
                _run_ralphex_module.subprocess,
                "call",
                side_effect=OSError(7, "Argument list too long", "ralphex"),
            ),
            mock.patch.object(_run_ralphex_module.shutil, "which", return_value="/usr/local/bin/ralphex"),
        ):
            result = run_ralphex("plan.md", {}, False, env={"BIG": "x" * 300000})

        captured = capsys.readouterr()
        assert result == 1
        assert "failed to invoke ralphex" in captured.err

    def test_run_ralphex_maps_new_bool_flags(self) -> None:
        """The review/tasks_only mode flags map to their bare ralphex flags;
        False is equivalent to absent (bool-mapping rule regression guard)."""
        with (
            mock.patch.object(_run_ralphex_module.subprocess, "call", return_value=0) as mock_call,
            mock.patch.object(_run_ralphex_module.shutil, "which", return_value="/usr/bin/ralphex"),
        ):
            run_ralphex("p.md", {"review": True}, False)
            review_argv = list(mock_call.call_args.args[0])

            run_ralphex("p.md", {"tasks_only": True}, False)
            tasks_argv = list(mock_call.call_args.args[0])

            run_ralphex("p.md", {"review": False, "tasks_only": False}, False)
            neither_argv = list(mock_call.call_args.args[0])

        assert "--review" in review_argv
        assert "--tasks-only" not in review_argv

        assert "--tasks-only" in tasks_argv
        assert "--review" not in tasks_argv

        assert "--review" not in neither_argv
        assert "--tasks-only" not in neither_argv

    def test_run_ralphex_external_flags_and_zero_rule(self) -> None:
        """The external-review surface maps exactly: external_only emits -e,
        the two external scalars pass 0 verbatim, the historical
        max_iterations 0 is dropped, base_ref carries its value, and the
        retired flags never appear."""
        with (
            mock.patch.object(_run_ralphex_module.subprocess, "call", return_value=0) as mock_call,
            mock.patch.object(_run_ralphex_module.shutil, "which", return_value="/usr/bin/ralphex"),
        ):
            run_ralphex(
                "p.md",
                {
                    "external_only": True,
                    "review_patience": 0,
                    "max_external_iterations": 0,
                    "max_iterations": 0,
                    "base_ref": "main",
                },
                False,
            )

        argv = list(mock_call.call_args.args[0])
        assert argv == [
            "ralphex",
            "p.md",
            "--config-dir",
            ".ralphex/",
            "-e",
            "--review-patience",
            "0",
            "--max-external-iterations",
            "0",
            "--base-ref",
            "main",
        ]
        assert "--worktree" not in argv
        assert "--skip-finalize" not in argv

    def test_max_iterations_zero_dropped_by_launcher(self, capsys: pytest.CaptureFixture[str]) -> None:
        """dry-run print: a 0 max_iterations never reaches the printed command
        while a 0 review_patience does (the asymmetric zero rule, both arms)."""
        run_ralphex("p.md", {"tasks_only": True, "max_iterations": 0}, dry_run=True)

        dropped = capsys.readouterr()
        assert "--max-iterations" not in dropped.err
        assert "--tasks-only" in dropped.err

        run_ralphex("p.md", {"review_patience": 0}, dry_run=True)

        passed = capsys.readouterr()
        assert "--review-patience 0" in passed.err
