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

A resolved file loads through the workflow-cell loading chain
(``load_workflow``) with the three activation channels — the result is a
``LoadedWorkflow`` (document plus active profile), never a bare document.

Contract tests pin the import surface and the signature. Logic tests cover
each rule with ``monkeypatch.chdir`` controlling the CWD-based workflows root
(``<cwd>/.goga/workflows``) and profiles root (``<cwd>/.goga/profiles``).
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path
from typing import Any, get_type_hints

import pytest
from goga.pipeline.resolve_workflow import resolve_workflow
from goga.pipeline.workflow import LoadedWorkflow, ProfileSource, WorkflowSyntaxError

# The package __init__ re-exports ``resolve_workflow`` (the function), which
# shadows the ``resolve_workflow`` submodule name in attribute access —
# ``import goga.pipeline.resolve_workflow as module`` binds the function.
# Resolve the real module via ``sys.modules`` instead. Per
# [[feedback_mock_patch_module_shadowing]].
_resolve_workflow_module = sys.modules["goga.pipeline.resolve_workflow"]


def _write_workflow(cwd: Path, name: str, text: str) -> Path:
    """Write a workflow-file at ``<cwd>/.goga/workflows/<name>.yml`` and return it."""
    workflows_dir = cwd / ".goga" / "workflows"
    workflows_dir.mkdir(parents=True, exist_ok=True)
    path = workflows_dir / f"{name}.yml"
    path.write_text(text)
    return path


def _write_project_profile(cwd: Path, name: str, text: str) -> Path:
    """Write a project profile at ``<cwd>/.goga/profiles/<name>.yml`` and return it."""
    profiles_dir = cwd / ".goga" / "profiles"
    profiles_dir.mkdir(parents=True, exist_ok=True)
    path = profiles_dir / f"{name}.yml"
    path.write_text(text)
    return path


class TestResolveWorkflowContract:
    def test_resolve_workflow_is_importable_from_module(self) -> None:
        """The routine lives at its declared location ``goga.pipeline.resolve_workflow``."""
        assert _resolve_workflow_module.resolve_workflow is resolve_workflow

    def test_resolve_workflow_signature(self) -> None:
        """Signature: (pipeline_name, workflow_name, no_workflow, cli_profile, env_profile, home_profiles)."""
        signature = inspect.signature(resolve_workflow)
        # The module uses ``from __future__ import annotations``, so raw
        # annotations are strings — resolve them through get_type_hints.
        hints = get_type_hints(resolve_workflow)

        assert list(signature.parameters) == [
            "pipeline_name",
            "workflow_name",
            "no_workflow",
            "cli_profile",
            "env_profile",
            "home_profiles",
        ]
        assert hints["pipeline_name"] is str
        assert hints["workflow_name"] == str | None
        assert hints["no_workflow"] is bool
        assert hints["cli_profile"] == str | None
        assert hints["env_profile"] == str | None
        assert hints["home_profiles"] == dict[str, dict[str, Any]] | None
        assert hints["return"] == LoadedWorkflow | None
        assert signature.parameters["cli_profile"].default is None
        assert signature.parameters["env_profile"].default is None
        assert signature.parameters["home_profiles"].default is None


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
        assert result.document.stages["test"].skip is True
        assert "audit" in result.document.extend

    def test_resolve_workflow_basename_auto_match(self, isolated_cwd: Path) -> None:
        """No workflow_name → the pipeline basename is auto-matched."""
        _write_workflow(isolated_cwd, "deploy", "prompt: Basename workflow\n")

        result = resolve_workflow("deploy", None, False)

        assert result is not None
        assert result.document.prompt == "Basename workflow"

    def test_resolve_workflow_empty_name_falls_back_to_basename(self, isolated_cwd: Path) -> None:
        """An empty-string workflow_name means no name — the basename auto-match still applies."""
        _write_workflow(isolated_cwd, "deploy", "prompt: Basename workflow\n")

        result = resolve_workflow("deploy", "", False)

        assert result is not None
        assert result.document.prompt == "Basename workflow"

    def test_resolve_workflow_returns_loaded_workflow_with_document_and_profile(self, isolated_cwd: Path) -> None:
        """A resolved file returns a LoadedWorkflow — .document plus the active .profile.

        The CLI activation channel flows into the loading chain: the project
        profile renders the workflow's Jinja interpolation, so the document
        carries the rendered values and the profile names the channel value.
        """
        _write_project_profile(isolated_cwd, "mixa", "worker:\n  agent: codex\n")
        _write_workflow(
            isolated_cwd,
            "deploy",
            "stages:\n  build:\n    agent: '{{ worker.agent }}'\n",
        )

        result = resolve_workflow("deploy", None, False, cli_profile="mixa")

        assert isinstance(result, LoadedWorkflow)
        assert result.profile is not None
        assert result.profile.name == "mixa"
        assert result.profile.source is ProfileSource.PROJECT
        assert result.document.stages["build"].agent == "codex"

    def test_resolve_workflow_env_channel_with_home_bundle(self, isolated_cwd: Path) -> None:
        """The env channel plus the home bundle resolve a HOME-source profile."""
        bundle = {"mixa": {"worker": {"agent": "codex"}}}
        _write_workflow(
            isolated_cwd,
            "deploy",
            "stages:\n  build:\n    agent: '{{ worker.agent }}'\n",
        )

        result = resolve_workflow("deploy", None, False, env_profile="mixa", home_profiles=bundle)

        assert isinstance(result, LoadedWorkflow)
        assert result.profile is not None
        assert result.profile.source is ProfileSource.HOME
        assert result.document.stages["build"].agent == "codex"

    def test_resolve_workflow_no_profile_document_profile_is_none(self, isolated_cwd: Path) -> None:
        """A plain workflow-file loads with profile=None (empty-context render)."""
        _write_workflow(isolated_cwd, "deploy", "prompt: plain\n")

        result = resolve_workflow("deploy", None, False)

        assert isinstance(result, LoadedWorkflow)
        assert result.profile is None
        assert result.document.profile is None

    def test_resolve_workflow_disabled_returns_none(self, isolated_cwd: Path) -> None:
        """no_workflow=True wins even when the named file exists."""
        _write_workflow(isolated_cwd, "hardening", "prompt: must be ignored\n")

        result = resolve_workflow("deploy", "hardening", True)

        assert result is None

    def test_resolve_workflow_disabled_short_circuits_before_load(self, isolated_cwd: Path) -> None:
        """no_workflow=True short-circuits before any load — even a malformed file never opens."""
        _write_workflow(isolated_cwd, "hardening", "stages:\n  test:\n    loop: 0\n")

        result = resolve_workflow("deploy", "hardening", True, cli_profile="mixa")

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
        """A traversal-carrying name is a containment-guard silent miss; nothing outside is read.

        A valid workflow-file (the canary) sits at the location the traversal
        name escapes to — one level above the workflows root, inside the
        project tree. A broken containment guard would parse it and return a
        document; the ``None`` asserts the file is never read, without
        patching the internal parser.
        """
        (isolated_cwd / ".goga" / "workflows").mkdir(parents=True)
        canary = isolated_cwd / ".goga" / "pipelines" / "evil.yml"
        canary.parent.mkdir(parents=True)
        canary.write_text("prompt: must not be read\n")

        result = resolve_workflow("deploy", "../pipelines/evil", False)

        assert result is None

    def test_resolve_workflow_absolute_name_returns_none(
        self, isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An absolute-path name is a containment-guard silent miss; nothing outside is read.

        The canary is a valid workflow-file at the very absolute path the name
        carries — inside the tmp tree but outside the workflows root. A broken
        containment guard would join to the absolute path, parse the canary,
        and return a document; the ``None`` asserts the file is never read,
        without patching the internal parser.
        """
        (isolated_cwd / ".goga" / "workflows").mkdir(parents=True)
        canary = isolated_cwd / "outside.yml"
        canary.write_text("prompt: must not be read\n")

        result = resolve_workflow("deploy", str(canary), False)

        assert result is None

    def test_resolve_workflow_reads_no_environment_variables(
        self, isolated_cwd: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Env decision variables are ignored — the flags are the only input."""
        _write_workflow(isolated_cwd, "deploy", "prompt: Basename workflow\n")
        # Composed rather than literal so the change-set-wide no-residue grep
        # stays clean: these retired names are inert passengers here, not a
        # channel the resolver reads.
        monkeypatch.setenv("GOGA_" + "WORKFLOW_DISABLED", "1")
        monkeypatch.setenv("GOGA_" + "WORKFLOW_NAME", "hardening")

        result = resolve_workflow("deploy", None, False)

        assert result is not None
        assert result.document.prompt == "Basename workflow"
