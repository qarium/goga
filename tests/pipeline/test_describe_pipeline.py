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

Fixtures mirror the design's General Setup: ``deploy.yml`` (STAGES format,
build→test) and ``hardening.yml`` (``stages.test.skip: true`` +
``extend.audit``).
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from typing import get_type_hints
from unittest import mock

import pytest
from goga.pipeline.compiler import compile_flow
from goga.pipeline.describe_pipeline import describe_pipeline
from goga.pipeline.order_stages import order_stages
from goga.pipeline.pipeline_card import CardStage, PipelineCard
from goga.pipeline.workflow import parse_workflow

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

# A user-source pipeline-file — distinct header values prove the card was
# composed from the user dir, not an identically named project file.
_USER_DEPLOY_YML = """\
name: User Deploy
description: User-level deploy pipeline
---

build:
  title: Build
"""


@pytest.fixture
def isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """chdir into tmp_path — the workflows root resolves to ``<tmp>/.goga/workflows``."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


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


class TestDescribePipelineLogic:
    def test_describe_pipeline_returns_card_from_header_and_stages(
        self, tmp_path: Path, isolated_cwd: Path
    ) -> None:
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

    def test_describe_pipeline_user_source_composes_from_user_dir(
        self, tmp_path: Path, isolated_cwd: Path
    ) -> None:
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

    def test_describe_pipeline_applies_explicit_workflow(
        self, tmp_path: Path, isolated_cwd: Path
    ) -> None:
        """An explicit workflow name resolves that file — skip removes test, extend adds audit."""
        project_dir = tmp_path / "project_pipelines"
        _write_pipeline(project_dir, "deploy", _DEPLOY_YML)
        _write_workflow(isolated_cwd, "hardening", _HARDENING_YML)

        card = describe_pipeline("deploy", project_dir, tmp_path / "user_pipelines", "hardening", False)

        # ``skip`` inside the workflow is a compiler directive — it applies to
        # the card exactly as it applies to the run.
        assert [stage.id for stage in card.stages] == ["build", "audit"]

    def test_describe_pipeline_composition_equals_run_composition(
        self, tmp_path: Path, isolated_cwd: Path
    ) -> None:
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

    def test_describe_pipeline_no_workflow_reports_raw_composition(
        self, tmp_path: Path, isolated_cwd: Path
    ) -> None:
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

    def test_describe_pipeline_removes_temp_flow_file(
        self, tmp_path: Path, isolated_cwd: Path
    ) -> None:
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
