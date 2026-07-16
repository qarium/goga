"""Pipeline-cell integration tests for agent-prompt materialization.

These tests cover the cross-entity composition inside the pipeline cell that the
mocked unit tests in ``test_run_pipeline.py`` do not by themselves exercise as a
single flow:

``compile_flow`` (mocked to emit a documents tuple) → ``run_pipeline`` (real)
unpacks the tuple, runs the validate-first materialization of the four agent
prompt files into ``<AFM_DIR>/prompts/`` (real filesystem I/O), then calls
``run_flow`` (mocked) with the compiled flow path.

The integration surface is ``run_pipeline`` driving step 6.5 against real
``_resolve_defaults_dir`` output (monkeypatched to a tmp dir for determinism)
while ``compile_flow`` and ``run_flow`` are patched at the module so the
documents tuple and the afm invocation are controlled. The three scenarios
mirror the design document's Data Flows:

- **A** (no ``agents`` block): the documents tuple carries ``agents=None``;
  exactly four prompt files land in ``<AFM_DIR>/prompts/`` and their contents
  match the package defaults; ``run_flow`` is still called once with the flow
  path.
- **B** (partial override — ``agents.planning`` only): ``prompts/planning.md``
  carries the inline override; the other three are copied from defaults;
  ``run_flow`` still fires once.
- **C** (missing default + no override — atomicity): a defaults dir with only
  three files plus a pre-existing sentinel/stale prompts dir; ``run_pipeline``
  raises ``RuntimeError`` naming the missing key BEFORE wiping the prompts dir,
  so the sentinel and stale file survive and no fresh file is written;
  ``run_flow`` is never called.

``_isolate_home`` (autouse in ``conftest.py``) is left intact per the plan's
debugging notes — it must not be removed.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest
from goga.pipeline import run_pipeline
from goga.pipeline.compiler import (
    BodyFormat,
    FlowDocument,
    PhasesBody,
    PipelineAgents,
    PipelineDocument,
    PipelineHeader,
)

# goga.pipeline.run_pipeline is shadowed in the package __init__ by the
# run_pipeline function, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules and patch its
# compile_flow / run_flow / _resolve_defaults_dir attributes directly. Per
# [[feedback_mock_patch_module_shadowing]].
_run_pipeline_module = sys.modules["goga.pipeline.run_pipeline"]

# The four fixed agent-prompt keys; mirrors run_pipeline._AGENT_KEYS.
_AGENT_KEYS = ("planning", "implementation", "review", "summary")


@pytest.fixture
def afm_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point AFM_DIR at a tmp dir and return the resolved path.

    flow_path inside run_pipeline is ``afm_dir / "flow.yml"``. Returning the
    resolved value lets assertions compare against exactly what run_pipeline
    builds (it resolves AFM_DIR internally). The directory itself is not
    created here — compile_flow is mocked, so its parent-must-exist
    precondition never fires.
    """
    directory = (tmp_path / ".afm").resolve()
    monkeypatch.setenv("AFM_DIR", str(directory))
    return directory


def _write_pipeline(directory: Path, name: str = "deploy") -> None:
    """Create an empty pipeline file so name resolution matches it."""
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"{name}.yml").write_text("pipeline")


def _write_defaults(
    defaults_dir: Path, keys: tuple[str, ...] = _AGENT_KEYS
) -> None:
    """Write ``default <key>\\n`` prompt files for the given keys into defaults_dir."""
    defaults_dir.mkdir(parents=True, exist_ok=True)
    for key in keys:
        (defaults_dir / f"{key}.md").write_text(f"default {key}\n")


def _documents(agents: PipelineAgents | None = None) -> tuple[PipelineDocument, FlowDocument]:
    """Build the documents tuple ``compile_flow`` returns, for mock wiring.

    ``agents`` defaults to None (no header block). The header/body match the
    shape run_pipeline expects when it unpacks the tuple.
    """
    pipeline_doc = PipelineDocument(
        header=PipelineHeader(name="deploy", description="d", agents=agents),
        format=BodyFormat.PHASES,
        body=PhasesBody(steps=[]),
    )
    flow_doc = FlowDocument(name="deploy", description="d", stages=[])
    return (pipeline_doc, flow_doc)


def _patch_defaults(monkeypatch: pytest.MonkeyPatch, defaults_dir: Path) -> None:
    """Redirect run_pipeline's default-prompt resolver at a tmp defaults dir."""
    monkeypatch.setattr(_run_pipeline_module, "_resolve_defaults_dir", lambda: defaults_dir)


class _MaterializationHarness:
    """Shared wiring helpers for the three integration scenarios.

    Each scenario writes an empty pipeline file (so name resolution matches),
    redirects ``_resolve_defaults_dir`` at a controlled defaults dir, and patches
    ``compile_flow`` + ``run_flow`` at the module so the documents tuple and the
    afm invocation are controlled while the materialization I/O is real.
    """

    def _setup(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        defaults_keys: tuple[str, ...] = _AGENT_KEYS,
        agents: PipelineAgents | None = None,
    ) -> tuple[Path, Path, Path]:
        defaults_dir = tmp_path / "defaults"
        _write_defaults(defaults_dir, keys=defaults_keys)
        _patch_defaults(monkeypatch, defaults_dir)

        project_dir = tmp_path / "pipelines"
        _write_pipeline(project_dir)

        user_dir = tmp_path / "user"
        return project_dir, user_dir, defaults_dir


class TestIntegrationMaterializationScenarioA(_MaterializationHarness):
    """Scenario A — a documents tuple with ``agents=None``."""

    def test_no_agents_materializes_four_defaults_and_invokes_run_flow(
        self,
        tmp_path: Path,
        afm_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """agents=None → exactly four default files copied; run_flow still fires once.

        The composition: ``compile_flow`` (mocked) emits a documents tuple with
        ``header.agents is None``; ``run_pipeline`` (real) unpacks it and copies all
        four package defaults into ``<AFM_DIR>/prompts/``; ``run_flow`` (mocked) is
        then called exactly once with the flow path and the port.
        """
        project_dir, user_dir, defaults_dir = self._setup(tmp_path, monkeypatch)

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0) as mock_run_flow,
        ):
            exit_code = run_pipeline("deploy", project_dir, user_dir, 50321)

        assert exit_code == 0
        prompts_dir = afm_dir / "prompts"

        # Exactly four files, one per fixed agent key — no extras, no leftovers.
        assert sorted(p.name for p in prompts_dir.iterdir()) == [
            "implementation.md",
            "planning.md",
            "review.md",
            "summary.md",
        ]

        # Each materialized file matches the package default byte-for-byte.
        for key in _AGENT_KEYS:
            assert (prompts_dir / f"{key}.md").read_text() == (defaults_dir / f"{key}.md").read_text()

        # The composition still drives afm: run_flow is called once with the
        # compiled flow path (not the DSL path) and the caller-allocated port.
        mock_run_flow.assert_called_once_with(afm_dir / "flow.yml", 50321)


class TestIntegrationMaterializationScenarioB(_MaterializationHarness):
    """Scenario B — a partial override (``agents.planning`` only)."""

    def test_partial_override_replaces_planning_and_copies_the_rest(
        self,
        tmp_path: Path,
        afm_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """agents.planning set → planning.md carries the override; others are defaults.

        The inline override on one key flows from ``compile_flow``'s documents
        tuple through ``run_pipeline`` step 6.5 to ``prompts/planning.md``; the
        three unspecified keys fall back to their package defaults. ``run_flow``
        still fires once.
        """
        override = "OVERRIDE\n"
        agents = PipelineAgents(planning=override)
        project_dir, user_dir, defaults_dir = self._setup(tmp_path, monkeypatch, agents=agents)

        with (
            mock.patch.object(
                _run_pipeline_module,
                "compile_flow",
                return_value=_documents(agents),
            ),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0) as mock_run_flow,
        ):
            exit_code = run_pipeline("deploy", project_dir, user_dir, 50321)

        assert exit_code == 0
        prompts_dir = afm_dir / "prompts"

        # The override replaces the planning file wholesale.
        assert (prompts_dir / "planning.md").read_text() == override

        # The three unspecified keys use their package defaults.
        for key in ("implementation", "review", "summary"):
            assert (prompts_dir / f"{key}.md").read_text() == (defaults_dir / f"{key}.md").read_text()

        # Still exactly four files; afm still invoked once with the flow path.
        assert sorted(p.name for p in prompts_dir.iterdir()) == [
            "implementation.md",
            "planning.md",
            "review.md",
            "summary.md",
        ]
        mock_run_flow.assert_called_once_with(afm_dir / "flow.yml", 50321)


class TestIntegrationMaterializationScenarioC(_MaterializationHarness):
    """Scenario C — a missing default with no override (validate-first atomicity)."""

    def test_missing_default_with_no_override_raises_before_wipe(
        self,
        tmp_path: Path,
        afm_dir: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Missing default + no override raises before wipe; prompts dir left untouched.

        The defaults dir carries only three files (no ``implementation.md``). A
        pre-existing prompts dir from a past run holds a sentinel and a stale
        planning file. ``run_pipeline`` step 6.5b validate-first must raise
        ``RuntimeError`` naming the missing key BEFORE the wipe in 6.5c — so the
        sentinel and stale file survive, no fresh file is written, and
        ``run_flow`` is never called.
        """
        # Defaults dir with the implementation default removed.
        project_dir, user_dir, _defaults_dir = self._setup(
            tmp_path, monkeypatch, defaults_keys=("planning", "review", "summary")
        )

        # Atomicity sentinel: a pre-existing prompts dir from a past run.
        prompts_dir = afm_dir / "prompts"
        prompts_dir.mkdir(parents=True, exist_ok=True)
        (prompts_dir / "sentinel.md").write_text("PRE-EXISTING\n")
        (prompts_dir / "planning.md").write_text("STALE\n")

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", return_value=_documents()),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0) as mock_run_flow,
            pytest.raises(RuntimeError, match="implementation: default prompt missing"),
        ):
            run_pipeline("deploy", project_dir, user_dir, 50321)

        # afm is never launched when materialization cannot proceed.
        mock_run_flow.assert_not_called()

        # The wipe (6.5c) never ran: the sentinel and the stale file survive.
        assert (prompts_dir / "sentinel.md").read_text() == "PRE-EXISTING\n"
        assert (prompts_dir / "planning.md").read_text() == "STALE\n"

        # No fresh default file was written before the raise — atomicity holds.
        assert not (prompts_dir / "implementation.md").exists()
        assert not (prompts_dir / "review.md").exists()
        assert not (prompts_dir / "summary.md").exists()
