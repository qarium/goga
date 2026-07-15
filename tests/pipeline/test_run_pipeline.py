from __future__ import annotations

import inspect
import sys
from pathlib import Path
from unittest import mock
from unittest.mock import call

import pytest
from goga.pipeline import run_pipeline
from goga.pipeline.compiler import StructuralError

# goga.pipeline.run_pipeline is shadowed in the package __init__ by the
# run_pipeline function, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules and patch its
# run_flow / compile_flow attributes directly. Per [[feedback_mock_patch_module_shadowing]].
_run_pipeline_module = sys.modules["goga.pipeline.run_pipeline"]


@pytest.fixture
def afm_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point AFM_DIR at a tmp dir and return the resolved path.

    flow_path inside run_pipeline is ``afm_dir / "flow.yml"``. Returning the
    resolved value lets assertions compare against exactly what run_pipeline
    builds (it resolves AFM_DIR internally). The directory itself is not
    created here — compile_flow is mocked in every test, so its
    parent-must-exist precondition never fires.
    """
    directory = (tmp_path / ".afm").resolve()
    monkeypatch.setenv("AFM_DIR", str(directory))
    return directory


def _write_pipeline(directory: Path, name: str = "deploy") -> None:
    """Create an empty pipeline file so name resolution matches it."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.yml").write_text("pipeline")


class TestRunPipelineContract:
    def test_run_pipeline_importable_from_facade(self) -> None:
        """run_pipeline is importable from the goga.pipeline facade."""
        assert run_pipeline is not None

    def test_run_pipeline_signature_matches_contract(self) -> None:
        """run_pipeline exposes the (name, project_dir, user_dir, port) signature."""
        signature = inspect.signature(run_pipeline)
        parameters = list(signature.parameters)

        assert parameters == ["name", "project_dir", "user_dir", "port"]

    def test_run_pipeline_returns_zero_on_success(self, tmp_path: Path, afm_dir: Path) -> None:
        """run_pipeline returns 0 on a successful compile + afm invocation."""
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=None),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        assert exit_code == 0


class TestRunPipelineLogic:
    def test_run_pipeline_passes_compiled_flow_path_and_port_to_run_flow(
        self, tmp_path: Path, afm_dir: Path
    ) -> None:
        """run_flow receives the compiled flow.yml path (not the DSL path) and the port."""
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=None),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0) as mock_run_flow,
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        mock_run_flow.assert_called_once_with(afm_dir / "flow.yml", 50321)

    def test_run_pipeline_resolves_user_source_when_only_in_user_dir(
        self, tmp_path: Path, afm_dir: Path
    ) -> None:
        """A pipeline only in user_dir still compiles + runs against its source path."""
        project_dir = tmp_path / "pipelines"
        project_dir.mkdir()
        user_dir = tmp_path / "user_pipelines"
        _write_pipeline(user_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=None) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0) as mock_run_flow,
        ):
            exit_code = run_pipeline("deploy", project_dir, user_dir, 50321)

        assert exit_code == 0
        # compile_flow receives the user-dir pipeline path (resolved) and the flow path.
        mock_compile.assert_called_once_with((user_dir / "deploy.yml").resolve(), afm_dir / "flow.yml")
        mock_run_flow.assert_called_once_with(afm_dir / "flow.yml", 50321)

    def test_run_pipeline_returns_nonzero_when_name_not_found(
        self, tmp_path: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A missing pipeline name returns nonzero without invoking compile_flow or run_flow."""
        project_dir = tmp_path / "pipelines"
        user_dir = tmp_path / "user_pipelines"

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow") as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow") as mock_run_flow,
        ):
            exit_code = run_pipeline("nonexistent", project_dir, user_dir, 50321)

        assert exit_code != 0
        mock_compile.assert_not_called()
        mock_run_flow.assert_not_called()
        captured = capsys.readouterr()
        assert "missing" in captured.err

    def test_run_pipeline_rejects_yml_suffixed_name(self, tmp_path: Path, afm_dir: Path) -> None:
        """A name carrying the '.yml' suffix never matches (entry names are extension-less)."""
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow") as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow") as mock_run_flow,
        ):
            exit_code = run_pipeline("deploy.yml", project_dir, tmp_path / "user_pipelines", 50321)

        assert exit_code != 0
        mock_compile.assert_not_called()
        mock_run_flow.assert_not_called()

    def test_run_pipeline_propagates_run_flow_exit_code(self, tmp_path: Path, afm_dir: Path) -> None:
        """run_pipeline propagates run_flow's exit code unchanged."""
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=None),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=7),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        assert exit_code == 7

    def test_run_pipeline_propagates_missing_binary_exit_code(
        self, tmp_path: Path, afm_dir: Path
    ) -> None:
        """run_pipeline propagates run_flow's 127 (missing afm binary) exit code."""
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=None),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=127),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        assert exit_code == 127

    def test_run_pipeline_forwards_distinct_port_values(self, tmp_path: Path, afm_dir: Path) -> None:
        """The port integer is forwarded verbatim to run_flow — single source of truth."""
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=None),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0) as mock_run_flow,
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 8080)

        assert mock_run_flow.call_args == call(afm_dir / "flow.yml", 8080)

    def test_run_pipeline_afm_dir_not_set_raises_runtime_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing AFM_DIR raises RuntimeError before compile_flow or run_flow run."""
        monkeypatch.delenv("AFM_DIR", raising=False)
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow") as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow") as mock_run_flow,
            pytest.raises(RuntimeError, match="AFM_DIR not set"),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        mock_compile.assert_not_called()
        mock_run_flow.assert_not_called()

    def test_run_pipeline_propagates_structural_error_from_compile_flow(
        self, tmp_path: Path, afm_dir: Path
    ) -> None:
        """A structural DSL error from compile_flow propagates unchanged; run_flow is not called."""
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(
                _run_pipeline_module,
                "compile_flow",
                side_effect=StructuralError("unsupported body format"),
            ),
            mock.patch.object(_run_pipeline_module, "run_flow") as mock_run_flow,
            pytest.raises(StructuralError, match="unsupported body format"),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        mock_run_flow.assert_not_called()

    def test_run_pipeline_calls_compile_then_run_flow_in_order(
        self, tmp_path: Path, afm_dir: Path
    ) -> None:
        """compile_flow runs before run_flow."""
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)
        order: list[str] = []

        def _compile(*args: object, **kwargs: object) -> None:
            order.append("compile")

        def _run(*args: object, **kwargs: object) -> int:
            order.append("run")
            return 0

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", side_effect=_compile),
            mock.patch.object(_run_pipeline_module, "run_flow", side_effect=_run),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        assert exit_code == 0
        assert order == ["compile", "run"]

    def test_run_pipeline_resolves_relative_afm_dir_to_absolute(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A relative AFM_DIR is resolved to an absolute flow_path before reaching compile_flow."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("AFM_DIR", ".afm")
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)
        captured: dict[str, Path] = {}

        def _capture(pipeline_path: Path, flow_path: Path) -> None:
            captured["flow_path"] = flow_path

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", side_effect=_capture),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        assert captured["flow_path"].is_absolute()
        assert captured["flow_path"] == (tmp_path / ".afm").resolve() / "flow.yml"

    def test_run_pipeline_empty_afm_dir_raises_runtime_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An empty-string AFM_DIR is treated as unset and raises RuntimeError.

        A bare ``is None`` check would let ``""`` through, ``Path("").resolve()`` to
        the cwd, and silently write ``flow.yml`` there — this guards that misconfiguration.
        """
        monkeypatch.setenv("AFM_DIR", "")
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow") as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow") as mock_run_flow,
            pytest.raises(RuntimeError, match="AFM_DIR not set"),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        mock_compile.assert_not_called()
        mock_run_flow.assert_not_called()

    def test_run_pipeline_writes_compiled_flow_file_for_real_compile(
        self, tmp_path: Path, afm_dir: Path
    ) -> None:
        """A real (un-mocked) compile step writes a valid flow-file at AFM_DIR/flow.yml.

        Unlike the wiring tests, ``compile_flow`` is NOT mocked — this drives the real
        DSL → flow-file write through ``run_pipeline`` and confirms ``run_flow`` receives
        the compiled path. Locks in the end-to-end compile → run contract that the
        mocked tests cannot verify.
        """
        import yaml

        # compile_flow requires flow_path.parent to already exist.
        afm_dir.mkdir(parents=True)
        project_dir = tmp_path / "pipelines"
        project_dir.mkdir()
        (project_dir / "deploy.yml").write_text(
            "name: Deploy\n"
            "description: Deploy pipeline\n"
            "---\n"
            "\n"
            "- name: build\n"
            "  description: Build\n"
            "  prompt: Build it\n"
            "- name: ship\n"
            "  description: Ship\n"
            "  prompt: Ship it\n",
        )

        with mock.patch.object(_run_pipeline_module, "run_flow", return_value=0) as mock_run_flow:
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        assert exit_code == 0

        # The compiled flow-file exists at AFM_DIR/flow.yml and parses as valid YAML.
        flow_path = afm_dir / "flow.yml"
        assert flow_path.is_file()
        loaded = yaml.safe_load(flow_path.read_text())
        assert loaded["name"] == "Deploy"
        assert [stage["id"] for stage in loaded["stages"]] == ["build", "ship"]
        # Position-derived depends_on: first stage none, second depends on its predecessor.
        assert "depends_on" not in loaded["stages"][0]
        assert loaded["stages"][1]["depends_on"] == ["build"]

        # run_flow received the compiled flow path (not the DSL path) and the port.
        mock_run_flow.assert_called_once_with(flow_path, 50321)
