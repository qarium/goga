"""Contract and logic tests for the ``describe_pipeline`` Routine.

The pipeline cell's CODEMANIFEST declares ``describe_pipeline`` as the composer
of the single pipeline card: the author-facing name/description from the DSL
header plus the post-workflow stage composition in execution order. The card
shares the run path's machinery — the same ``resolve_workflow`` rule set and
the same ``compile_flow`` compiler — so what the card shows is structurally
what the run executes. Loop copies appear as separate rows (``NAME-1..N``),
skip directives from the workflow apply (a compiler directive), while the
``GOGA_SKIP_STAGES`` environment variable is deliberately NOT read.

The compiled flow-file is written to a throwaway temp directory (never the
project or a runtime directory) and removed once the card is composed. An
unknown pipeline name raises ``RuntimeError`` with a readable message.

The card composes through the same amendment layer a run composes through:
the amendment facts are resolved in the routine and delivered over the
checkpoint surface (unless the decision is disabled), the card reports the
committed tools as ``provenance``, and no run events fire. The tool-package
scenarios run the platform code for real over the boundary fixtures of
``tests/hooks/conftest.py``.

Fixtures mirror the design's General Setup: ``deploy.yml`` (STAGES format,
build→test) and ``hardening.yml`` (``stages.test.skip: true`` +
``extend.audit``).
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from typing import Any, get_type_hints
from unittest import mock

import pytest
from goga.history import current_year
from goga.pipeline.compiler import compile_flow
from goga.pipeline.describe_pipeline import describe_pipeline
from goga.pipeline.hooks import WorkIdentity
from goga.pipeline.order_stages import order_stages
from goga.pipeline.pipeline_card import CardStage, PipelineCard
from goga.pipeline.workflow import WorkflowDocument, WorkflowStage, parse_workflow

# The package __init__ re-exports ``describe_pipeline`` (the function), which
# shadows the ``describe_pipeline`` submodule name in attribute access —
# ``import goga.pipeline.describe_pipeline as module`` binds the function.
# Resolve the real module via ``sys.modules`` instead. Per
# [[feedback_mock_patch_module_shadowing]].
_describe_pipeline_module = sys.modules["goga.pipeline.describe_pipeline"]

# General Setup fixtures (STAGES DSL file + workflow files).
_DEPLOY_YML = """\
name: Deploy
description: Deploy the service
---

build:
  title: Build
test:
  title: Test
  depends_on:
    - build
"""

# ``stages.test.skip: true`` removes ``test``; ``extend.audit`` inserts a new
# stage after it (its depends_on resolves to build once test is removed).
_HARDENING_YML = "stages:\n  test:\n    skip: true\nextend:\n  audit:\n    after: [test]\n    title: Audit\n"

# A loop workflow — the nontrivial composition case: build expands into two
# chained copies (``build-1``/``build-2``), each a separate card row.
_LOOP_YML = "stages:\n  build:\n    loop: 2\n"

# The auto-match workflow of the amendment scenarios — an authored prompt the
# tool layer appends to. The skip directive exists only so the disabled
# scenario can prove the workflow did NOT leak into the composition (it would
# remove ``test`` if it did).
_AUTHORED_YML = "prompt: authored\nstages:\n  test:\n    skip: true\n"

# A user-source pipeline-file — distinct header values prove the card was
# composed from the user dir, not an identically named project file.
_USER_DEPLOY_YML = """\
name: User Deploy
description: User-level deploy pipeline
---

build:
  title: Build
"""


def _write_pipeline(project_dir: Path, name: str, text: str) -> Path:
    """Write a pipeline-file into ``project_dir`` and return its path."""
    project_dir.mkdir(parents=True, exist_ok=True)
    path = project_dir / f"{name}.yml"
    path.write_text(text)
    return path


def _write_workflow(cwd: Path, name: str, text: str) -> Path:
    """Write a workflow-file at ``<cwd>/.goga/workflows/<name>.yml`` and return it."""
    workflows_dir = cwd / ".goga" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    path = workflows_dir / f"{name}.yml"
    path.write_text(text)
    return path


@pytest.fixture(autouse=True)
def _empty_package_environment(pin_package_environment) -> None:
    """Pin the package environment empty for every test of this module.

    The card path builds the real registry through the amendment layer, so
    an unpinned environment would make the composed card depend on the
    machine's installed ``goga_tool_*`` packages. Tests that install a tool
    pin their own environment on top — the later pin wins.
    """
    pin_package_environment({})


class TestDescribePipelineContract:
    def test_describe_pipeline_is_importable_from_module(self) -> None:
        """The routine lives at its declared location ``goga.pipeline.describe_pipeline``."""
        assert _describe_pipeline_module.describe_pipeline is describe_pipeline

    def test_describe_pipeline_signature(self) -> None:
        """Signature: (name, project_dir, user_dir, workflow, no_workflow) -> PipelineCard."""
        signature = inspect.signature(describe_pipeline)
        # The module uses ``from __future__ import annotations``, so raw
        # annotations are strings — resolve them through get_type_hints.
        hints = get_type_hints(describe_pipeline)

        assert list(signature.parameters) == ["name", "project_dir", "user_dir", "workflow", "no_workflow"]
        assert hints["name"] is str
        assert hints["project_dir"] is Path
        assert hints["user_dir"] is Path
        assert hints["workflow"] == str | None
        assert hints["no_workflow"] is bool
        assert hints["return"] is PipelineCard

    def test_describe_pipeline_card_carries_empty_provenance_without_tools(
        self,
        tmp_path: Path,
        isolated_cwd: Path,
        pin_package_environment,
    ) -> None:
        """The no-tools path composes through the amendment layer as the passthrough.

        With the package environment pinned empty the registry builds empty,
        the delivery commits nothing, and the overlay is the passthrough —
        the returned card's ``provenance`` is the deterministic empty list.
        """
        pin_package_environment({})
        project_dir = tmp_path / "project_pipelines"
        _write_pipeline(project_dir, "deploy", _DEPLOY_YML)

        card = describe_pipeline("deploy", project_dir, tmp_path / "user_pipelines", None, False)

        assert card.provenance == []


class TestDescribePipelineLogic:
    def test_describe_pipeline_returns_card_from_header_and_stages(self, tmp_path: Path, isolated_cwd: Path) -> None:
        """Name/description are the author-facing header values; stages are the compiled rows.

        No ``.goga/workflows`` directory exists, so no workflow applies — the
        raw composition (build, test) is reported. The card name is the header
        ``name`` ("Deploy"), not the discovered stem ("deploy").
        """
        project_dir = tmp_path / "project_pipelines"
        pipeline_path = _write_pipeline(project_dir, "deploy", _DEPLOY_YML)

        card = describe_pipeline("deploy", project_dir, tmp_path / "user_pipelines", None, False)

        assert card.name == "Deploy"
        assert card.description == "Deploy the service"
        assert [(stage.id, stage.title) for stage in card.stages] == [
            ("build", "Build"),
            ("test", "Test"),
        ]
        assert all(isinstance(stage, CardStage) for stage in card.stages)
        # The pipeline-file itself was consumed read-only.
        assert pipeline_path.exists()

    def test_describe_pipeline_user_source_composes_from_user_dir(self, tmp_path: Path, isolated_cwd: Path) -> None:
        """A pipeline discovered in the user dir composes its card from the user file."""
        user_dir = tmp_path / "user_pipelines"
        user_path = _write_pipeline(user_dir, "deploy", _USER_DEPLOY_YML)

        card = describe_pipeline("deploy", tmp_path / "project_pipelines", user_dir, None, False)

        # The header values come from the USER file — proving the source-dir
        # selection followed the discovered entry's source, not project_dir.
        assert card.name == "User Deploy"
        assert card.description == "User-level deploy pipeline"
        assert [stage.id for stage in card.stages] == ["build"]
        assert user_path.exists()

    def test_describe_pipeline_applies_explicit_workflow(self, tmp_path: Path, isolated_cwd: Path) -> None:
        """An explicit workflow name resolves that file — skip removes test, extend adds audit."""
        project_dir = tmp_path / "project_pipelines"
        _write_pipeline(project_dir, "deploy", _DEPLOY_YML)
        _write_workflow(isolated_cwd, "hardening", _HARDENING_YML)

        card = describe_pipeline("deploy", project_dir, tmp_path / "user_pipelines", "hardening", False)

        # ``skip`` inside the workflow is a compiler directive — it applies to
        # the card exactly as it applies to the run.
        assert [stage.id for stage in card.stages] == ["build", "audit"]

    def test_describe_pipeline_composition_equals_run_composition(self, tmp_path: Path, isolated_cwd: Path) -> None:
        """The card's stage composition equals an independently compiled run's — AC-3.

        The loop workflow (``stages.build.loop: 2``) makes the case nontrivial:
        the compiler expands build into ``build-1``/``build-2``, and the card
        must report each copy as a separate row, in the same order the run
        would execute them.
        """
        project_dir = tmp_path / "project_pipelines"
        pipeline_path = _write_pipeline(project_dir, "deploy", _DEPLOY_YML)
        workflow_path = _write_workflow(isolated_cwd, "looped", _LOOP_YML)

        card = describe_pipeline("deploy", project_dir, tmp_path / "user_pipelines", "looped", False)

        _, flow_doc = compile_flow(
            pipeline_path,
            tmp_path / "run_flow.yml",
            workflow=parse_workflow(workflow_path),
        )

        # ``CardStage.title`` mirrors ``FlowStage.name`` (the compiled display name).
        assert [(stage.id, stage.title) for stage in card.stages] == [
            (stage.id, stage.name) for stage in order_stages(flow_doc.stages)
        ]
        assert [stage.id for stage in card.stages] == ["build-1", "build-2", "test"]

    def test_describe_pipeline_no_workflow_reports_raw_composition(self, tmp_path: Path, isolated_cwd: Path) -> None:
        """``no_workflow=True`` suppresses even a basename auto-match that would apply."""
        project_dir = tmp_path / "project_pipelines"
        _write_pipeline(project_dir, "deploy", _DEPLOY_YML)
        # The basename auto-match (deploy.yml) exists — no_workflow must win.
        _write_workflow(isolated_cwd, "deploy", _HARDENING_YML)

        card = describe_pipeline("deploy", project_dir, tmp_path / "user_pipelines", None, True)

        assert [stage.id for stage in card.stages] == ["build", "test"]

    def test_describe_pipeline_unknown_name_raises_readable_error(self, tmp_path: Path) -> None:
        """An unknown pipeline name raises RuntimeError with the readable missing-message."""
        with pytest.raises(RuntimeError, match="pipeline 'ghost' is missing"):
            describe_pipeline("ghost", tmp_path / "project_pipelines", tmp_path / "user_pipelines", None, False)

    def test_describe_pipeline_removes_temp_flow_file(self, tmp_path: Path, isolated_cwd: Path) -> None:
        """The compiled flow-file lands in a throwaway temp dir and is removed after.

        The card's only write is the temp flow-file: it never touches the
        project tree or the user's home, and it does not outlive the call.
        """
        project_dir = tmp_path / "project_pipelines"
        _write_pipeline(project_dir, "deploy", _DEPLOY_YML)

        before = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))

        with mock.patch.object(
            _describe_pipeline_module, "compile_flow", wraps=_describe_pipeline_module.compile_flow
        ) as spy:
            describe_pipeline("deploy", project_dir, tmp_path / "user_pipelines", None, False)

        flow_path = spy.call_args.args[1]
        assert flow_path.name == "flow.yml"
        assert flow_path.parent.name.startswith("goga-pipeline-card-")
        assert not flow_path.exists()
        # The temp dir lives outside both the project tree and the user's home.
        assert not flow_path.is_relative_to(tmp_path)
        assert not flow_path.is_relative_to(Path.home())

        # Read-only towards the project/runtime tree: nothing was added.
        after = sorted(str(p.relative_to(tmp_path)) for p in tmp_path.rglob("*"))
        assert after == before

    def test_describe_pipeline_ignores_skip_env(
        self, tmp_path: Path, isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """``GOGA_SKIP_STAGES`` is a run-only directive — the card ignores it."""
        project_dir = tmp_path / "project_pipelines"
        _write_pipeline(project_dir, "deploy", _DEPLOY_YML)
        monkeypatch.setenv("GOGA_SKIP_STAGES", "build")

        card = describe_pipeline("deploy", project_dir, tmp_path / "user_pipelines", None, False)

        assert [stage.id for stage in card.stages] == ["build", "test"]


class TestDescribePipelineAmendmentLayer:
    """The card composes through the same amendment a run composes through."""

    def test_describe_pipeline_reports_provenance_through_same_layer(
        self,
        tmp_path: Path,
        isolated_cwd: Path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A committed tool contribution lands on the card as provenance.

        The workflow auto-matches (``deploy.yml`` with the authored prompt);
        the tool contributes a prompt-only document over it; the merged
        overlay workflow is what ``compile_flow`` receives. The real compiler
        runs into the temp dir — no mocks beyond the tool environment.
        """
        pin_package_environment({"goga_tool_demo": ["demo-dist"]})

        def register(hooks: object) -> None:
            def hardening(self: object, context: object) -> None:
                context.contribute(WorkflowDocument(prompt="tool-text"))

            hooks.subscribe("pipeline", "amend_workflow", "hardening", hardening)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register)

        project_dir = tmp_path / "project_pipelines"
        _write_pipeline(project_dir, "deploy", _DEPLOY_YML)
        _write_workflow(isolated_cwd, "deploy", _AUTHORED_YML)

        card = describe_pipeline("deploy", project_dir, tmp_path / "user_pipelines", None, False)

        # The platform derives the tool identity from the package name:
        # goga_tool_demo -> demo.
        assert card.provenance == ["demo"]
        assert card.name == "Deploy"

    def test_describe_pipeline_disabled_reports_raw_composition(
        self,
        tmp_path: Path,
        isolated_cwd: Path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A disabled decision delivers nothing — the raw composition, no tool layer.

        The amend hook fails loudly when called, so a clean return proves the
        delivery never ran. The auto-match workflow exists (with a skip that
        would remove ``test`` if it leaked in) — ``no_workflow`` must win over
        it, and the card is the same composition a no-workflow-file compile
        produces.
        """
        pin_package_environment({"goga_tool_demo": ["demo-dist"]})

        def register(hooks: object) -> None:
            def hardening(self: object, context: object) -> None:
                raise AssertionError("amend hook must not run for a disabled decision")

            hooks.subscribe("pipeline", "amend_workflow", "hardening", hardening)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register)

        project_dir = tmp_path / "project_pipelines"
        _write_pipeline(project_dir, "deploy", _DEPLOY_YML)
        _write_workflow(isolated_cwd, "deploy", _AUTHORED_YML)

        card = describe_pipeline("deploy", project_dir, tmp_path / "user_pipelines", None, True)

        assert card.provenance == []
        assert [(stage.id, stage.title) for stage in card.stages] == [
            ("build", "Build"),
            ("test", "Test"),
        ]

    def test_describe_pipeline_committed_contribution_changes_the_composition(
        self,
        tmp_path: Path,
        isolated_cwd: Path,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """A tool contribution that changes the stages is visible in the card.

        A skip directive contributed onto the empty base (a silent-miss
        auto-match) removes ``test`` — falsifiably different from the raw
        two-stage composition, proving the card compiled the merged overlay
        workflow, not the pre-amendment one.
        """
        pin_package_environment({"goga_tool_demo": ["demo-dist"]})

        def register(hooks: object) -> None:
            def hardening(self: object, context: object) -> None:
                context.contribute(WorkflowDocument(stages={"test": WorkflowStage(skip=True)}))

            hooks.subscribe("pipeline", "amend_workflow", "hardening", hardening)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register)

        project_dir = tmp_path / "project_pipelines"
        _write_pipeline(project_dir, "deploy", _DEPLOY_YML)

        card = describe_pipeline("deploy", project_dir, tmp_path / "user_pipelines", None, False)

        assert [stage.id for stage in card.stages] == ["build"]  # test removed by the tool's skip
        assert card.provenance == ["demo"]

    def test_describe_pipeline_delivers_the_run_path_fact_set(
        self,
        tmp_path: Path,
        isolated_cwd: Path,
        monkeypatch: pytest.MonkeyPatch,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The card delivers the same decision and work facts the run form delivers.

        Observed through a recording tool: the decision follows the flags and
        the resolution outcome (explicit hit / auto miss), and the work
        identity follows the branch — the hosting form on a topic branch, the
        literal ``unknown`` branch-only form when git resolves none, and the
        guarded branch-only form on a fully unsluggable branch.
        """
        recorded: dict[str, Any] = {}
        pin_package_environment({"goga_tool_demo": ["demo-dist"]})

        def register(hooks: object) -> None:
            def recorder(self: object, context: object) -> None:
                recorded["facts"] = context

            hooks.subscribe("pipeline", "amend_workflow", "recorder", recorder)  # type: ignore[attr-defined]

        install_tool_package("goga_tool_demo", register_hooks=register)

        project_dir = tmp_path / "project_pipelines"
        _write_pipeline(project_dir, "deploy", _DEPLOY_YML)
        workflows_dir = isolated_cwd / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "ci.yml").write_text("prompt: ci\n")

        topic_dir = isolated_cwd / ".goga" / "history" / current_year() / "feature-demo"
        topic_dir.mkdir(parents=True)

        # Explicit hit on a topic-hosting branch — the hosting work form.
        monkeypatch.setattr(_describe_pipeline_module, "resolve_current_branch_name", lambda: "feature-demo")
        describe_pipeline("deploy", project_dir, tmp_path / "user_pipelines", "ci", False)
        facts = recorded["facts"]
        assert (facts.decision.kind, facts.decision.workflow_name) == ("explicit", "ci")
        assert facts.pipeline.name == "deploy"
        assert facts.pipeline.display_name == "Deploy"
        assert facts.pipeline.source == "project"
        assert facts.work == WorkIdentity(branch="feature-demo", slug="feature-demo", year=current_year())

        # Auto-miss on an unsluggable branch — the guarded branch-only form.
        monkeypatch.setattr(_describe_pipeline_module, "resolve_current_branch_name", lambda: "Ветка")
        describe_pipeline("deploy", project_dir, tmp_path / "user_pipelines", None, False)
        facts = recorded["facts"]
        assert (facts.decision.kind, facts.decision.workflow_name) == ("silent-miss", None)
        assert facts.work == WorkIdentity(branch="Ветка")

        # No branch at all — the literal "unknown" branch-only form.
        monkeypatch.setattr(_describe_pipeline_module, "resolve_current_branch_name", lambda: None)
        describe_pipeline("deploy", project_dir, tmp_path / "user_pipelines", None, False)
        assert recorded["facts"].work == WorkIdentity(branch="unknown")
