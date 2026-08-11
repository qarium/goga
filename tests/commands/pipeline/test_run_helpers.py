"""Contract and logic tests for the two runtime-dir facades declared in
``goga/commands/pipeline/CODEMANIFEST`` and colocated with
``run_pipeline_container`` in ``run_pipeline_container.py``:

- ``resolve_pipeline_runtime_dir(pipeline_name) -> Path``
- ``clean_pipeline_runtime_dir(pipeline_runtime_dir) -> None``

These are thin host-side facades over ``resolve_runtime_dir`` from
``goga.runtime``. The atomic helpers ``normalize_project_path`` and
``resolve_git_branch`` that used to live here were relocated to
``goga.runtime.paths`` (tested in ``tests/runtime/test_paths.py``) and are no
longer defined in this module. These tests verify the renamed facades delegate
correctly and clean idempotently; they have no docker dependency.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest
from goga.commands.pipeline.run_pipeline_container import (
    clean_pipeline_runtime_dir,
    resolve_pipeline_runtime_dir,
)

# Resolve the real submodule via sys.modules (the package __init__ binds the
# function name `run_pipeline_container`, which would shadow string-based
# mock.patch paths walking through the package on Python 3.10).
_rpc_mod = sys.modules["goga.commands.pipeline.run_pipeline_container"]


# --- Contract tests ---


class TestRunHelpersContract:
    def test_both_facades_importable_from_run_pipeline_container(self) -> None:
        """The two renamed facades are importable from the declared location."""
        from goga.commands.pipeline.run_pipeline_container import (
            clean_pipeline_runtime_dir,
            resolve_pipeline_runtime_dir,
        )

        assert callable(resolve_pipeline_runtime_dir)
        assert callable(clean_pipeline_runtime_dir)

    def test_old_names_not_defined_in_module(self) -> None:
        """The relocated helpers and old facade names are gone from the module."""
        assert not hasattr(_rpc_mod, "normalize_project_path")
        assert not hasattr(_rpc_mod, "resolve_git_branch")
        assert not hasattr(_rpc_mod, "resolve_afm_runtime_dir")
        assert not hasattr(_rpc_mod, "clean_afm_runtime_dir")

    def test_resolve_pipeline_runtime_dir_returns_absolute_path(self) -> None:
        """resolve_pipeline_runtime_dir returns an absolute Path."""
        result = resolve_pipeline_runtime_dir("deploy")
        assert isinstance(result, Path)
        assert result.is_absolute()

    def test_resolve_pipeline_runtime_dir_delegates_to_runtime_dir(self) -> None:
        """resolve_pipeline_runtime_dir delegates to resolve_runtime_dir("pipelines", name)."""
        with mock.patch.object(_rpc_mod, "resolve_runtime_dir") as mock_rrd:
            mock_rrd.return_value = Path("/fake/pipelines/path")
            result = resolve_pipeline_runtime_dir("deploy")
        assert result == Path("/fake/pipelines/path")
        assert mock_rrd.call_args == mock.call("pipelines", "deploy")

    def test_clean_pipeline_runtime_dir_returns_none(self, tmp_path: Path) -> None:
        """clean_pipeline_runtime_dir returns None (and creates the directory)."""
        assert clean_pipeline_runtime_dir(tmp_path / "rt") is None
        assert (tmp_path / "rt").exists()


# --- Logic tests (positive): resolve_pipeline_runtime_dir delegation ---


class TestResolvePipelineRuntimeDirLogic:
    def test_delegates_with_pipeline_name_suffix(self) -> None:
        """Delegation forwards the pipeline name as the sole suffix part."""
        for name in ("deploy", "canary", "my-pipe"):
            with mock.patch.object(_rpc_mod, "resolve_runtime_dir") as mock_rrd:
                mock_rrd.return_value = Path("/fake/path")
                resolve_pipeline_runtime_dir(name)
            assert mock_rrd.call_args == mock.call("pipelines", name)

    def test_does_not_create_the_directory(self, tmp_path: Path, monkeypatch) -> None:
        """The facade is pure — it does not mkdir the resolved directory."""
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path / "proj")
        monkeypatch.setattr("goga.runtime.paths.resolve_git_branch", lambda: "main")
        result = resolve_pipeline_runtime_dir("deploy")
        assert isinstance(result, Path)
        assert not result.exists()

    def test_sanitizes_colon_in_pipeline_name_segment(self, tmp_path: Path, monkeypatch) -> None:
        """A ':' in the pipeline name becomes '-' in the host path segment.

        Regression guard for the docker ``invalid mode`` defect: the host
        state-dir path is later used as a docker bind-mount source
        (``<runtime_dir>:/home/goga/pipeline``), so an unsanitized ':' would be
        parsed by docker as the ``source:target[:mode]`` separator. The facade
        must sanitize the path segment so the composed path is mount-safe.
        """
        monkeypatch.setattr(Path, "home", lambda: tmp_path / "home")
        monkeypatch.setattr(Path, "cwd", lambda: tmp_path / "proj")
        monkeypatch.setattr("goga.runtime.paths.resolve_git_branch", lambda: "main")
        result = resolve_pipeline_runtime_dir("pybuggy:api-feature")
        assert result.name == "pybuggy-api-feature"
        assert ":" not in str(result)

    def test_delegation_sanitizes_colon_before_resolving(self) -> None:
        """The ':' is sanitized BEFORE delegation: the suffix reaches
        ``resolve_runtime_dir`` already as 'pybuggy-api-feature'."""
        with mock.patch.object(_rpc_mod, "resolve_runtime_dir") as mock_rrd:
            mock_rrd.return_value = Path("/fake/path")
            resolve_pipeline_runtime_dir("pybuggy:api-feature")
        assert mock_rrd.call_args == mock.call("pipelines", "pybuggy-api-feature")


# --- Logic tests (positive): clean_pipeline_runtime_dir ---


class TestCleanPipelineRuntimeDirLogic:
    def test_wipes_and_recreates(self, tmp_path: Path) -> None:
        """A populated directory is emptied without raising."""
        runtime_dir = tmp_path / "rt"
        nested = runtime_dir / "deep" / "nested"
        nested.mkdir(parents=True)
        (nested / "state.txt").write_text("stale")

        clean_pipeline_runtime_dir(runtime_dir)

        assert runtime_dir.exists()
        assert not any(runtime_dir.iterdir())

    def test_clean_idempotent(self, tmp_path: Path) -> None:
        """Wiping a populated dir twice leaves it empty without raising."""
        runtime_dir = tmp_path / "rt"
        nested = runtime_dir / "deep" / "nested"
        nested.mkdir(parents=True)
        (nested / "state.txt").write_text("stale")

        clean_pipeline_runtime_dir(runtime_dir)
        clean_pipeline_runtime_dir(runtime_dir)  # second call must not raise

        assert runtime_dir.exists()
        assert not any(runtime_dir.iterdir())

    def test_creates_when_absent(self, tmp_path: Path) -> None:
        """A missing directory is created by the mkdir in the algorithm."""
        runtime_dir = tmp_path / "rt"
        assert not runtime_dir.exists()

        clean_pipeline_runtime_dir(runtime_dir)

        assert runtime_dir.exists()
        assert not any(runtime_dir.iterdir())

    def test_propagates_partial_removal_failure(self, tmp_path: Path) -> None:
        """The wipe is total: a partial-removal failure surfaces, not swallowed."""
        runtime_dir = tmp_path / "rt"
        runtime_dir.mkdir()
        (runtime_dir / "locked.json").write_text("stale")
        with (
            mock.patch.object(_rpc_mod.shutil, "rmtree", side_effect=PermissionError("denied")),
            pytest.raises(PermissionError),
        ):
            clean_pipeline_runtime_dir(runtime_dir)

    def test_tolerates_concurrent_removal(self, tmp_path: Path) -> None:
        """A vanished dir between check and rmtree (concurrent --clean) is tolerated."""
        runtime_dir = tmp_path / "rt"
        runtime_dir.mkdir()
        with mock.patch.object(_rpc_mod.shutil, "rmtree", side_effect=FileNotFoundError):
            clean_pipeline_runtime_dir(runtime_dir)  # does not raise
        assert runtime_dir.exists()
