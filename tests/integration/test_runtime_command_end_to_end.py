"""End-to-end integration tests for the registered ``goga runtime`` surface.

The stitched path under test: the root ``goga`` app (``goga/cli.py``)
dispatches ``runtime`` through the ``goga.commands`` facade re-export into
the runtime group (``goga/commands/runtime/runtime.py``), whose
subcommands resolve their targets via the cell's ``targets``/``archive``
routines — every path composed by the shared ``goga.runtime`` formula
(``resolve_runtime_dir``) — and refuse inside the goga image via the
``goga.docker`` marker (``is_in_docker``). The parity scenarios pin the
acceptance criteria no single-cell test can prove: the printed
directories are exactly what the real build run
(``resolve_build_runtime_dir``, ``build.py``) and the real pipeline run
(``resolve_pipeline_runtime_dir``, ``run_pipeline_container.py``) use —
one formula, no second path scheme. Boundary mocks only, per the
convention: git via the ``subprocess.run`` CompletedProcess pattern,
``Path.home`` via monkeypatch, real file I/O under ``tmp_path``;
``tests/conftest.py`` already scrubs ``GOGA_DOCKER`` between tests.
"""

from __future__ import annotations

import subprocess
import tarfile
from pathlib import Path
from unittest import mock

import pytest
from click.testing import CliRunner
from goga.cli import app
from goga.commands.build import resolve_build_runtime_dir
from goga.commands.pipeline.run_pipeline_container import resolve_pipeline_runtime_dir
from goga.runtime import normalize_project_path, resolve_runtime_dir


def _git_completed(stdout: str) -> subprocess.CompletedProcess:
    """Build the ``subprocess.run`` return the git boundary mock delivers."""
    return subprocess.CompletedProcess(
        ["git", "branch", "--show-current"],
        0,
        stdout=stdout,
        stderr="",
    )


def _isolate_work_home(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path]:
    """Patch cwd into ``tmp_path/work`` and ``Path.home`` into ``tmp_path/home``."""
    work = tmp_path / "work"
    work.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.chdir(work)
    monkeypatch.setattr(Path, "home", lambda: home)

    return work, home


def _seed_target(base: Path, *segments: str, files: dict[str, str] | None = None) -> Path:
    """Create a target directory tree under ``base`` and return its path."""
    target = base.joinpath(*segments)
    target.mkdir(parents=True)

    for rel, content in (files or {}).items():
        file = target / rel
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(content)

    return target


class TestRegisteredSurface:
    def test_root_app_runtime_build_prints_formula_dir(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Through the root app, build prints exactly the formula's directory — one line."""
        work, home = _isolate_work_home(monkeypatch, tmp_path)

        with mock.patch.object(subprocess, "run", return_value=_git_completed("feature/x\n")):
            result = CliRunner().invoke(app, ["runtime", "build"])
            formula_dir = resolve_runtime_dir("builds")

        assert result.exit_code == 0
        expected = home / ".goga" / "runtime" / "builds" / normalize_project_path(work) / "feature-x"

        assert result.output.strip() == str(formula_dir)
        assert result.output.strip() == str(expected)
        assert len(result.output.strip().splitlines()) == 1
        assert not formula_dir.exists()

    def test_root_app_runtime_pipeline_prints_formula_dir(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Through the root app, pipeline prints the sanitized pipeline directory — one line."""
        work, home = _isolate_work_home(monkeypatch, tmp_path)

        with mock.patch.object(subprocess, "run", return_value=_git_completed("main\n")):
            result = CliRunner().invoke(app, ["runtime", "pipeline", "pybuggy:api"])
            formula_dir = resolve_runtime_dir("pipelines", "pybuggy-api")

        assert result.exit_code == 0
        assert result.output.strip() == str(formula_dir)
        assert result.output.strip() == str(
            home / ".goga" / "runtime" / "pipelines" / normalize_project_path(work) / "main" / "pybuggy-api"
        )
        assert len(result.output.strip().splitlines()) == 1

    def test_root_app_runtime_archive_creates_wrapper_root_archive(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Through the root app, archive -b writes the archive at the printed path, wrapper-rooted."""
        work, home = _isolate_work_home(monkeypatch, tmp_path)
        segment = normalize_project_path(work)
        _seed_target(
            home,
            ".goga",
            "runtime",
            "builds",
            segment,
            "feature-x",
            files={"a.txt": "hello", "sub/b.log": "log"},
        )

        with mock.patch.object(subprocess, "run", return_value=_git_completed("feature/x\n")):
            result = CliRunner().invoke(app, ["runtime", "archive", "-b"])

        assert result.exit_code == 0

        archive = Path(result.output.strip())

        assert len(result.output.strip().splitlines()) == 1
        assert archive == work / "goga-runtime-build-feature-x.tar.gz"
        assert archive.is_file()

        with tarfile.open(archive) as tar:
            names = tar.getnames()

        assert names[0] == "goga-runtime-build-feature-x"
        assert "goga-runtime-build-feature-x/a.txt" in names
        assert "goga-runtime-build-feature-x/sub/b.log" in names


class TestRunLocationParity:
    def test_runtime_build_matches_the_build_run_directory(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The printed build directory is the one the build run bind-mounts."""
        _isolate_work_home(monkeypatch, tmp_path)

        with mock.patch.object(subprocess, "run", return_value=_git_completed("release/9\n")):
            result = CliRunner().invoke(app, ["runtime", "build"])
            run_dir = resolve_build_runtime_dir()

        assert result.exit_code == 0
        assert result.output.strip() == str(run_dir)

    def test_runtime_pipeline_matches_the_pipeline_run_directory(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """The printed pipeline directory is the one the pipeline run composes for the same name."""
        _isolate_work_home(monkeypatch, tmp_path)

        with mock.patch.object(subprocess, "run", return_value=_git_completed("main\n")):
            result = CliRunner().invoke(app, ["runtime", "pipeline", "pybuggy:api"])
            run_dir = resolve_pipeline_runtime_dir("pybuggy:api")

        assert result.exit_code == 0
        assert result.output.strip() == str(run_dir)


class TestBranchOverride:
    def test_branch_override_addresses_explicit_segment_git_free(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """-b release/1.2 prints the build-parity path for release-1.2 — git never consulted."""
        _isolate_work_home(monkeypatch, tmp_path)

        with mock.patch.object(subprocess, "run", return_value=_git_completed("main\n")) as run_mock:
            result = CliRunner().invoke(app, ["runtime", "-b", "release/1.2", "build"])
            run_dir = resolve_runtime_dir("builds", branch="release-1.2")

        assert run_mock.call_count == 0
        assert result.exit_code == 0
        assert result.output.strip() == str(run_dir)


class TestDerivedBranchFallback:
    def test_git_failure_falls_back_to_default_segment(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """A failing git branch query degrades the segment to default through the whole CLI stack.

        The documented fallback (outside a repository, detached HEAD, or a
        missing git binary) — here delivered as a failing CompletedProcess,
        the boundary the real not-a-repository case produces.
        """
        work, home = _isolate_work_home(monkeypatch, tmp_path)

        failed = subprocess.CompletedProcess(
            ["git", "branch", "--show-current"],
            128,
            stdout="",
            stderr="fatal: not a git repository (or any of the parent directories): .git",
        )

        with mock.patch.object(subprocess, "run", return_value=failed):
            result = CliRunner().invoke(app, ["runtime", "build"])

        expected = home / ".goga" / "runtime" / "builds" / normalize_project_path(work) / "default"

        assert result.exit_code == 0
        assert result.output.strip() == str(expected)
        assert len(result.output.strip().splitlines()) == 1


class TestInImageRefusal:
    def test_root_app_runtime_refuses_inside_image(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Through the root app, the docker marker refuses the subcommand — clean, stdout empty."""
        monkeypatch.setenv("GOGA_DOCKER", "1")

        result = CliRunner().invoke(app, ["runtime", "build"])

        assert result.exit_code == 1
        assert "host" in result.stderr.lower()
        assert result.stdout == ""
