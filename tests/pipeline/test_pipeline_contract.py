"""Facade contract tests for the ``goga.pipeline`` package.

The pipeline cell's CODEMANIFEST declares twenty-one facade names: the six
pre-existing entities/routines (``PipelineEntry``, ``PipelineSource``,
``apply_skip_stages``, ``list_pipelines``, ``pipeline_cli``,
``run_pipeline``), the seven informational-surface names built by the
``pipeline-info`` plan (``CardStage``, ``PipelineCard``,
``PipelineSummary``, ``describe_pipeline``, ``describe_pipelines``,
``order_stages``, ``resolve_workflow``), the in-container afm
configuration authorship routine (``write_afm_config``) added by the
``fix-pipeline-context`` topic, the per-stage env delivery routine
(``apply_stage_env_wrappers``) added by the ``contributor-profile`` plan,
the per-step gate env delivery routine (``apply_gate_env_wrappers``) added
by the ``gates-env`` follow-up, and the four afm lifecycle-hook bridge routines (``build_run_event``,
``build_stage_event``, ``map_event_action``, ``run_hook``) added by the
``support-afm-hooks`` topic. The two platform-carrying re-exports
(``describe_pipeline``, ``run_pipeline``) resolve lazily (PEP 562), so a
hook process never pays their import cost on the fast path. Per the
language rule recorded in the plan's Re-exports section, only identifiers
listed in ``__all__`` constitute the facade — a name importable by
accident but absent from ``__all__`` is not part of the contract surface.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import goga.pipeline as pipeline_facade

NEW_FACADE_NAMES = (
    "PipelineSummary",
    "PipelineCard",
    "CardStage",
    "describe_pipelines",
    "resolve_workflow",
    "order_stages",
    "describe_pipeline",
)

BRIDGE_FACADE_NAMES = (
    "build_run_event",
    "build_stage_event",
    "map_event_action",
    "run_hook",
)


def _run_child(code: str) -> subprocess.CompletedProcess[str]:
    """Run one laziness probe in a fresh interpreter against the repository tree.

    Args:
        code: The Python source the child executes.

    Returns:
        The completed child process — stdout carries the probe's verdict.
    """
    repo_root = Path(__file__).resolve().parents[2]

    return subprocess.run(
        [sys.executable, "-c", code],
        check=False,
        capture_output=True,
        text=True,
        timeout=60,
        env={**os.environ, "PYTHONPATH": str(repo_root)},
    )


class TestPipelineFacade:
    def test_facade_exports_new_names(self) -> None:
        """Every informational-surface name is defined on the package and in __all__."""
        for name in NEW_FACADE_NAMES:
            assert hasattr(pipeline_facade, name), f"{name} is not defined on goga.pipeline"
            assert name in pipeline_facade.__all__, f"{name} is missing from goga.pipeline.__all__"

    def test_facade_all_is_alphabetical(self) -> None:
        """__all__ keeps the alphabetical ordering convention (uppercase first)."""
        assert pipeline_facade.__all__ == sorted(pipeline_facade.__all__)

    def test_facade_all_has_twenty_one_names(self) -> None:
        """Fifteen pre-bridge names, the four bridge routines, the afm skin materializer, the gate env delivery."""
        assert len(pipeline_facade.__all__) == 21
        for name in BRIDGE_FACADE_NAMES:
            assert name in pipeline_facade.__all__
        assert "write_afm_config" in pipeline_facade.__all__
        assert "apply_stage_env_wrappers" in pipeline_facade.__all__
        assert "apply_gate_env_wrappers" in pipeline_facade.__all__
        assert "materialize_afm_skin" in pipeline_facade.__all__

    def test_facade_preserves_pre_existing_names(self) -> None:
        """The six names exported before the pipeline-info work stay exported."""
        for name in (
            "PipelineEntry",
            "PipelineSource",
            "apply_skip_stages",
            "list_pipelines",
            "pipeline_cli",
            "run_pipeline",
        ):
            assert name in pipeline_facade.__all__
            assert hasattr(pipeline_facade, name)

    def test_zone_and_cell_facades_export_the_new_names(self) -> None:
        """The zone carries the four bridged contexts; the cell the four bridge routines; the lazy pairs resolve."""
        import goga as root_facade
        import goga.pipeline.hooks as zone_facade
        from goga import AST, app

        from tests.pipeline.hooks.conftest import ZONE_ALL

        assert sorted(zone_facade.__all__) == ZONE_ALL
        for name in BRIDGE_FACADE_NAMES:
            assert name in pipeline_facade.__all__

        assert len(pipeline_facade.__all__) == 21
        assert callable(pipeline_facade.run_pipeline)
        assert callable(pipeline_facade.describe_pipeline)
        assert root_facade.__all__ == ["AST", "app"]
        assert isinstance(AST, type)
        assert callable(app)

    def test_facade_names_are_the_declared_modules_symbols(self) -> None:
        """The facade re-exports the declaring modules' objects, not copies."""
        facade_describe_pipeline = pipeline_facade.describe_pipeline

        from goga.pipeline.describe_pipeline import describe_pipeline
        from goga.pipeline.describe_pipelines import describe_pipelines
        from goga.pipeline.gate_env_wrappers import apply_gate_env_wrappers
        from goga.pipeline.hook_bridge import build_run_event, build_stage_event, map_event_action, run_hook
        from goga.pipeline.order_stages import order_stages
        from goga.pipeline.pipeline_card import CardStage, PipelineCard
        from goga.pipeline.pipeline_summary import PipelineSummary
        from goga.pipeline.resolve_workflow import resolve_workflow

        assert pipeline_facade.PipelineSummary is PipelineSummary
        assert pipeline_facade.PipelineCard is PipelineCard
        assert pipeline_facade.CardStage is CardStage
        assert pipeline_facade.describe_pipelines is describe_pipelines
        assert pipeline_facade.resolve_workflow is resolve_workflow
        assert pipeline_facade.order_stages is order_stages
        assert facade_describe_pipeline is describe_pipeline
        assert pipeline_facade.describe_pipeline is describe_pipeline
        assert pipeline_facade.run_hook is run_hook
        assert pipeline_facade.map_event_action is map_event_action
        assert pipeline_facade.apply_gate_env_wrappers is apply_gate_env_wrappers
        assert pipeline_facade.build_run_event is build_run_event
        assert pipeline_facade.build_stage_event is build_stage_event


class TestFacadeLaziness:
    """Fresh-interpreter probes of the PEP 562 fast-path discipline.

    The lazy re-exports exist so one hook process per afm event never
    imports the platform; each probe spawns a real child because a warm
    test process has long since bound the attributes under test.
    """

    def test_bare_root_import_loads_no_platform_modules(self) -> None:
        """A bare ``import goga`` leaves the commands tree and the hooks platform unimported."""
        result = _run_child(
            "import sys, goga; print(sorted(m for m in sys.modules if m.startswith(('goga.commands', 'goga.hooks'))))"
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "[]"

    def test_pipeline_import_leaves_the_hooks_zone_unimported(self) -> None:
        """``import goga.pipeline`` loads the cell without the hooks zone or the platform."""
        result = _run_child(
            "import sys, goga.pipeline; "
            "print(sorted(m for m in sys.modules if m.startswith(('goga.hooks', 'goga.pipeline.hooks'))))"
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "[]"

    def test_lazy_reexport_binds_once_and_stays_the_function(self) -> None:
        """Touching the lazy pair binds the callable; later direct imports never shadow it."""
        result = _run_child(
            "import goga.pipeline as p; "
            "first = p.run_pipeline; "
            'bound = "run_pipeline" in vars(p); '
            "second = p.run_pipeline; "
            "from goga.pipeline.run_pipeline import run_pipeline as direct; "
            "print(first is second, bound, p.run_pipeline is direct, callable(p.run_pipeline))"
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "True True True True"

    def test_direct_submodule_import_keeps_the_lazy_pair_the_routines(self) -> None:
        """Importing the lazy submodules first still binds the facade to their routines.

        Each lazy facade name collides with its own submodule name; without the
        package guard the submodule object would land on the facade slot and
        ``from goga.pipeline import run_pipeline`` would return the module.
        """
        result = _run_child(
            "import sys; "
            "import goga.pipeline.describe_pipeline, goga.pipeline.run_pipeline; "
            "from goga.pipeline import describe_pipeline, run_pipeline; "
            "d = sys.modules['goga.pipeline.describe_pipeline']; "
            "r = sys.modules['goga.pipeline.run_pipeline']; "
            "print(callable(describe_pipeline), callable(run_pipeline), "
            "describe_pipeline is d.describe_pipeline, run_pipeline is r.run_pipeline)"
        )

        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == "True True True True"
