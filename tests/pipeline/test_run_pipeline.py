from __future__ import annotations

import inspect
import sys
from pathlib import Path
from unittest import mock
from unittest.mock import call

import pytest
from goga.pipeline import run_pipeline
from goga.pipeline.compiler import (
    BodyFormat,
    FlowDocument,
    PhasesBody,
    PipelineDocument,
    PipelineHeader,
    PipelineRoles,
    StructuralError,
)

# goga.pipeline.run_pipeline is shadowed in the package __init__ by the
# run_pipeline function, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules and patch its
# run_flow / compile_flow attributes directly. Per [[feedback_mock_patch_module_shadowing]].
_run_pipeline_module = sys.modules["goga.pipeline.run_pipeline"]

# The four materialized afm prompt-file stems. The first three resolve from the
# overridable roles (planner/executor/reviewer) via translate_role; summary is a
# separate, always-default channel. These are output-side afm names, not role
# aliases — run_pipeline materializes exactly these four files.
_PROMPT_STEMS = ("planning", "implementation", "review", "summary")


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


def _fake_documents(
    roles: PipelineRoles | None = None,
) -> tuple[PipelineDocument, FlowDocument]:
    """Build the documents tuple ``compile_flow`` now returns, for mock wiring.

    Shared by the materialization tests and the existing wiring tests so they
    exercise the same unpack shape. ``roles`` defaults to None (no header block).
    """
    pipeline_doc = PipelineDocument(
        header=PipelineHeader(name="deploy", description="d", roles=roles),
        format=BodyFormat.PHASES,
        body=PhasesBody(steps=[]),
    )
    flow_doc = FlowDocument(name="deploy", description="d", stages=[])
    return (pipeline_doc, flow_doc)


def _write_defaults(defaults_dir: Path, stems: tuple[str, ...] = _PROMPT_STEMS) -> None:
    """Write ``default <stem>\\n`` prompt files for the given stems into defaults_dir."""
    defaults_dir.mkdir(parents=True, exist_ok=True)
    for stem in stems:
        (defaults_dir / f"{stem}.md").write_text(f"default {stem}\n")


class TestRunPipelineContract:
    def test_run_pipeline_importable_from_facade(self) -> None:
        """run_pipeline is importable from the goga.pipeline facade."""
        assert run_pipeline is not None

    def test_run_pipeline_signature_matches_contract(self) -> None:
        """run_pipeline exposes the (name, project_dir, user_dir, port, parallel) signature."""
        signature = inspect.signature(run_pipeline)
        parameters = list(signature.parameters)

        assert parameters == ["name", "project_dir", "user_dir", "port", "parallel"]

    def test_run_pipeline_returns_zero_on_success(self, tmp_path: Path, afm_dir: Path) -> None:
        """run_pipeline returns 0 on a successful compile + afm invocation."""
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        assert exit_code == 0


class TestRunPipelineLogic:
    def test_run_pipeline_passes_compiled_flow_path_and_port_to_run_flow(self, tmp_path: Path, afm_dir: Path) -> None:
        """run_flow receives the compiled flow.yml path (not the DSL path) and the port."""
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0) as mock_run_flow,
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        mock_run_flow.assert_called_once_with(afm_dir / "flow.yml", 50321, max_parallel=None)

    def test_run_pipeline_resolves_user_source_when_only_in_user_dir(
        self, tmp_path: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A pipeline only in user_dir still compiles + runs against its source path."""
        project_dir = tmp_path / "pipelines"
        project_dir.mkdir()
        user_dir = tmp_path / "user_pipelines"
        _write_pipeline(user_dir)
        # resolve_project_name derives the in-container project name from git — pin
        # it to a known value so the exact compile_flow call assertion is deterministic.
        monkeypatch.setattr(_run_pipeline_module, "resolve_project_name", lambda: "widget")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0) as mock_run_flow,
        ):
            exit_code = run_pipeline("deploy", project_dir, user_dir, 50321)

        assert exit_code == 0
        # compile_flow receives the user-dir pipeline path (resolved), the flow
        # path, the resolved workflow (None — no workflow env, no basename
        # file at <cwd>/.goga/workflows/deploy.yml), the in-container
        # project root as root_dir (resolved from Path.cwd()), and the resolved
        # project_name (OUTPUT-only context derived from git at step 7).
        mock_compile.assert_called_once_with(
            (user_dir / "deploy.yml").resolve(),
            afm_dir / "flow.yml",
            workflow=None,
            root_dir=str(Path.cwd().resolve()),
            project_name="widget",
        )
        mock_run_flow.assert_called_once_with(afm_dir / "flow.yml", 50321, max_parallel=None)

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
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=7),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        assert exit_code == 7

    def test_run_pipeline_propagates_missing_binary_exit_code(self, tmp_path: Path, afm_dir: Path) -> None:
        """run_pipeline propagates run_flow's 127 (missing afm binary) exit code."""
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=127),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        assert exit_code == 127

    def test_run_pipeline_forwards_distinct_port_values(self, tmp_path: Path, afm_dir: Path) -> None:
        """The port integer is forwarded verbatim to run_flow — single source of truth."""
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0) as mock_run_flow,
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 8080)

        assert mock_run_flow.call_args == call(afm_dir / "flow.yml", 8080, max_parallel=None)

    def test_run_pipeline_threads_parallel_to_run_flow(self, tmp_path: Path, afm_dir: Path) -> None:
        """parallel=4 reaches run_flow as max_parallel=4 (host -p/--parallel → afm --max-parallel)."""
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0) as mock_run_flow,
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321, parallel=4)

        # max_parallel=4 threads straight through to run_flow — afm then receives
        # ``--max-parallel 4``. ``parallel`` is compilation-orthogonal, so
        # compile_flow is unaffected (the mock still returns the canned docs).
        mock_run_flow.assert_called_once_with(afm_dir / "flow.yml", 50321, max_parallel=4)

    def test_run_pipeline_parallel_none_default(self, tmp_path: Path, afm_dir: Path) -> None:
        """Omitting parallel threads max_parallel=None to run_flow (flag omitted downstream)."""
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0) as mock_run_flow,
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        # None reaches run_flow verbatim ⇒ run_flow omits --max-parallel (backward compat).
        mock_run_flow.assert_called_once_with(afm_dir / "flow.yml", 50321, max_parallel=None)

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

    def test_run_pipeline_propagates_structural_error_from_compile_flow(self, tmp_path: Path, afm_dir: Path) -> None:
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

    def test_run_pipeline_calls_compile_then_run_flow_in_order(self, tmp_path: Path, afm_dir: Path) -> None:
        """compile_flow runs before run_flow."""
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)
        order: list[str] = []

        def _compile(*args: object, **kwargs: object) -> tuple[PipelineDocument, FlowDocument]:
            order.append("compile")
            return _fake_documents()

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

        def _capture(pipeline_path: Path, flow_path: Path, **kwargs: object) -> tuple[PipelineDocument, FlowDocument]:
            captured["flow_path"] = flow_path
            return _fake_documents()

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", side_effect=_capture),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        assert captured["flow_path"].is_absolute()
        assert captured["flow_path"] == (tmp_path / ".afm").resolve() / "flow.yml"

    def test_run_pipeline_forwards_cwd_as_root_dir(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The ``run_pipeline`` routine forwards the in-container project root (``Path.cwd()``) as ``root_dir``.

        The host-side launcher sets ``workdir=/workspace`` and bind-mounts the
        project there, so ``Path.cwd()`` inside the container is the single
        source of truth for the afm ``root_dir`` directive. Mirrors the mount
        decision rather than re-declaring the literal.
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("AFM_DIR", str(tmp_path / ".afm"))
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)
        captured: dict[str, object] = {}

        def _capture(pipeline_path: Path, flow_path: Path, **kwargs: object) -> tuple[PipelineDocument, FlowDocument]:
            captured["root_dir"] = kwargs.get("root_dir")
            return _fake_documents()

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", side_effect=_capture),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user_pipelines", 50321)

        # root_dir is the resolved in-container CWD — single source of truth,
        # not a re-declared literal.
        assert captured["root_dir"] == str(tmp_path.resolve())

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

    def test_run_pipeline_writes_compiled_flow_file_for_real_compile(self, tmp_path: Path, afm_dir: Path) -> None:
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
            "  title: Build\n"
            "  prompt: Build it\n"
            "- name: ship\n"
            "  title: Ship\n"
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
        mock_run_flow.assert_called_once_with(flow_path, 50321, max_parallel=None)

    def test_run_pipeline_threads_real_role_override_through_full_chain(self, tmp_path: Path, afm_dir: Path) -> None:
        """A real ``roles`` header block threads verbatim through the whole chain.

        Unlike the materialization tests below (which mock ``compile_flow``), this
        drives the real parse_dsl → compile_flow → run_pipeline path with a real
        pipeline-file carrying an inline ``roles.planner`` override. The override
        must land byte-for-byte at ``<AFM_DIR>/prompts/planning.md`` (the planner
        role's afm stem via ``translate_role``), and the non-overridden roles plus
        summary must fall back to the REAL package defaults (the resolver is NOT
        patched). This is the headline feature's truest path — a regression that
        normalized or trimmed the override text (e.g. an added ``.strip()``, or a
        block-scalar/normalization mismatch between parse and write) would break
        it.
        """
        afm_dir.mkdir(parents=True)
        project_dir = tmp_path / "pipelines"
        project_dir.mkdir()
        override = "Custom planning prompt.\nLine two.\n"
        (project_dir / "deploy.yml").write_text(
            "name: Deploy\n"
            "description: Deploy pipeline\n"
            "roles:\n"
            "  planner: |\n"
            "    Custom planning prompt.\n"
            "    Line two.\n"
            "---\n"
            "\n"
            "- name: build\n"
            "  title: Build\n"
            "  prompt: Build it\n",
        )

        with mock.patch.object(_run_pipeline_module, "run_flow", return_value=0):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert exit_code == 0
        prompts_dir = afm_dir / "prompts"
        # The planner override lands at planning.md verbatim — no normalization.
        assert (prompts_dir / "planning.md").read_text() == override
        # Non-overridden roles + summary fall back to the real package defaults.
        for stem in ("implementation", "review", "summary"):
            assert (prompts_dir / f"{stem}.md").read_text() != ""


class TestRunPipelineSkipStages:
    """Step 6e — read ``GOGA_SKIP_STAGES`` and merge skip directives onto the
    resolved workflow via :func:`apply_skip_stages`, then forward the merged
    document to ``compile_flow``.

    Each test mocks ``compile_flow``/``run_flow`` (the real ``compile_flow``
    end-to-end scenarios live in the integration tests) and isolates CWD so the
    workflow-resolution path (``<cwd>/.goga/workflows/<name>.yml``) is hermetic.
    Materialization falls back to the REAL package defaults (the resolver is NOT
    patched here), so ``compile_flow`` returning ``roles=None`` is sufficient.
    """

    def test_run_pipeline_step6e_reads_skip_env_and_forwards(
        self, tmp_path: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GOGA_SKIP_STAGES=build,test → a merged skip-doc is forwarded to compile_flow.

        With no workflow-file at ``<cwd>/.goga/workflows/deploy.yml``, step 6
        resolves ``workflow=None``; step 6e then merges the skip directives into a
        fresh document whose ``build``/``test`` stages carry ``skip=True``.
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("GOGA_SKIP_STAGES", "build,test")
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert exit_code == 0
        wf = mock_compile.call_args.kwargs["workflow"]
        assert wf is not None
        assert set(wf.stages.keys()) == {"build", "test"}
        assert all(wf.stages[name].skip is True for name in wf.stages)

    def test_run_pipeline_step6e_empty_env_is_noop(
        self, tmp_path: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unset/empty GOGA_SKIP_STAGES leaves the resolved workflow unchanged (None)."""
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("GOGA_SKIP_STAGES", raising=False)
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert exit_code == 0
        # Regression-safe: behaves exactly as before step 6e existed.
        assert mock_compile.call_args.kwargs["workflow"] is None

    def test_run_pipeline_skip_merges_onto_resolved_workflow(
        self, tmp_path: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Skip directives merge ONTO a basename-resolved workflow (AC4).

        The workflow-file ``<cwd>/.goga/workflows/deploy.yml`` carries a ``build``
        override (``agent: codex``); ``GOGA_SKIP_STAGES=review`` merges a skip
        entry on top. The merged doc preserves the resolved ``build.agent`` and
        carries a fresh ``review`` skip stage (skip wins only for skipped names).
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("GOGA_WORKFLOW_DISABLED", raising=False)
        monkeypatch.delenv("GOGA_WORKFLOW_NAME", raising=False)
        monkeypatch.setenv("GOGA_SKIP_STAGES", "review")

        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "deploy.yml").write_text("stages:\n  build:\n    agent: codex\n")

        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert exit_code == 0
        wf = mock_compile.call_args.kwargs["workflow"]
        assert wf is not None
        # Resolved override preserved (the skip did not touch "build").
        assert wf.stages["build"].agent == "codex"
        assert wf.stages["build"].skip is False
        # Merged skip directive applied only to "review".
        assert wf.stages["review"].skip is True

    def test_apply_skip_stages_trailing_comma_in_env(
        self, tmp_path: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A trailing comma in GOGA_SKIP_STAGES yields no empty-string stage (edge).

        ``"build,"`` splits into ``["build", ""]``; the empty fragment is dropped so
        the merged document carries only ``build`` and never an ``""`` key.
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("GOGA_SKIP_STAGES", "build,")
        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert exit_code == 0
        wf = mock_compile.call_args.kwargs["workflow"]
        assert set(wf.stages.keys()) == {"build"}
        assert "" not in wf.stages


class TestRunPipelineSkipStagesIntegration:
    """Step 6e end-to-end through the REAL ``compile_flow``.

    Unlike :class:`TestRunPipelineSkipStages`, ``compile_flow`` is NOT mocked
    here — the :func:`apply_skip_stages`-synthesized document is consumed by the
    real 4pre (strict name validation) + 4skip (remove + reconnect
    ``depends_on``) + empty-body guard machinery, and the compiled
    ``<AFM_DIR>/flow.yml`` is read back. Only ``run_flow`` is patched (→ 0) so
    afm never runs. CWD is isolated so the basename workflow-resolution path
    (``<cwd>/.goga/workflows/<name>.yml``) is hermetic: no workflow-file means
    step 6 resolves ``workflow=None``, and step 6e merges the skip directives
    onto a fresh document.
    """

    def _write_stages_pipeline(self, directory: Path, body: str, name: str = "deploy") -> None:
        """Write a STAGES-format pipeline file (header + mapping body).

        Pattern mirrors ``tests/pipeline/compiler/fixtures/compile_flow/stages.yml``.
        The inline body is test content, not a contract.
        """
        directory.mkdir(parents=True, exist_ok=True)
        (directory / f"{name}.yml").write_text(f"name: Deploy\ndescription: Deploy pipeline\n---\n\n{body}")

    def test_run_pipeline_skip_removes_stage_from_compiled_flow(
        self, tmp_path: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """GOGA_SKIP_STAGES drops the named stage and reconnects dependents end-to-end.

        A STAGES deploy.yml (``build`` → ``test`` → ``review``) with
        ``GOGA_SKIP_STAGES=build`` compiles through the real ``compile_flow``:
        ``build`` is removed, ``test`` reconnected to nothing, ``review`` still
        depends on ``test``. Proves Data Flow Scenario 2 (workflow-less skip)
        end-to-end.
        """
        import yaml

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("GOGA_SKIP_STAGES", "build")
        afm_dir.mkdir(parents=True)
        project_dir = tmp_path / "pipelines"
        self._write_stages_pipeline(
            project_dir,
            "build:\n"
            "  title: Build\n"
            "\n"
            "test:\n"
            "  title: Test\n"
            "  depends_on:\n"
            "    - build\n"
            "\n"
            "review:\n"
            "  title: Review\n"
            "  depends_on:\n"
            "    - test\n",
        )

        with mock.patch.object(_run_pipeline_module, "run_flow", return_value=0):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert exit_code == 0

        compiled = yaml.safe_load((afm_dir / "flow.yml").read_text())
        stage_ids = [stage["id"] for stage in compiled["stages"]]
        assert "build" not in stage_ids
        assert set(stage_ids) == {"test", "review"}
        # workflow-less skip → workflow.prompt is None → prompt omitted from flow.
        assert compiled.get("prompt") is None
        # 4skip rewiring: ``test``'s reference to the removed ``build`` collapses
        # to nothing (explicit empty list), while ``review`` still depends on
        # ``test`` unchanged.
        by_id = {stage["id"]: stage for stage in compiled["stages"]}
        assert by_id["test"].get("depends_on") == []
        assert by_id["review"].get("depends_on") == ["test"]

    def test_run_pipeline_unknown_skip_raises_structural_error(
        self, tmp_path: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An unknown --skip name surfaces as a compile_flow StructuralError (AC3).

        :func:`apply_skip_stages` performs no name validation (deferred to
        ``compile_flow`` 4pre); ``GOGA_SKIP_STAGES=ghost`` therefore merges a
        ``ghost`` skip entry whose name matches no pipeline stage, and the real
        ``compile_flow`` 4pre strict validation raises before ``run_flow`` runs.
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("GOGA_SKIP_STAGES", "ghost")
        afm_dir.mkdir(parents=True)
        project_dir = tmp_path / "pipelines"
        self._write_stages_pipeline(
            project_dir,
            "build:\n  title: Build\n\ntest:\n  title: Test\n  depends_on:\n    - build\n",
        )

        with (
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0) as mock_run_flow,
            pytest.raises(StructuralError, match=r"unknown stage name in workflow\.stages: ghost"),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        mock_run_flow.assert_not_called()

    def test_run_pipeline_all_stages_skipped_empty_body(
        self, tmp_path: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Skipping the only stage trips the compile_flow empty-body guard (edge).

        A single-stage pipeline (``build``) with ``GOGA_SKIP_STAGES=build``
        removes every step; the real ``compile_flow`` post-4skip empty-body guard
        raises ``StructuralError("empty body")``.
        """
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("GOGA_SKIP_STAGES", "build")
        afm_dir.mkdir(parents=True)
        project_dir = tmp_path / "pipelines"
        self._write_stages_pipeline(
            project_dir,
            "build:\n  title: Build\n",
        )

        with (
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
            pytest.raises(StructuralError, match="empty body"),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user", 50321)


class TestRunPipelineMaterialization:
    """Step 6.5 — materialize the four agent prompt files into <AFM_DIR>/prompts/.

    Each test mocks ``compile_flow`` to return a documents tuple (per the
    unpack contract) and patches ``_resolve_defaults_dir`` at a tmp directory so
    the default-prompt source is deterministic. ``_isolate_home`` (autouse) is
    left intact per the plan's debugging notes.
    """

    def _patch_defaults(self, monkeypatch: pytest.MonkeyPatch, defaults_dir: Path) -> None:
        monkeypatch.setattr(_run_pipeline_module, "_resolve_defaults_dir", lambda: defaults_dir)

    def test_run_pipeline_materializes_four_default_prompts_without_agents(
        self, tmp_path: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """No ``agents`` block → all four files copied from package defaults."""
        defaults_dir = tmp_path / "defaults"
        _write_defaults(defaults_dir)
        self._patch_defaults(monkeypatch, defaults_dir)

        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert exit_code == 0
        prompts_dir = afm_dir / "prompts"
        assert prompts_dir.exists()
        files = sorted(p.name for p in prompts_dir.iterdir())
        assert files == ["implementation.md", "planning.md", "review.md", "summary.md"]
        for stem in _PROMPT_STEMS:
            assert (prompts_dir / f"{stem}.md").read_text() == f"default {stem}\n"

    def test_run_pipeline_applies_partial_override(
        self, tmp_path: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An inline override on one role replaces only its file; others use defaults."""
        defaults_dir = tmp_path / "defaults"
        _write_defaults(defaults_dir)
        self._patch_defaults(monkeypatch, defaults_dir)

        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)
        roles = PipelineRoles(planner="OVERRIDE\n")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents(roles)),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert exit_code == 0
        prompts_dir = afm_dir / "prompts"
        assert (prompts_dir / "planning.md").read_text() == "OVERRIDE\n"
        for stem in ("implementation", "review", "summary"):
            assert (prompts_dir / f"{stem}.md").read_text() == f"default {stem}\n"

    def test_run_pipeline_writes_prompts_idempotently_on_repeat(
        self, tmp_path: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Wipe+rmtree before write guarantees idempotency regardless of prior state."""
        defaults_dir = tmp_path / "defaults"
        _write_defaults(defaults_dir)
        self._patch_defaults(monkeypatch, defaults_dir)

        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)
        prompts_dir = afm_dir / "prompts"

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user", 50321)
            # Inject a leftover file from a hypothetical prior state.
            (prompts_dir / "leftover.md").write_text("leftover\n")
            run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        files = sorted(p.name for p in prompts_dir.iterdir())
        assert files == ["implementation.md", "planning.md", "review.md", "summary.md"]
        assert not (prompts_dir / "leftover.md").exists()

    def test_run_pipeline_raises_when_default_missing_and_no_override(
        self, tmp_path: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Missing default + no override raises before wipe (validate-first atomicity)."""
        defaults_dir = tmp_path / "defaults"
        _write_defaults(defaults_dir, stems=("planning", "review", "summary"))  # no implementation
        self._patch_defaults(monkeypatch, defaults_dir)

        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        # Atomicity sentinel: pre-existing prompts dir from a past run. The
        # validate-first algorithm must leave it untouched when it raises.
        prompts_dir = afm_dir / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        (prompts_dir / "sentinel.md").write_text("PRE-EXISTING\n")
        (prompts_dir / "planning.md").write_text("STALE\n")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0) as mock_run_flow,
            pytest.raises(RuntimeError, match="implementation: default prompt missing"),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        mock_run_flow.assert_not_called()
        # Wipe never ran: sentinel and stale file survive.
        assert (prompts_dir / "sentinel.md").read_text() == "PRE-EXISTING\n"
        assert (prompts_dir / "planning.md").read_text() == "STALE\n"
        # No fresh default file was written before the raise.
        assert not (prompts_dir / "implementation.md").exists()
        assert not (prompts_dir / "review.md").exists()
        assert not (prompts_dir / "summary.md").exists()

    def test_run_pipeline_succeeds_when_default_missing_but_override_supplied(
        self, tmp_path: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing default is fine when an inline override supplies that role."""
        defaults_dir = tmp_path / "defaults"
        _write_defaults(defaults_dir, stems=("planning", "review", "summary"))  # no implementation
        self._patch_defaults(monkeypatch, defaults_dir)

        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)
        roles = PipelineRoles(executor="OVERRIDE\n")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents(roles)),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert exit_code == 0
        prompts_dir = afm_dir / "prompts"
        assert (prompts_dir / "implementation.md").read_text() == "OVERRIDE\n"
        for stem in ("planning", "review", "summary"):
            assert (prompts_dir / f"{stem}.md").read_text() == f"default {stem}\n"

    def test_run_pipeline_full_role_override_plus_summary_default(
        self, tmp_path: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All three role overrides → their stems carry overrides; summary is always default.

        The three overridable roles (planner/executor/reviewer) each supply an
        override, so their stems (planning/implementation/review) carry the
        override text. ``summary`` has NO override channel — it always comes from
        the package default, even when every role is overridden. The defaults dir
        must still hold ``summary.md`` (the always-default channel); the role
        defaults are unused.
        """
        defaults_dir = tmp_path / "defaults"
        _write_defaults(defaults_dir, stems=("summary",))  # only the always-default channel
        self._patch_defaults(monkeypatch, defaults_dir)

        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)
        roles = PipelineRoles(planner="P\n", executor="I\n", reviewer="R\n")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents(roles)),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert exit_code == 0
        prompts_dir = afm_dir / "prompts"
        assert (prompts_dir / "planning.md").read_text() == "P\n"
        assert (prompts_dir / "implementation.md").read_text() == "I\n"
        assert (prompts_dir / "review.md").read_text() == "R\n"
        # summary is always-default — never overridden, copied from the package default.
        assert (prompts_dir / "summary.md").read_text() == "default summary\n"

    def test_run_pipeline_materializes_overrides_and_summary_default(
        self, tmp_path: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A role override materializes at its stem; summary is always the package default.

        Header ``roles.executor`` carries an inline override, which lands at
        ``implementation.md`` (the executor role's afm stem via ``translate_role``).
        The two unspecified roles fall back to their package defaults, and
        ``summary`` is always-default — never overridden — so it carries the
        package default text byte-for-byte. Exactly four prompt files materialize.
        """
        defaults_dir = tmp_path / "defaults"
        _write_defaults(defaults_dir)
        self._patch_defaults(monkeypatch, defaults_dir)

        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)
        roles = PipelineRoles(executor="exec override")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents(roles)),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert exit_code == 0
        prompts_dir = afm_dir / "prompts"
        # executor override → implementation.md (its translate_role stem).
        assert (prompts_dir / "implementation.md").read_text() == "exec override"
        # Unspecified roles fall back to their package defaults.
        assert (prompts_dir / "planning.md").read_text() == "default planning\n"
        assert (prompts_dir / "review.md").read_text() == "default review\n"
        # summary is always-default — never overridden.
        assert (prompts_dir / "summary.md").read_text() == "default summary\n"
        assert sorted(p.name for p in prompts_dir.iterdir()) == [
            "implementation.md",
            "planning.md",
            "review.md",
            "summary.md",
        ]

    def test_run_pipeline_raises_when_role_default_missing_without_override(
        self, tmp_path: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing role default with no override raises before the prompts dir exists.

        The patched defaults dir lacks ``planning.md`` (the planner role's stem).
        With ``roles=None`` there is no override, so step 8b must raise
        ``RuntimeError("planning: default prompt missing ...")`` during
        validate-before-wipe — BEFORE the prompts directory is created (atomicity:
        no partial state on disk when the run aborts).
        """
        defaults_dir = tmp_path / "defaults"
        # planning.md absent — the planner role's default is missing.
        _write_defaults(defaults_dir, stems=("implementation", "review", "summary"))
        self._patch_defaults(monkeypatch, defaults_dir)

        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0) as mock_run_flow,
            pytest.raises(RuntimeError, match="planning: default prompt missing"),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        mock_run_flow.assert_not_called()
        # Validate-before-wipe: the prompts dir was never created.
        assert not (afm_dir / "prompts").exists()

    def test_run_pipeline_raises_when_summary_default_missing(
        self, tmp_path: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A missing summary default raises before the prompts dir exists.

        ``summary`` has no override channel — it is always materialized from the
        package default. Step 8b checks the summary default explicitly (after the
        role loop) and raises ``RuntimeError("summary: default prompt missing
        from package")`` BEFORE the prompts directory is created (atomicity: no
        partial state on disk when the run aborts). Without this check a missing
        ``summary.md`` would instead surface as a ``FileNotFoundError`` at the
        post-wipe ``shutil.copy``, leaving a half-populated prompts dir behind.
        """
        defaults_dir = tmp_path / "defaults"
        # All three role defaults present; only summary.md (always-default channel) absent.
        _write_defaults(defaults_dir, stems=("planning", "implementation", "review"))
        self._patch_defaults(monkeypatch, defaults_dir)

        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0) as mock_run_flow,
            pytest.raises(RuntimeError, match="summary: default prompt missing from package"),
        ):
            run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        mock_run_flow.assert_not_called()
        # Validate-before-wipe: the prompts dir was never created.
        assert not (afm_dir / "prompts").exists()

    def test_run_pipeline_writes_prompts_before_run_flow(
        self, tmp_path: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All four prompt files exist BEFORE run_flow is invoked.

        afm needs the prompt files present at startup, so materialization
        (step 6.5) must complete before run_flow (step 7). ``run_flow`` is given a
        ``side_effect`` that inspects the prompts dir at the moment afm would be
        starting — if materialization were reordered to after ``run_flow``, the
        assertions inside the side_effect would fail. The mocked ``compile_flow``
        carries a partial override so both write paths (override + default copy)
        are exercised on the in-order check.
        """
        defaults_dir = tmp_path / "defaults"
        _write_defaults(defaults_dir)
        self._patch_defaults(monkeypatch, defaults_dir)

        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)
        roles = PipelineRoles(planner="OVERRIDE\n")

        prompts_seen: dict[str, object] = {}

        def _run_flow_expects_prompts(_flow_path: object, _port: object, **_kwargs: object) -> int:
            prompts_dir = afm_dir / "prompts"
            prompts_seen["files"] = sorted(p.name for p in prompts_dir.iterdir())
            prompts_seen["planning"] = (prompts_dir / "planning.md").read_text()
            return 0

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents(roles)),
            mock.patch.object(_run_pipeline_module, "run_flow", side_effect=_run_flow_expects_prompts),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert exit_code == 0
        # Captured from inside run_flow — proves the four files predate it.
        assert prompts_seen["files"] == [
            "implementation.md",
            "planning.md",
            "review.md",
            "summary.md",
        ]
        assert prompts_seen["planning"] == "OVERRIDE\n"

    def test_resolve_defaults_dir_points_at_real_package_prompts(self) -> None:
        """The real ``_resolve_defaults_dir()`` resolves to a dir holding the four shipped prompts.

        Every other materialization test monkeypatches the resolver to a tmp dir,
        so a packaging regression (assets moved, renamed, or excluded from the
        wheel) would leave the suite green while production hits
        ``RuntimeError("... default prompt missing ...")`` at first run. This pins
        the real resolver against the four shipped ``goga/assets/afm/prompts``
        files so a packaging drift is caught here, not in production.
        """
        defaults_dir = _run_pipeline_module._resolve_defaults_dir()

        assert defaults_dir.is_dir()
        for stem in _PROMPT_STEMS:
            assert (defaults_dir / f"{stem}.md").is_file()
            assert (defaults_dir / f"{stem}.md").read_text() != ""
