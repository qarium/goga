"""Contract and logic tests for the entity declared in
``goga/commands/runtime/CODEMANIFEST`` with ``location: runtime.py``: the
``runtime`` click group with the ``build``/``pipeline``/``archive``
subcommands.

The group carries the shared ``-b/--branch`` scope (bound only before the
subcommand token); the subcommands wire the ``targets``/``archive``
routines into the CLI surface with the project's error strategy: the
in-image refusal, the empty/dash name guards, and the XOR target
selection are ``click.ClickException`` clean errors (exit 1, stdout
empty), while argv-form errors (a missing NAME, an unknown option after
the subcommand, a bare group) are click's own usage errors (exit 2).
The boundary mocks follow the convention: git via the
``subprocess.run`` CompletedProcess pattern, ``Path.home`` via
monkeypatch, real file I/O under ``tmp_path``; ``tests/conftest.py``
already scrubs ``GOGA_DOCKER`` between tests.
"""

from __future__ import annotations

import importlib
import subprocess
import tarfile
from pathlib import Path
from unittest import mock

import click
import pytest
from click.testing import CliRunner
from goga.commands.runtime import runtime
from goga.runtime import normalize_project_path

# The cell module itself — the goga.commands facade re-export shadows the
# ``runtime`` attribute with the group object, so the module is bound through
# sys.modules instead of the ``from goga.commands import runtime`` form.
runtime_cell = importlib.import_module("goga.commands.runtime")


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


# --- Contract tests ---


class TestRuntimeGroupContract:
    def test_runtime_importable_from_facade(self) -> None:
        """runtime is importable from the goga.commands.runtime facade."""
        assert runtime_cell.runtime is runtime

    def test_runtime_is_a_click_group(self) -> None:
        """runtime is a click.Group container for the subcommands."""
        assert isinstance(runtime, click.Group)

    def test_runtime_registers_three_subcommands(self) -> None:
        """The group carries exactly the three declared subcommands."""
        assert set(runtime.commands) == {"build", "pipeline", "archive"}

    def test_group_carries_only_the_branch_option(self) -> None:
        """The group owns the shared -b/--branch option — and nothing else."""
        assert len(runtime.params) == 1
        branch_option = runtime.params[0]
        assert isinstance(branch_option, click.Option)
        assert branch_option.name == "branch"
        assert {"-b", "--branch"} <= set(branch_option.opts)
        assert branch_option.default is None

    def test_pipeline_carries_the_required_name_argument(self) -> None:
        """pipeline owns the required NAME positional — and nothing else."""
        pipeline = runtime.commands["pipeline"]
        assert len(pipeline.params) == 1
        name_argument = pipeline.params[0]
        assert isinstance(name_argument, click.Argument)
        assert name_argument.name == "name"
        assert name_argument.required

    def test_archive_carries_build_pipeline_output_options(self) -> None:
        """archive owns the -b/--build flag plus the -p and -o value options."""
        archive = runtime.commands["archive"]
        by_name = {param.name: param for param in archive.params}
        assert set(by_name) == {"build", "pipeline", "output"}

        assert isinstance(by_name["build"], click.Option)
        assert by_name["build"].is_flag
        assert {"-b", "--build"} <= set(by_name["build"].opts)

        assert isinstance(by_name["pipeline"], click.Option)
        assert {"-p", "--pipeline"} <= set(by_name["pipeline"].opts)
        assert by_name["pipeline"].default is None

        assert isinstance(by_name["output"], click.Option)
        assert {"-o", "--output"} <= set(by_name["output"].opts)
        assert by_name["output"].default is None

    def test_bare_runtime_group_prints_help_nonzero(self) -> None:
        """A bare group invocation prints help and exits 2 — the click group default.

        Pins the corrected review finding: the bare group matches a bare
        ``goga history`` (exit 2), never an exit-0 assumption.
        """
        result = CliRunner().invoke(runtime, [])

        assert result.exit_code == 2
        assert "Usage:" in result.output


# --- Logic tests — positives ---


class TestRuntimePathQueries:
    def test_runtime_build_prints_build_dir_single_line(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """build prints exactly the build directory of the mocked branch — one line, nothing created."""
        work = tmp_path / "work"
        work.mkdir()
        monkeypatch.chdir(work)
        monkeypatch.setattr(Path, "home", lambda: Path("/Users/tester"))

        with mock.patch.object(subprocess, "run", return_value=_git_completed("feature/x\n")):
            result = CliRunner().invoke(runtime, ["build"])

        expected = Path("/Users/tester/.goga/runtime/builds") / normalize_project_path(work) / "feature-x"

        assert result.exit_code == 0
        assert result.output.strip() == str(expected)
        assert len(result.output.strip().splitlines()) == 1
        assert not expected.exists()

    def test_runtime_pipeline_sanitizes_colons_like_run_time(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """pipeline sanitizes the name exactly as the run composes its state segment."""
        work = tmp_path / "work"
        work.mkdir()
        monkeypatch.chdir(work)

        with mock.patch.object(subprocess, "run", return_value=_git_completed("main\n")):
            result = CliRunner().invoke(runtime, ["pipeline", "pybuggy:api-feature"])

        suffix = f"/pipelines/{normalize_project_path(work)}/main/pybuggy-api-feature"

        assert result.exit_code == 0
        assert result.output.strip().endswith(suffix)


class TestRuntimeArchive:
    def test_runtime_archive_build_target_creates_wrapper_root_archive(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """archive -b writes the default-named archive with the wrapper-root layout."""
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
            result = CliRunner().invoke(runtime, ["archive", "-b"])

        assert result.exit_code == 0

        archive = Path(result.output.strip())

        assert archive == work / "goga-runtime-build-feature-x.tar.gz"
        assert archive.is_file()

        with tarfile.open(archive) as tar:
            names = tar.getnames()

        assert names[0] == "goga-runtime-build-feature-x"
        assert "goga-runtime-build-feature-x/a.txt" in names
        assert "goga-runtime-build-feature-x/sub/b.log" in names

    def test_runtime_archive_pipeline_target_and_explicit_output(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """archive -p packages the sanitized pipeline target; -o overwrites the existing file."""
        work, home = _isolate_work_home(monkeypatch, tmp_path)
        segment = normalize_project_path(work)
        _seed_target(home, ".goga", "runtime", "pipelines", segment, "main", "pybuggy-api")
        out_path = tmp_path / "report.tar.gz"
        out_path.write_text("PRE-EXISTING")

        with mock.patch.object(subprocess, "run", return_value=_git_completed("main\n")):
            result = CliRunner().invoke(runtime, ["archive", "-p", "pybuggy:api", "-o", str(out_path)])

        assert result.exit_code == 0
        assert out_path.is_file()

        with tarfile.open(out_path) as tar:
            assert tar.getnames()[0] == "goga-runtime-pybuggy-api-main"

    def test_runtime_branch_option_overrides_segment(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """The group -b/--branch replaces the git-derived segment — git is never consulted."""
        work, home = _isolate_work_home(monkeypatch, tmp_path)
        segment = normalize_project_path(work)
        _seed_target(home, ".goga", "runtime", "builds", segment, "release-1.2")

        with mock.patch.object(subprocess, "run", return_value=_git_completed("main\n")) as run_mock:
            result = CliRunner().invoke(runtime, ["-b", "release/1.2", "build"])

        assert run_mock.call_count == 0
        assert result.exit_code == 0
        assert result.output.strip().endswith(f"/builds/{segment}/release-1.2")

    def test_runtime_dual_b_parses_at_both_levels(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """-b before the token is the group branch; -b after it is the archive build flag."""
        work, home = _isolate_work_home(monkeypatch, tmp_path)
        segment = normalize_project_path(work)
        _seed_target(home, ".goga", "runtime", "builds", segment, "main")

        with mock.patch.object(subprocess, "run", return_value=_git_completed("main\n")):
            result = CliRunner().invoke(runtime, ["-b", "main", "archive", "-b"])

        assert result.exit_code == 0
        assert "goga-runtime-build-main" in result.output


# --- Logic tests — negatives ---


class TestRuntimeRefusals:
    def test_runtime_subcommands_refuse_inside_image(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Every subcommand refuses inside the goga image: clean error, empty stdout."""
        monkeypatch.setenv("GOGA_DOCKER", "1")

        runner = CliRunner()

        for argv in (["build"], ["pipeline", "p"], ["archive", "-b"]):
            result = runner.invoke(runtime, argv)
            assert result.exit_code == 1
            assert "host" in result.stderr.lower()
            assert result.stdout == ""

    def test_runtime_archive_target_selection_usage_errors(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """Neither or both targets is a clean error — and no archive file appears."""
        work = tmp_path / "work"
        work.mkdir()
        monkeypatch.chdir(work)

        runner = CliRunner()

        for argv in (["archive"], ["archive", "-b", "-p", "x"]):
            result = runner.invoke(runtime, argv)
            assert result.exit_code != 0
            assert "exactly one" in result.stderr

        assert list(work.glob("*.tar.gz")) == []

    def test_runtime_pipeline_dash_leading_name_is_clean_error(self) -> None:
        """A dash-leading NAME (via --) is a clean invalid-name error."""
        result = CliRunner().invoke(runtime, ["pipeline", "--", "-weird"])

        assert result.exit_code == 1
        assert "invalid pipeline name" in result.stderr

    def test_runtime_pipeline_empty_name_is_clean_error(self) -> None:
        """An empty NAME is a clean error — the empty path segment is not a pipeline address."""
        result = CliRunner().invoke(runtime, ["pipeline", ""])

        assert result.exit_code == 1
        assert "invalid pipeline name" in result.stderr
        assert result.stdout == ""

    def test_runtime_archive_empty_pipeline_value_is_clean_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """An empty -p value is a clean error — it would package the whole branch state."""
        work = tmp_path / "work"
        work.mkdir()
        monkeypatch.chdir(work)

        with mock.patch.object(subprocess, "run", return_value=_git_completed("feature-x\n")):
            result = CliRunner().invoke(runtime, ["archive", "-p", ""])

        assert result.exit_code == 1
        assert "invalid pipeline name" in result.stderr
        assert list(work.glob("*.tar.gz")) == []

    def test_runtime_archive_pipeline_dash_value_is_clean_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A dash-leading -p value is taken as the value and refused by the guard."""
        work = tmp_path / "work"
        work.mkdir()
        monkeypatch.chdir(work)

        with mock.patch.object(subprocess, "run", return_value=_git_completed("feature-x\n")):
            result = CliRunner().invoke(runtime, ["archive", "-p", "-weird"])

        assert result.exit_code == 1
        assert "invalid pipeline name" in result.stderr
        assert result.stdout == ""
        assert list(work.glob("*.tar.gz")) == []

    def test_runtime_pipeline_missing_name_is_usage_error(self) -> None:
        """A missing NAME is click's own usage error — non-zero exit."""
        result = CliRunner().invoke(runtime, ["pipeline"])

        assert result.exit_code == 2

    def test_runtime_archive_missing_target_names_path_no_archive(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """A missing target directory is a clean error naming the path — no archive created."""
        work, home = _isolate_work_home(monkeypatch, tmp_path)

        with mock.patch.object(subprocess, "run", return_value=_git_completed("feature-x\n")):
            result = CliRunner().invoke(runtime, ["archive", "-b"])

        expected_missing = home / ".goga" / "runtime" / "builds" / normalize_project_path(work) / "feature-x"

        assert result.exit_code == 1
        assert str(expected_missing) in result.stderr
        assert list(work.glob("*.tar.gz")) == []

    def test_runtime_archive_default_name_collision_refused(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """An existing default-named file is refused with a pointer to -o/--output."""
        work, home = _isolate_work_home(monkeypatch, tmp_path)
        segment = normalize_project_path(work)
        _seed_target(home, ".goga", "runtime", "builds", segment, "feature-x")
        collision = work / "goga-runtime-build-feature-x.tar.gz"
        collision.write_text("TAKEN")

        with mock.patch.object(subprocess, "run", return_value=_git_completed("feature/x\n")):
            result = CliRunner().invoke(runtime, ["archive", "-b"])

        assert result.exit_code == 1
        assert "-o" in result.stderr
        assert "--output" in result.stderr
        assert collision.read_text() == "TAKEN"

    def test_runtime_archive_output_directory_is_error(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """An -o pointing at an existing directory is a clean error; nothing is written."""
        work, home = _isolate_work_home(monkeypatch, tmp_path)
        segment = normalize_project_path(work)
        _seed_target(home, ".goga", "runtime", "builds", segment, "feature-x")
        dest_dir = work / "destdir"
        dest_dir.mkdir()

        with mock.patch.object(subprocess, "run", return_value=_git_completed("feature/x\n")):
            result = CliRunner().invoke(runtime, ["archive", "-b", "-o", str(dest_dir)])

        assert result.exit_code == 1
        assert list(dest_dir.iterdir()) == []
        assert list(work.glob("*.tar.gz")) == []

    def test_runtime_archive_output_missing_parent_is_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """An -o under a missing parent directory is a clean error — no implicit mkdir."""
        work, home = _isolate_work_home(monkeypatch, tmp_path)
        segment = normalize_project_path(work)
        _seed_target(home, ".goga", "runtime", "builds", segment, "feature-x")
        dest = work / "no" / "such" / "dir" / "a.tar.gz"

        with mock.patch.object(subprocess, "run", return_value=_git_completed("feature/x\n")):
            result = CliRunner().invoke(runtime, ["archive", "-b", "-o", str(dest)])

        assert result.exit_code == 1
        assert not (work / "no").exists()

    def test_runtime_archive_unwritable_destination_is_clean_error(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """An OSError at the packaging step surfaces as a clean error — no traceback.

        The destination is pre-created read-only in a writable directory (the
        explicit -o overwrite scenario): open fails before any data, the
        guarded cleanup keeps the pre-existing file, and the command wraps
        the OSError into a ClickException.
        """
        work, home = _isolate_work_home(monkeypatch, tmp_path)
        segment = normalize_project_path(work)
        _seed_target(home, ".goga", "runtime", "builds", segment, "feature-x")
        dest = work / "locked.tar.gz"
        dest.write_text("ORIGINAL")
        dest.chmod(0o444)

        try:
            with mock.patch.object(subprocess, "run", return_value=_git_completed("feature/x\n")):
                result = CliRunner().invoke(runtime, ["archive", "-b", "-o", str(dest)])
        finally:
            dest.chmod(0o644)

        assert result.exit_code == 1
        assert "Error:" in result.stderr
        assert "Traceback" not in result.output
        assert dest.read_text() == "ORIGINAL"


# --- Logic tests — edges ---


class TestRuntimeEdges:
    def test_runtime_archive_empty_target_directory_packages(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        """An existing but empty target directory is packaged — only the wrapper root inside."""
        work, home = _isolate_work_home(monkeypatch, tmp_path)
        segment = normalize_project_path(work)
        _seed_target(home, ".goga", "runtime", "builds", segment, "feature-x")

        with mock.patch.object(subprocess, "run", return_value=_git_completed("feature/x\n")):
            result = CliRunner().invoke(runtime, ["archive", "-b"])

        assert result.exit_code == 0

        archive = work / "goga-runtime-build-feature-x.tar.gz"

        with tarfile.open(archive) as tar:
            assert tar.getnames() == ["goga-runtime-build-feature-x"]

    def test_runtime_group_option_only_before_subcommand(self) -> None:
        """build carries no options — a -b after the token is a usage error."""
        result = CliRunner().invoke(runtime, ["build", "-b"])

        assert result.exit_code == 2
        assert "No such option" in result.stderr
