"""Contract and logic tests for the ``resolve_workflow`` Routine.

The pipeline cell's CODEMANIFEST declares ``resolve_workflow`` as the single
point of optional-workflow resolution, shared by the run path (``run_pipeline``,
whose input comes from the container environment) and the info-card path
(``describe_pipeline``, whose input comes from CLI flags). The rule set is
parameterized — this module never reads environment variables; the owners of
the flags decide them and pass the decision in:

    no_workflow=True          → None (disabled wins)
    workflow_name not None/"" → that file
    otherwise                 → basename auto-match (pipeline name)
    containment escape        → None (silent miss, never a traversal)
    missing file              → None (silent miss, not an error)
    malformed file            → WorkflowSyntaxError propagates unchanged

Contract tests pin the import surface and the signature. Logic tests cover
each rule with ``monkeypatch.chdir`` controlling the CWD-based workflows root
(``<cwd>/.goga/workflows``).
"""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import get_type_hints

import pytest
from goga.pipeline.resolve_workflow import resolve_workflow
from goga.pipeline.workflow import WorkflowDocument, WorkflowSyntaxError


@pytest.fixture
def isolated_cwd(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """chdir into tmp_path — the workflows root resolves to ``<tmp>/.goga/workflows``."""
    monkeypatch.chdir(tmp_path)
    return tmp_path


def _write_workflow(cwd: Path, name: str, text: str) -> Path:
    """Write a workflow-file at ``<cwd>/.goga/workflows/<name>.yml`` and return it."""
    workflows_dir = cwd / ".goga" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    path = workflows_dir / f"{name}.yml"
    path.write_text(text)
    return path


class TestResolveWorkflowContract:
    def test_resolve_workflow_is_importable_from_module(self) -> None:
        """The routine lives at its declared location ``goga.pipeline.resolve_workflow``."""
        import goga.pipeline.resolve_workflow as module

        assert module.resolve_workflow is resolve_workflow

    def test_resolve_workflow_signature(self) -> None:
        """Signature: (pipeline_name: str, workflow_name: str | None, no_workflow: bool)."""
        signature = inspect.signature(resolve_workflow)
        # The module uses ``from __future__ import annotations``, so raw
        # annotations are strings — resolve them through get_type_hints.
        hints = get_type_hints(resolve_workflow)

        assert list(signature.parameters) == ["pipeline_name", "workflow_name", "no_workflow"]
        assert hints["pipeline_name"] is str
        assert hints["workflow_name"] == str | None
        assert hints["no_workflow"] is bool
        assert hints["return"] == WorkflowDocument | None


class TestResolveWorkflowLogic:
    def test_resolve_workflow_explicit_name_parses_that_file(
        self, isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An explicit workflow_name resolves that file — not the basename auto-match."""
        _write_workflow(
            isolated_cwd,
            "hardening",
            "stages:\n  test:\n    skip: true\nextend:\n  audit:\n    after: [test]\n    title: Audit\n",
        )
        _write_workflow(isolated_cwd, "deploy", "prompt: basename should not win\n")

        result = resolve_workflow("deploy", "hardening", False)

        assert result is not None
        assert result.stages["test"].skip is True
        assert "audit" in result.extend

    def test_resolve_workflow_basename_auto_match(self, isolated_cwd: Path) -> None:
        """No workflow_name → the pipeline basename is auto-matched."""
        _write_workflow(isolated_cwd, "deploy", "prompt: Basename workflow\n")

        result = resolve_workflow("deploy", None, False)

        assert result is not None
        assert result.prompt == "Basename workflow"

    def test_resolve_workflow_empty_name_falls_back_to_basename(self, isolated_cwd: Path) -> None:
        """An empty-string workflow_name means no name — the basename auto-match still applies."""
        _write_workflow(isolated_cwd, "deploy", "prompt: Basename workflow\n")

        result = resolve_workflow("deploy", "", False)

        assert result is not None
        assert result.prompt == "Basename workflow"

    def test_resolve_workflow_disabled_returns_none(self, isolated_cwd: Path) -> None:
        """no_workflow=True wins even when the named file exists."""
        _write_workflow(isolated_cwd, "hardening", "prompt: must be ignored\n")

        result = resolve_workflow("deploy", "hardening", True)

        assert result is None

    def test_resolve_workflow_missing_file_silent_miss(self, isolated_cwd: Path) -> None:
        """A missing workflow-file is a silent miss — None, never an exception."""
        (isolated_cwd / ".goga" / "workflows").mkdir(parents=True)

        result = resolve_workflow("deploy", None, False)

        assert result is None

    def test_resolve_workflow_propagates_syntax_error(self, isolated_cwd: Path) -> None:
        """A structurally malformed file surfaces WorkflowSyntaxError unchanged."""
        _write_workflow(isolated_cwd, "hardening", "stages:\n  test:\n    loop: 0\n")

        with pytest.raises(WorkflowSyntaxError, match=r"loop must be >= 1"):
            resolve_workflow("deploy", "hardening", False)

    def test_resolve_workflow_traversal_name_returns_none(
        self, isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A traversal-carrying name is a containment-guard silent miss; nothing outside is read."""
        from unittest import mock

        import goga.pipeline.resolve_workflow as module

        (isolated_cwd / ".goga" / "workflows").mkdir(parents=True)

        with mock.patch.object(module, "parse_workflow") as mock_parse:
            result = resolve_workflow("deploy", "../../etc/passwd", False)

        assert result is None
        mock_parse.assert_not_called()

    def test_resolve_workflow_reads_no_environment_variables(
        self, isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Env decision variables are ignored — the flags are the only input."""
        _write_workflow(isolated_cwd, "deploy", "prompt: Basename workflow\n")
        monkeypatch.setenv("GOGA_WORKFLOW_DISABLED", "1")
        monkeypatch.setenv("GOGA_WORKFLOW_NAME", "hardening")

        result = resolve_workflow("deploy", None, False)

        assert result is not None
        assert result.prompt == "Basename workflow"
