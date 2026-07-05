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
# Per [[feedback_mock_patch_module_shadowing]].
_run_flow_module = sys.modules["goga.afm.run_flow"]


class TestRunFlowContract:
    def test_run_flow_importable_from_facade(self) -> None:
        """run_flow is importable from the goga.afm facade."""
        assert run_flow is not None

    def test_run_flow_signature_matches_contract(self) -> None:
        """run_flow exposes the (flow_path, port) signature."""
        signature = inspect.signature(run_flow)
        parameters = list(signature.parameters)

        assert parameters == ["flow_path", "port"]

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
