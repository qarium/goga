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
    PipelineAgents,
    PipelineDocument,
    PipelineHeader,
    StructuralError,
)

# goga.pipeline.run_pipeline is shadowed in the package __init__ by the
# run_pipeline function, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules and patch its
# run_flow / compile_flow attributes directly. Per [[feedback_mock_patch_module_shadowing]].
_run_pipeline_module = sys.modules["goga.pipeline.run_pipeline"]

# The four fixed agent-prompt keys; mirrors run_pipeline._AGENT_KEYS.
_AGENT_KEYS = ("planning", "implementation", "review", "summary")


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
    agents: PipelineAgents | None = None,
) -> tuple[PipelineDocument, FlowDocument]:
    """Build the documents tuple ``compile_flow`` now returns, for mock wiring.

    Shared by the materialization tests and the existing wiring tests so they
    exercise the same unpack shape. ``agents`` defaults to None (no header block).
    """
    pipeline_doc = PipelineDocument(
        header=PipelineHeader(name="deploy", description="d", agents=agents),
        format=BodyFormat.PHASES,
        body=PhasesBody(steps=[]),
    )
    flow_doc = FlowDocument(name="deploy", description="d", stages=[])
    return (pipeline_doc, flow_doc)


def _write_defaults(defaults_dir: Path, keys: tuple[str, ...] = _AGENT_KEYS) -> None:
    """Write ``default <key>\\n`` prompt files for the given keys into defaults_dir."""
    defaults_dir.mkdir(parents=True, exist_ok=True)
    for key in keys:
        (defaults_dir / f"{key}.md").write_text(f"default {key}\n")


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

        mock_run_flow.assert_called_once_with(afm_dir / "flow.yml", 50321)

    def test_run_pipeline_resolves_user_source_when_only_in_user_dir(self, tmp_path: Path, afm_dir: Path) -> None:
        """A pipeline only in user_dir still compiles + runs against its source path."""
        project_dir = tmp_path / "pipelines"
        project_dir.mkdir()
        user_dir = tmp_path / "user_pipelines"
        _write_pipeline(user_dir)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents()) as mock_compile,
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0) as mock_run_flow,
        ):
            exit_code = run_pipeline("deploy", project_dir, user_dir, 50321)

        assert exit_code == 0
        # compile_flow receives the user-dir pipeline path (resolved), the flow
        # path, and the resolved workflow (None — no workflow env, no basename
        # file at <cwd>/.goga/workflows/deploy.yml).
        mock_compile.assert_called_once_with((user_dir / "deploy.yml").resolve(), afm_dir / "flow.yml", workflow=None)
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
        mock_run_flow.assert_called_once_with(flow_path, 50321)

    def test_run_pipeline_threads_real_agents_override_through_full_chain(self, tmp_path: Path, afm_dir: Path) -> None:
        """A real ``agents`` header block threads verbatim through the whole chain.

        Unlike the materialization tests below (which mock ``compile_flow``), this
        drives the real parse_dsl → compile_flow → run_pipeline path with a real
        pipeline-file carrying an inline ``agents.planning`` override. The
        override must land byte-for-byte at ``<AFM_DIR>/prompts/planning.md``, and
        the non-overridden keys must fall back to the REAL package defaults (the
        resolver is NOT patched). This is the headline feature's truest path — a
        regression that normalized or trimmed the override text (e.g. an added
        ``.strip()``, or a block-scalar/normalization mismatch between parse and
        write) would break it.
        """
        afm_dir.mkdir(parents=True)
        project_dir = tmp_path / "pipelines"
        project_dir.mkdir()
        override = "Custom planning prompt.\nLine two.\n"
        (project_dir / "deploy.yml").write_text(
            "name: Deploy\n"
            "description: Deploy pipeline\n"
            "agents:\n"
            "  planning: |\n"
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
        # The override lands verbatim — no normalization, no trimming.
        assert (prompts_dir / "planning.md").read_text() == override
        # Non-overridden keys fall back to the real package defaults (non-empty).
        for key in ("implementation", "review", "summary"):
            assert (prompts_dir / f"{key}.md").read_text() != ""


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
        for key in _AGENT_KEYS:
            assert (prompts_dir / f"{key}.md").read_text() == f"default {key}\n"

    def test_run_pipeline_applies_partial_override(
        self, tmp_path: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An inline override on one key replaces only that file; others use defaults."""
        defaults_dir = tmp_path / "defaults"
        _write_defaults(defaults_dir)
        self._patch_defaults(monkeypatch, defaults_dir)

        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)
        agents = PipelineAgents(planning="OVERRIDE\n")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents(agents)),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert exit_code == 0
        prompts_dir = afm_dir / "prompts"
        assert (prompts_dir / "planning.md").read_text() == "OVERRIDE\n"
        for key in ("implementation", "review", "summary"):
            assert (prompts_dir / f"{key}.md").read_text() == f"default {key}\n"

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
        _write_defaults(defaults_dir, keys=("planning", "review", "summary"))  # no implementation
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
        """A missing default is fine when an inline override supplies that key."""
        defaults_dir = tmp_path / "defaults"
        _write_defaults(defaults_dir, keys=("planning", "review", "summary"))  # no implementation
        self._patch_defaults(monkeypatch, defaults_dir)

        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)
        agents = PipelineAgents(implementation="OVERRIDE\n")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents(agents)),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert exit_code == 0
        prompts_dir = afm_dir / "prompts"
        assert (prompts_dir / "implementation.md").read_text() == "OVERRIDE\n"
        for key in ("planning", "review", "summary"):
            assert (prompts_dir / f"{key}.md").read_text() == f"default {key}\n"

    def test_run_pipeline_full_override_writes_all_four_files(
        self, tmp_path: Path, afm_dir: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """All four overrides → no package default read; files written in fixed order."""
        defaults_dir = tmp_path / "defaults"
        defaults_dir.mkdir()  # intentionally empty — overrides cover every key
        self._patch_defaults(monkeypatch, defaults_dir)

        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)
        agents = PipelineAgents(planning="P\n", implementation="I\n", review="R\n", summary="S\n")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents(agents)),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, tmp_path / "user", 50321)

        assert exit_code == 0
        prompts_dir = afm_dir / "prompts"
        assert (prompts_dir / "planning.md").read_text() == "P\n"
        assert (prompts_dir / "implementation.md").read_text() == "I\n"
        assert (prompts_dir / "review.md").read_text() == "R\n"
        assert (prompts_dir / "summary.md").read_text() == "S\n"

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
        agents = PipelineAgents(planning="OVERRIDE\n")

        prompts_seen: dict[str, object] = {}

        def _run_flow_expects_prompts(_flow_path: object, _port: object) -> int:
            prompts_dir = afm_dir / "prompts"
            prompts_seen["files"] = sorted(p.name for p in prompts_dir.iterdir())
            prompts_seen["planning"] = (prompts_dir / "planning.md").read_text()
            return 0

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_fake_documents(agents)),
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
        for key in _AGENT_KEYS:
            assert (defaults_dir / f"{key}.md").is_file()
            assert (defaults_dir / f"{key}.md").read_text() != ""
