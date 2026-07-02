from __future__ import annotations

import inspect
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
_run_flow_module = sys.modules["goga.afm.run_flow"]


class TestRunFlowContract:
    def test_run_flow_importable_from_facade(self) -> None:
        """run_flow is importable from the goga.afm facade."""
        assert run_flow is not None

    def test_run_flow_signature_matches_contract(self) -> None:
        """run_flow exposes the (flow_path,) signature — abs-path wrapper only."""
        signature = inspect.signature(run_flow)
        parameters = list(signature.parameters)

        assert parameters == ["flow_path"]

    def test_run_flow_returns_int(self, tmp_path: Path) -> None:
        """run_flow returns 0 on a successful (exit 0) flowmanager invocation."""
        flow_path = tmp_path / "deploy.yml"
        flow_path.write_text("flow")

        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            return_value=MagicMock(returncode=0),
        ):
            exit_code = run_flow(flow_path)

        assert exit_code == 0


class TestRunFlowLogic:
    def test_run_flow_invokes_flowmanager_with_absolute_path(self, tmp_path: Path) -> None:
        """The flow file's absolute path (passed verbatim by the caller) reaches flowmanager."""
        flow_path = tmp_path / "deploy.yml"
        flow_path.write_text("flow")

        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            return_value=MagicMock(returncode=0),
        ) as mock_subprocess:
            exit_code = run_flow(flow_path)

        assert exit_code == 0
        mock_subprocess.assert_called_once()
        called_args = mock_subprocess.call_args.args[0]
        assert called_args == ["flowmanager", "run", str(flow_path)]

    def test_run_flow_handles_missing_flowmanager_binary(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A missing flowmanager binary yields a nonzero code and a clear message."""
        flow_path = tmp_path / "deploy.yml"
        flow_path.write_text("flow")

        with mock.patch.object(_run_flow_module.subprocess, "run", side_effect=FileNotFoundError):
            exit_code = run_flow(flow_path)

        assert exit_code != 0
        assert exit_code == 127
        captured = capsys.readouterr()
        assert "flowmanager" in captured.err
        assert "PATH" in captured.err

    def test_run_flow_handles_non_executable_flowmanager_binary(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A generic OSError (not just a FileNotFoundError) maps to 126.

        Using a plain ``OSError`` (not a ``PermissionError`` subclass) also guards
        the handler-ordering invariant: ``FileNotFoundError`` must be caught
        before the generic ``OSError`` branch, otherwise this would return 127.
        """
        flow_path = tmp_path / "deploy.yml"
        flow_path.write_text("flow")

        with mock.patch.object(_run_flow_module.subprocess, "run", side_effect=OSError("not executable")):
            exit_code = run_flow(flow_path)

        assert exit_code != 0
        assert exit_code == 126
        captured = capsys.readouterr()
        assert "flowmanager" in captured.err

    def test_run_flow_propagates_nonzero_flowmanager_exit_code(self, tmp_path: Path) -> None:
        """A non-zero flowmanager exit code is propagated unchanged (not collapsed to 1)."""
        flow_path = tmp_path / "deploy.yml"
        flow_path.write_text("flow")

        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            return_value=MagicMock(returncode=7),
        ):
            exit_code = run_flow(flow_path)

        assert exit_code == 7

    def test_run_flow_does_not_resolve_names(self) -> None:
        """run_flow forwards its argument verbatim — no .resolve() or name lookup inside.

        A relative path is forwarded unchanged: if run_flow called ``.resolve()``
        or did any filesystem lookup, flowmanager would receive an absolute
        (canonicalized) path instead of the relative string passed in.
        """
        relative_path = Path("deploy.yml")

        with mock.patch.object(
            _run_flow_module.subprocess,
            "run",
            return_value=MagicMock(returncode=0),
        ) as mock_subprocess:
            exit_code = run_flow(relative_path)

        assert exit_code == 0
        called_args = mock_subprocess.call_args.args[0]
        # The relative path reaches flowmanager as-is — no canonicalization inside run_flow.
        assert called_args == ["flowmanager", "run", "deploy.yml"]
