from __future__ import annotations

import inspect
import os
import sys
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

import pytest
from goga.afm import run_flow

# goga.afm.run_flow is shadowed in the package __init__ by the run_flow
# function, so `import goga.afm.run_flow as ...` returns the function, not the
# module. Resolve the real module via sys.modules — mock.patch paths that walk
# through the shadowed name fail on Python 3.10 (its _dot_lookup __import__s
# the full dotted path first, which can't cross a non-package module boundary).
# Per [[feedback_mock_patch_module_shadowing]].
_run_flow_module = sys.modules["goga.afm.run_flow"]


class TestRunFlowContract:
    def test_run_flow_importable_from_facade(self) -> None:
        """run_flow is importable from the goga.afm facade."""
        assert run_flow is not None

    def test_run_flow_signature_matches_contract(self) -> None:
        """run_flow exposes the (flow_path, port, max_parallel, exit_on_fail, env) signature."""
        signature = inspect.signature(run_flow)
        parameters = list(signature.parameters)

        assert parameters == ["flow_path", "port", "max_parallel", "exit_on_fail", "env"]

        env_annotation = signature.parameters["env"].annotation
        assert env_annotation == "dict[str, str] | None" or env_annotation == dict[str, str] | None
        assert signature.parameters["env"].default is None
        assert signature.parameters["max_parallel"].default is None
        assert signature.parameters["exit_on_fail"].default is False
        assert signature.parameters["exit_on_fail"].annotation is bool or (
            signature.parameters["exit_on_fail"].annotation == "bool"
        )

    def test_run_flow_exit_on_fail_positioned_between_max_parallel_and_env(self) -> None:
        """exit_on_fail sits after max_parallel and before env in the signature."""
        signature = inspect.signature(run_flow)
        parameters = list(signature.parameters)

        assert parameters.index("exit_on_fail") == parameters.index("max_parallel") + 1
        assert parameters.index("exit_on_fail") == parameters.index("env") - 1

    def test_run_flow_max_parallel_inserted_after_port_before_path(self, tmp_path: Path) -> None:
        """max_parallel materializes as `--max-parallel <N>` after --port, before the path."""
        flow_path = tmp_path / "deploy.yml"
        flow_path.write_text("flow")

        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            return_value=MagicMock(returncode=0),
        ) as mock_subprocess:
            run_flow(flow_path, 50321, max_parallel=4)

        called_args = mock_subprocess.call_args.args[0]
        # --max-parallel sits immediately after --port <port>, before the positional path.
        port_index = called_args.index("--port")
        assert called_args[port_index + 2] == "--max-parallel"
        assert called_args[port_index + 3] == "4"
        assert called_args[-1] == str(flow_path)

    def test_run_flow_returns_int(self, tmp_path: Path) -> None:
        """run_flow returns 0 on a successful (exit 0) afm invocation."""
        flow_path = tmp_path / "deploy.yml"
        flow_path.write_text("flow")

        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            return_value=MagicMock(returncode=0),
        ):
            exit_code = run_flow(flow_path, 50321)

        assert exit_code == 0


class TestRunFlowLogic:
    def test_run_flow_invokes_afm_run_with_port_and_path(self, tmp_path: Path) -> None:
        """afm is invoked via PATH as `afm run --port <port> <flow_path>`."""
        flow_path = tmp_path / "deploy.yml"
        flow_path.write_text("flow")

        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            return_value=MagicMock(returncode=0),
        ) as mock_subprocess:
            exit_code = run_flow(flow_path, 50321)

        assert exit_code == 0
        mock_subprocess.assert_called_once()
        called_args = mock_subprocess.call_args.args[0]
        assert called_args == ["afm", "run", "--port", "50321", str(flow_path)]

    def test_run_flow_passes_max_parallel_flag_when_set(self, tmp_path: Path) -> None:
        """max_parallel=4 materializes as `--max-parallel 4` between --port and the path."""
        flow_path = tmp_path / "deploy.yml"
        flow_path.write_text("flow")

        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            return_value=MagicMock(returncode=0),
        ) as mock_subprocess:
            exit_code = run_flow(flow_path, 50321, max_parallel=4)

        assert exit_code == 0
        mock_subprocess.assert_called_once()
        called_args = mock_subprocess.call_args.args[0]
        assert called_args == [
            "afm",
            "run",
            "--port",
            "50321",
            "--max-parallel",
            "4",
            str(flow_path),
        ]

    def test_run_flow_omits_max_parallel_flag_when_none(self, tmp_path: Path) -> None:
        """default max_parallel=None omits --max-parallel entirely (backward compat)."""
        flow_path = tmp_path / "deploy.yml"
        flow_path.write_text("flow")

        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            return_value=MagicMock(returncode=0),
        ) as mock_subprocess:
            exit_code = run_flow(flow_path, 50321)

        assert exit_code == 0
        called_args = mock_subprocess.call_args.args[0]
        assert "--max-parallel" not in called_args
        assert called_args == ["afm", "run", "--port", "50321", str(flow_path)]

    def test_run_flow_appends_exit_on_fail_flag(self, tmp_path: Path) -> None:
        """exit_on_fail=True appends --exit-on-fail after --max-parallel, before the path."""
        flow_path = tmp_path / "deploy.yml"
        flow_path.write_text("flow")

        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            return_value=MagicMock(returncode=0),
        ) as mock_subprocess:
            exit_code = run_flow(flow_path, 5000, max_parallel=2, exit_on_fail=True)

        assert exit_code == 0
        called_args = mock_subprocess.call_args.args[0]
        assert called_args == [
            "afm",
            "run",
            "--port",
            "5000",
            "--max-parallel",
            "2",
            "--exit-on-fail",
            str(flow_path),
        ]

    def test_run_flow_omits_exit_on_fail_by_default(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Default exit_on_fail=False omits the flag and never touches AFM_EXIT_ON_FAIL."""
        flow_path = tmp_path / "deploy.yml"
        flow_path.write_text("flow")
        monkeypatch.delenv("AFM_EXIT_ON_FAIL", raising=False)

        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            return_value=MagicMock(returncode=0),
        ) as mock_subprocess:
            exit_code = run_flow(flow_path, 5000)

        assert exit_code == 0
        called_args = mock_subprocess.call_args.args[0]
        assert called_args == ["afm", "run", "--port", "5000", str(flow_path)]
        assert "--exit-on-fail" not in called_args
        # The argv flag is the single channel — the environment variable is
        # neither read (no env kwarg composed from it) nor set.
        assert "env" not in mock_subprocess.call_args.kwargs
        assert "AFM_EXIT_ON_FAIL" not in os.environ

    def test_run_flow_exit_on_fail_without_max_parallel(self, tmp_path: Path) -> None:
        """exit_on_fail=True with max_parallel=None places the flag right after --port."""
        flow_path = tmp_path / "deploy.yml"
        flow_path.write_text("flow")

        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            return_value=MagicMock(returncode=0),
        ) as mock_subprocess:
            run_flow(flow_path, 5000, exit_on_fail=True)

        called_args = mock_subprocess.call_args.args[0]
        assert called_args == [
            "afm",
            "run",
            "--port",
            "5000",
            "--exit-on-fail",
            str(flow_path),
        ]

    def test_run_flow_explicit_false_exit_on_fail_omits_flag(self, tmp_path: Path) -> None:
        """An explicit exit_on_fail=False omits the flag exactly like the default."""
        flow_path = tmp_path / "deploy.yml"
        flow_path.write_text("flow")

        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            return_value=MagicMock(returncode=0),
        ) as mock_subprocess:
            run_flow(flow_path, 5000, max_parallel=2, exit_on_fail=False)

        called_args = mock_subprocess.call_args.args[0]
        assert called_args == [
            "afm",
            "run",
            "--port",
            "5000",
            "--max-parallel",
            "2",
            str(flow_path),
        ]
        assert "--exit-on-fail" not in called_args

    def test_run_flow_exit_on_fail_propagates_engine_exit_code(self, tmp_path: Path) -> None:
        """With the flag set, a failed stage surfaces as the engine's exit 1 verbatim."""
        flow_path = tmp_path / "deploy.yml"
        flow_path.write_text("flow")

        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            return_value=MagicMock(returncode=1),
        ):
            exit_code = run_flow(flow_path, 5000, exit_on_fail=True)

        assert exit_code == 1

    def test_run_flow_returns_127_when_afm_missing(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """A missing afm binary (FileNotFoundError) yields exit code 127 and a clear message."""
        flow_path = tmp_path / "deploy.yml"
        flow_path.write_text("flow")

        with mock.patch.object(_run_flow_module.subprocess, "run", side_effect=FileNotFoundError):
            exit_code = run_flow(flow_path, 50321)

        assert exit_code == 127
        captured = capsys.readouterr()
        assert "afm" in captured.err

    def test_run_flow_returns_126_on_oserror(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Any other OSError (here PermissionError) maps to exit code 126.

        Using a PermissionError subclass also guards handler ordering: the
        FileNotFoundError branch must be matched before the generic OSError
        branch, otherwise this would return 127.
        """
        flow_path = tmp_path / "deploy.yml"
        flow_path.write_text("flow")

        with mock.patch.object(_run_flow_module.subprocess, "run", side_effect=PermissionError("not executable")):
            exit_code = run_flow(flow_path, 50321)

        assert exit_code == 126

    def test_run_flow_file_not_found_caught_before_oserror(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """FileNotFoundError is caught by the dedicated branch, not the OSError branch."""
        flow_path = tmp_path / "deploy.yml"
        flow_path.write_text("flow")

        with mock.patch.object(_run_flow_module.subprocess, "run", side_effect=FileNotFoundError):
            exit_code = run_flow(flow_path, 50321)

        assert exit_code == 127

    def test_run_flow_propagates_nonzero_afm_exit_code(self, tmp_path: Path) -> None:
        """A non-zero afm exit code is propagated unchanged (not collapsed to 1)."""
        flow_path = tmp_path / "deploy.yml"
        flow_path.write_text("flow")

        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            return_value=MagicMock(returncode=7),
        ):
            exit_code = run_flow(flow_path, 50321)

        assert exit_code == 7

    def test_run_flow_does_not_resolve_names(self) -> None:
        """run_flow forwards its arguments verbatim — no .resolve() or name lookup inside.

        A relative path is forwarded unchanged: if run_flow called ``.resolve()``
        or did any filesystem lookup, afm would receive an absolute
        (canonicalized) path instead of the relative string passed in.
        """
        relative_path = Path("deploy.yml")

        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            return_value=MagicMock(returncode=0),
        ) as mock_subprocess:
            exit_code = run_flow(relative_path, 50321)

        assert exit_code == 0
        called_args = mock_subprocess.call_args.args[0]
        # The relative path reaches afm as-is — no canonicalization inside run_flow.
        assert called_args == ["afm", "run", "--port", "50321", "deploy.yml"]

    def test_run_flow_does_not_hardcode_srv_afm(self, tmp_path: Path) -> None:
        """afm is resolved through PATH — never a /srv/afm hard-code."""
        flow_path = tmp_path / "deploy.yml"
        flow_path.write_text("flow")

        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            return_value=MagicMock(returncode=0),
        ) as mock_subprocess:
            run_flow(flow_path, 50321)

        called_args = mock_subprocess.call_args.args[0]
        assert called_args[0] == "afm"
        assert "/srv/afm" not in " ".join(called_args)

    def test_run_flow_env_layer_applied_to_subprocess_only(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The env layer rides on top of the inherited environment, subprocess-only.

        The sentinel proves inheritance; the layer key overrides it in the
        composed mapping only — the caller's own ``os.environ`` never gains
        the key.
        """
        monkeypatch.setenv("SENTINEL", "inherited")

        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            return_value=MagicMock(returncode=0),
        ) as mock_subprocess:
            exit_code = run_flow(Path("/f.yml"), 8080, env={"KEY": "V"})

        assert exit_code == 0
        passed_env = mock_subprocess.call_args.kwargs["env"]
        assert passed_env["KEY"] == "V"
        assert passed_env["SENTINEL"] == "inherited"
        assert "KEY" not in os.environ
        assert mock_subprocess.call_args.args[0] == ["afm", "run", "--port", "8080", "/f.yml"]

    def test_run_flow_none_and_empty_env_are_pure_inheritance(self) -> None:
        """None and {} both launch with NO env kwarg — pure inheritance."""
        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            return_value=MagicMock(returncode=0),
        ) as mock_subprocess:
            run_flow(Path("/f.yml"), 8080)
            run_flow(Path("/f.yml"), 8080, env={})

        assert mock_subprocess.call_count == 2
        for call in mock_subprocess.call_args_list:
            assert "env" not in call.kwargs

    def test_run_flow_illegal_env_key_returns_126(self, capsys: pytest.CaptureFixture[str]) -> None:
        """An env layer rejected by the exec yields 126 and a clean, content-free error.

        The mocked ValueError text is CPython's verbatim message for an env
        key containing ``=`` (the shape a config-authored ``pipeline.env`` key
        could produce). The error line leaks neither the key nor the value.
        """
        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            side_effect=ValueError("illegal environment variable name"),
        ):
            exit_code = run_flow(Path("/f.yml"), 8080, env={"A=B": "v"})

        assert exit_code == 126
        captured = capsys.readouterr()
        err_lines = [line for line in captured.err.splitlines() if line]
        assert len(err_lines) == 1
        assert err_lines[0].startswith("Error:")
        assert "Traceback" not in captured.err
        assert "A=B" not in captured.err
        assert "v" not in captured.err
