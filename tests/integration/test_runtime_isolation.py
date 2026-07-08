"""Cross-cell integration tests for ralphex runtime isolation (Task 8).

These stitch together the full runtime-isolation contract across all four cells
of the ``ralphex-runtime-isolation`` design:

    goga/runtime/paths.py            (leaf — pure path composition)
        -> goga/runtime/__init__.py  (facade: resolve_runtime_dir)
            -> goga/commands/build/build.py                (consumer A)
                  resolve_build_runtime_dir -> resolve_runtime_dir("builds")
                  build() mkdir + optional wipe + nested -v <dir>:/workspace/.ralphex
            -> goga/commands/pipeline/run_pipeline_container.py (consumer B)
                  resolve_pipeline_runtime_dir -> resolve_runtime_dir("pipelines", name)
                  run_pipeline_container() mkdir + optional wipe
                      + -v <dir>:/home/goga/pipeline  + AFM_DIR=/home/goga/pipeline
        -> goga/build/build.py       (in-container — reuses the mounted .ralphex/)
              _cleanup_ralphex_dir removed; .ralphex/ arrives as a prepared mount

These tests confirm the design's interaction diagram and data flows hold
end-to-end. They are deliberately cross-cell: each test asserts an invariant
that only holds when two or more cells are wired together through the shared
``goga.runtime`` leaf. Where a single cell already has exhaustive coverage
(``tests/runtime/``, ``tests/commands/build/``,
``tests/commands/pipeline/``, ``tests/build/``), these tests do NOT repeat that
coverage — they assert the *seams* between cells.

The docker/subprocess boundary is mocked per
``[[feedback_mock_patch_module_shadowing]]``: the package ``__init__``
re-exports submodule functions, which shadows string-based ``mock.patch`` paths
on Python 3.10, so the real modules are resolved via ``sys.modules`` and patched
by attribute. ``subprocess.run`` is always mocked alongside ``Popen`` because
the launcher ``finally`` blocks call ``docker kill`` via ``subprocess.run``,
which opens its own ``Popen``.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from unittest import mock

from click.testing import CliRunner
from goga.commands import build as build_cmd
from goga.commands.build.build import resolve_build_runtime_dir
from goga.commands.pipeline.run_pipeline_container import (
    resolve_pipeline_runtime_dir,
    run_pipeline_container,
)
from goga.config import BuildConfig, Config, PipelineConfig, TaskExecutorConfig
from goga.runtime import normalize_project_path, resolve_runtime_dir

# The two consumer modules shadow their submodule names in their package
# __init__, so resolve the real modules via sys.modules for attribute patching.
_build_mod = sys.modules["goga.commands.build.build"]
_rpc_mod = sys.modules["goga.commands.pipeline.run_pipeline_container"]


def _valid_config(*, image: str | None = "qarium/goga:latest") -> Config:
    """Return a minimal valid Config usable by both the build and pipeline flows."""
    return Config(
        lang="python",
        image=image,
        build=BuildConfig(task_executor=TaskExecutorConfig(agent="claude")),
        pipeline=PipelineConfig(agent="claude"),
    )


def _pin_project(tmp_path: Path, monkeypatch, *, branch: str = "main") -> tuple[Path, Path, str]:
    """Redirect home/cwd/branch so runtime dir composition is deterministic.

    Pins ``Path.home()`` under ``tmp_path``, ``Path.cwd()`` to a project living
    under that home, and ``resolve_git_branch`` to ``branch`` (the resolved,
    already-slugified branch name — slugification of raw git output is unit-tested
    in ``tests/runtime/``, so the cross-cell tests stub the post-slugify result).
    Returns the (home, project, normalized_project_name) triple so tests can
    compute the expected shared base path.
    """
    home = tmp_path / "home"
    proj = home / "proj"
    proj.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(Path, "home", lambda: home)
    monkeypatch.setattr(Path, "cwd", lambda: proj)
    monkeypatch.setattr("goga.runtime.paths.resolve_git_branch", lambda: branch)
    # Credential-mount resolution reads $HOME via expanduser(); isolate it from
    # the host's real credential files for these cross-cell tests.
    monkeypatch.setattr(_build_mod, "resolve_credential_mounts", lambda: [])
    monkeypatch.setattr(_rpc_mod, "resolve_credential_mounts", lambda: [])
    return home, proj, normalize_project_path(proj)


class TestSharedLeafFormula:
    """Both consumers derive their host path from the same goga.runtime leaf.

    The design's central invariant (Data Flows): a single routine —
    ``resolve_runtime_dir`` — composes every host runtime path from the same
    ``normalize_project_path`` + ``resolve_git_branch`` primitives, so build and
    pipeline state never collide and never duplicate the primitives.
    """

    def test_both_consumers_share_normalized_project_and_branch_segments(self, tmp_path, monkeypatch):
        """build and pipeline paths share the same <normalized_project>/<branch>/ base."""
        home, _proj, normalized = _pin_project(tmp_path, monkeypatch, branch="main")

        build_dir = resolve_build_runtime_dir()
        pipeline_dir = resolve_pipeline_runtime_dir("deploy")

        shared_base = home / ".goga" / "runtime"
        # build: ~/.goga/runtime/builds/<normalized>/<branch>  (no suffix)
        assert build_dir == shared_base / "builds" / normalized / "main"
        # pipeline: ~/.goga/runtime/pipelines/<normalized>/<branch>/deploy (name suffix)
        assert pipeline_dir == shared_base / "pipelines" / normalized / "main" / "deploy"
        # the <normalized>/<branch>/ portion is byte-identical across purposes — the
        # only divergence is the purpose segment and the optional suffix. The build
        # tail (normalized/branch) is exactly the pipeline tail with its suffix dropped.
        build_tail = build_dir.relative_to(shared_base / "builds")
        pipeline_tail = pipeline_dir.relative_to(shared_base / "pipelines")
        assert build_tail == pipeline_tail.parent

    def test_both_facades_delegate_to_resolve_runtime_dir_with_correct_args(self, monkeypatch):
        """Each facade calls goga.runtime.resolve_runtime_dir with its own purpose/suffix.

        The consumer modules bind ``resolve_runtime_dir`` into their own namespace
        via ``from ...runtime import resolve_runtime_dir``, so the call is
        intercepted at the consumer module (per
        ``[[feedback_mock_patch_module_shadowing]]``) — not at the leaf module.
        """
        monkeypatch.setattr(_build_mod, "resolve_runtime_dir", mock.Mock(return_value=Path("/leaf/out")))
        monkeypatch.setattr(_rpc_mod, "resolve_runtime_dir", mock.Mock(return_value=Path("/leaf/out")))

        resolve_build_runtime_dir()
        resolve_pipeline_runtime_dir("deploy")

        assert _build_mod.resolve_runtime_dir.call_args == mock.call("builds")
        assert _rpc_mod.resolve_runtime_dir.call_args == mock.call("pipelines", "deploy")

    def test_resolve_runtime_dir_composes_via_shared_primitives(self, tmp_path, monkeypatch):
        """resolve_runtime_dir reads cwd, normalizes it, resolves the branch, composes."""
        home, _proj, normalized = _pin_project(tmp_path, monkeypatch, branch="main")

        # Drive the REAL primitives end-to-end (no facade) for the build purpose.
        actual = resolve_runtime_dir("builds")
        expected = home / ".goga" / "runtime" / "builds" / normalized / "main"
        assert actual == expected
        assert actual.is_absolute()


class TestBuildRuntimeDirFlow:
    """build(clean=True): resolve -> mkdir -> optional wipe -> nested bind-mount.

    Cross-entity: the path resolved by ``resolve_build_runtime_dir`` is the path
    mkdir'd, the path wiped when ``--clean`` is set, and the path mounted at
    ``/workspace/.ralphex``.
    """

    def _patch_docker_surfaces(self, stack, *, popen_side_effect):
        """Mock only the docker/config surfaces; let the runtime path machinery run for real."""
        stack.enter_context(mock.patch.object(_build_mod, "_check_docker", return_value=True))
        stack.enter_context(mock.patch.object(_build_mod, "_read_git_config", return_value={}))
        stack.enter_context(mock.patch.object(_build_mod, "load_config", return_value=_valid_config()))
        stack.enter_context(mock.patch.object(_build_mod, "_write_env_file", return_value=Path("/tmp/env")))
        stack.enter_context(mock.patch.object(subprocess, "Popen", side_effect=popen_side_effect))
        stack.enter_context(mock.patch.object(subprocess, "run"))

    def test_clean_true_mkdirs_wipes_and_mounts_resolved_path(self, tmp_path, monkeypatch):
        """build(clean=True) resolves, mkdirs, wipes, and mounts the SAME path at /workspace/.ralphex."""
        from contextlib import ExitStack

        _pin_project(tmp_path, monkeypatch)
        runtime_dir = resolve_build_runtime_dir()
        # Pre-populate stale state so the wipe is actually exercised — a no-op
        # clean would leave old-state.json behind and fail the assertions below.
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "old-state.json").write_text('{"stale": true}')

        captured: dict = {}

        def _fake_popen(cmd, *args, **kwargs):
            captured["cmd"] = list(cmd)
            proc = mock.Mock()
            proc.wait.return_value = 0
            return proc

        with ExitStack() as stack:
            self._patch_docker_surfaces(stack, popen_side_effect=_fake_popen)
            result = CliRunner().invoke(build_cmd, ["plan.md", "--clean"])

        assert result.exit_code == 0, result.output

        # mkdir happened (the dir still exists) and --clean wiped it empty —
        # the stale sentinel is gone, so the wipe genuinely ran.
        assert runtime_dir.exists()
        assert not (runtime_dir / "old-state.json").exists()
        assert not any(runtime_dir.iterdir())
        # the resolved path is the nested bind-mount source.
        assert f"{runtime_dir}:/workspace/.ralphex" in captured["cmd"]

    def test_build_path_never_leaks_into_env_file_or_env_args(self, tmp_path, monkeypatch):
        """The container sees only /workspace/.ralphex; the host path stays a mount source."""
        from contextlib import ExitStack

        _pin_project(tmp_path, monkeypatch)
        runtime_dir = resolve_build_runtime_dir()

        captured_cmd: dict = {}
        captured_env: dict = {}

        def _fake_popen(cmd, *args, **kwargs):
            captured_cmd["cmd"] = list(cmd)
            proc = mock.Mock()
            proc.wait.return_value = 0
            return proc

        def _fake_write_env(env, extra_env):
            captured_env["env"] = dict(env)
            captured_env["extra"] = tuple(extra_env)
            return Path("/tmp/env")

        with ExitStack() as stack:
            stack.enter_context(mock.patch.object(_build_mod, "_check_docker", return_value=True))
            stack.enter_context(mock.patch.object(_build_mod, "_read_git_config", return_value={}))
            stack.enter_context(mock.patch.object(_build_mod, "load_config", return_value=_valid_config()))
            stack.enter_context(mock.patch.object(_build_mod, "_write_env_file", side_effect=_fake_write_env))
            stack.enter_context(mock.patch.object(subprocess, "Popen", side_effect=_fake_popen))
            stack.enter_context(mock.patch.object(subprocess, "run"))
            result = CliRunner().invoke(build_cmd, ["plan.md", "-e", "EXTRA=keep-me"])

        assert result.exit_code == 0, result.output

        host_marker = ".goga/runtime/builds"
        for value in captured_env["env"].values():
            assert host_marker not in value
            assert str(runtime_dir) not in value
        for pair in captured_env["extra"]:
            assert host_marker not in pair
        # the only container-side mention of the runtime path is the mount target.
        cmd = captured_cmd["cmd"]
        assert f"{runtime_dir}:/workspace/.ralphex" in cmd
        for arg in cmd:
            if host_marker in arg:
                assert arg == f"{runtime_dir}:/workspace/.ralphex"


class TestPipelineRuntimeDirFlow:
    """run_pipeline_container(name, clean=...): resolve -> mkdir -> optional wipe -> mount + AFM_DIR.

    Cross-entity: the path resolved by ``resolve_pipeline_runtime_dir`` is the
    path mkdir'd, the path wiped when ``clean`` is set, the path mounted at
    ``/home/goga/pipeline``, and reflected in ``AFM_DIR`` (container-side only).
    """

    def _patch_pipeline_surfaces(self, monkeypatch, tmp_path):
        """Stub the pipeline helpers that would touch the host; keep runtime path real."""
        _pin_project(tmp_path, monkeypatch)
        monkeypatch.setattr(_rpc_mod, "_check_docker", lambda: True)
        monkeypatch.setattr(_rpc_mod, "_allocate_port", lambda: 50321)
        monkeypatch.setattr(_rpc_mod, "_read_git_config", lambda: {})

    def test_clean_true_wipes_mounts_and_sets_afm_dir(self, tmp_path, monkeypatch):
        """clean=True wipes the resolved dir, mounts it rw at /home/goga/pipeline, sets AFM_DIR."""
        self._patch_pipeline_surfaces(monkeypatch, tmp_path)
        runtime_dir = resolve_pipeline_runtime_dir("deploy")
        runtime_dir.mkdir(parents=True, exist_ok=True)
        (runtime_dir / "old-state.json").write_text("{}")

        captured_env: dict[str, str] = {}
        real_write = _rpc_mod._write_env_file

        def capture(env, extra_env=()):
            captured_env.update(env)
            return real_write(env, extra_env)

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(_rpc_mod, "_write_env_file", side_effect=capture),
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", _valid_config(), (), None, {}, True, False)

        # wiped + recreated empty before launch.
        assert runtime_dir.exists()
        assert not (runtime_dir / "old-state.json").exists()
        assert not any(runtime_dir.iterdir())

        cmd = mock_popen.call_args[0][0]
        # the resolved path is mounted read-write at /home/goga/pipeline.
        assert f"{runtime_dir}:/home/goga/pipeline" in cmd
        assert not any(arg == f"{runtime_dir}:/home/goga/pipeline:ro" for arg in cmd)
        # AFM_DIR points at the container-side mount target (never the host path).
        assert captured_env["AFM_DIR"] == "/home/goga/pipeline"

    def test_pipeline_host_path_never_leaks_into_env_file(self, tmp_path, monkeypatch):
        """The env-file carries AFM_DIR as /home/goga/pipeline; the host path never leaks."""
        self._patch_pipeline_surfaces(monkeypatch, tmp_path)
        runtime_dir = resolve_pipeline_runtime_dir("deploy")

        env_contents: list[str] = []
        real_write = _rpc_mod._write_env_file

        def capture(env, extra_env=()):
            path = real_write(env, extra_env)
            env_contents.append(path.read_text())
            return path

        mock_proc = mock.Mock()
        mock_proc.wait.return_value = 0
        with (
            mock.patch.object(_rpc_mod, "_write_env_file", side_effect=capture),
            mock.patch.object(subprocess, "Popen", return_value=mock_proc) as mock_popen,
            mock.patch.object(subprocess, "run"),
        ):
            run_pipeline_container("deploy", _valid_config())

        cmd = mock_popen.call_args[0][0]
        env_text = "\n".join(env_contents)
        host_marker = ".goga/runtime/pipelines"
        assert "AFM_DIR=/home/goga/pipeline\n" in env_text
        assert host_marker not in env_text
        # the only docker arg carrying the host path is the bind-mount source.
        for arg in cmd:
            if host_marker in arg:
                assert arg == f"{runtime_dir}:/home/goga/pipeline"


class TestStructuralInvariants:
    """Single-source-of-truth invariants enforced by scanning the goga/ tree.

    These guard against regressions where the relocated primitives or renamed
    facades creep back in as local copies. They scan the on-disk source (not the
    test fixtures) so they catch a stale copy in ANY cell.
    """

    @staticmethod
    def _source_files() -> list[Path]:
        """Return all .py files under goga/, excluding bytecode caches."""
        repo_goga = Path(__file__).resolve().parents[2] / "goga"
        return sorted(p for p in repo_goga.rglob("*.py"))

    def test_normalize_project_path_defined_once_in_runtime(self):
        """normalize_project_path lives only in goga/runtime/paths.py (no duplicate)."""
        hits = [path for path in self._source_files() if _defines_function(path, "normalize_project_path")]
        assert [p.name for p in hits] == ["paths.py"]
        assert hits[0].parent.name == "runtime"

    def test_resolve_git_branch_defined_once_in_runtime(self):
        """resolve_git_branch lives only in goga/runtime/paths.py (no duplicate)."""
        hits = [path for path in self._source_files() if _defines_function(path, "resolve_git_branch")]
        assert [p.name for p in hits] == ["paths.py"]
        assert hits[0].parent.name == "runtime"

    def test_old_afm_runtime_dir_names_absent(self):
        """The pre-rename names resolve_afm_runtime_dir / clean_afm_runtime_dir are gone."""
        offenders: list[str] = []
        for path in self._source_files():
            text = path.read_text()
            for stale in ("resolve_afm_runtime_dir", "clean_afm_runtime_dir"):
                if stale in text:
                    offenders.append(f"{path}: {stale}")
        assert offenders == [], f"stale afm names still present: {offenders}"

    def test_cleanup_ralphex_dir_absent_from_build_cell(self):
        """The in-container _cleanup_ralphex_dir is gone from goga/build (host owns .ralphex/)."""
        build_cell = Path(__file__).resolve().parents[2] / "goga" / "build"
        offenders: list[str] = []
        for path in sorted(build_cell.rglob("*.py")):
            if "_cleanup_ralphex_dir" in path.read_text():
                offenders.append(str(path))
        assert offenders == [], f"_cleanup_ralphex_dir still present in goga/build: {offenders}"

    def test_in_container_build_imports_not_runtime(self):
        """goga/build receives .ralphex/ as a mount — it must NOT import goga.runtime."""
        build_files = [path for path in self._source_files() if path.parts[-2] == "build" and path.parts[-3] == "goga"]
        for path in build_files:
            text = path.read_text()
            assert "goga.runtime" not in text, f"{path} unexpectedly imports goga.runtime"

    def test_both_consumers_import_resolve_runtime_dir_from_runtime(self):
        """build and pipeline command cells both import resolve_runtime_dir from goga.runtime."""
        build_text = (_build_mod.__file__ and Path(_build_mod.__file__).read_text()) or ""
        pipeline_text = (_rpc_mod.__file__ and Path(_rpc_mod.__file__).read_text()) or ""
        assert "from ...runtime import resolve_runtime_dir" in build_text
        assert "from ...runtime import resolve_runtime_dir" in pipeline_text


def _defines_function(path: Path, name: str) -> bool:
    """True if path defines a top-level ``def <name>(`` (not merely references it)."""
    try:
        text = path.read_text()
    except (OSError, UnicodeDecodeError):
        return False
    return f"def {name}(" in text
