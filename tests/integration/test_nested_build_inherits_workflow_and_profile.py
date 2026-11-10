"""Cross-cell integration: a nested build inherits the workflow and profile of its hosting run.

The design's headline inheritance scenario (data flows 2, 3, and 6 of the
contributor-profile feature): ``run_pipeline`` composes its afm launch layer
with the EFFECTIVE profile exported (``GOGA_PROFILE=<effective>``) while the
engine keys — ``GOGA_WORKFLOW`` and ``GOGA_HOME_PROFILES`` among them — are
dropped from the layer, so they reach the afm subprocess only through the
ambient container environment a stage inherits. A ``goga build`` invoked
inside that runtime therefore picks BOTH channels up through the environment
alone: the workflow via ambient ``GOGA_WORKFLOW``, the profile via the
exported ``GOGA_PROFILE`` layer entry, the bundle via ambient
``GOGA_HOME_PROFILES`` — and ``resolve_build_workflow`` composes exactly
those into one ``LoadedWorkflow``.

The run side activates its profile through the deepest channel chain — the
workflow ``profile:`` raw-text default, resolved against the decoded home
bundle, rendered into the workflow text — proving the same bundle feeds both
sides. Only the external afm boundary (``run_flow``) is mocked; the compile
runs for real.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from goga.build import resolve_build_workflow
from goga.docker import decode_home_profiles, encode_home_profiles
from goga.pipeline import run_pipeline
from goga.pipeline.workflow import ProfileSource

# goga.pipeline.run_pipeline is shadowed in the package __init__ by the
# run_pipeline function, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules and patch its
# compile_flow / run_flow attributes directly. Per
# [[feedback_mock_patch_module_shadowing]].
_run_pipeline_module = sys.modules["goga.pipeline.run_pipeline"]

# The home bundle both sides share: the "mixa" profile carrying the worker
# facts the workflow templates render (agent on the run side, model on the
# build side).
_BUNDLE: dict[str, dict[str, Any]] = {"mixa": {"worker": {"agent": "codex", "model": "sonnet"}}}

# The run-side workflow (basename auto-match of the pipeline "deploy"): the
# literal ``profile:`` default activates "mixa" — GOGA_PROFILE is absent — and
# the stage agent renders from the profile content.
_RUN_WORKFLOW_YML = "profile: mixa\nstages:\n  build:\n    agent: '{{ worker.agent }}'\n"

# The build-side workflow the ambient GOGA_WORKFLOW names: a build block whose
# env renders from the same profile content — its parsed shape identifies the
# loaded document as "hard"'s beyond the name alone.
_BUILD_WORKFLOW_YML = "build:\n  env:\n    WORKER: '{{ worker.model }}'\n"


def _write_project(tmp_path: Path) -> tuple[Path, Path]:
    """Materialize the project layout: pipeline, both workflows, and the afm runtime dir.

    Args:
        tmp_path: Project root used as the working directory for the test
            (workflow resolution is CWD-based — ``<cwd>/.goga/workflows``).

    Returns:
        The ``(project_dir, user_dir)`` pair the run receives.
    """
    project_dir = tmp_path / ".goga" / "pipelines"
    project_dir.mkdir(parents=True)
    (project_dir / "deploy.yml").write_text("name: Deploy\ndescription: d\n---\n\nbuild:\n  title: Build\n")

    workflows_dir = tmp_path / ".goga" / "workflows"
    workflows_dir.mkdir(parents=True)
    (workflows_dir / "deploy.yml").write_text(_RUN_WORKFLOW_YML)
    (workflows_dir / "hard.yml").write_text(_BUILD_WORKFLOW_YML)

    user_dir = tmp_path / "user_pipelines"
    user_dir.mkdir(parents=True)

    (tmp_path / ".afm").mkdir(parents=True)

    return project_dir, user_dir


class TestNestedBuildInheritsWorkflowAndProfile:
    def test_nested_build_inherits_workflow_and_profile(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        in_container_pipeline_run_context: Path,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        """The launch layer plus the ambient environment carry both channels to a nested build.

        The run activates "mixa" through the workflow ``profile:`` default
        (``GOGA_PROFILE`` absent), exports it as the layer's single entry, and
        drops every goga carriage key from the layer. The environment a nested
        ``goga build`` subprocess would inherit (``{**os.environ, **layer}`` —
        exactly the overlay ``run_flow`` applies) then still carries the
        workflow ("hard"), the profile ("mixa"), and the bundle — and
        ``resolve_build_workflow`` composes them into one loaded workflow.
        """
        project_dir, user_dir = _write_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("AFM_DIR", str((tmp_path / ".afm").resolve()))

        # The ambient container carriage: the workflow the host launcher
        # exported, the encoded bundle, and NO ambient profile — the effective
        # profile must come from the run's own activation.
        monkeypatch.setenv("GOGA_WORKFLOW", "hard")
        monkeypatch.setenv("GOGA_HOME_PROFILES", encode_home_profiles(_BUNDLE))
        monkeypatch.delenv("GOGA_PROFILE", raising=False)
        monkeypatch.delenv("GOGA_EXTRA_ENV", raising=False)

        run_captured: dict[str, Any] = {}
        real_compile = _run_pipeline_module.compile_flow

        def _spy(pipeline_path: Path, flow_path: Path, workflow: object = None, **kwargs: object):
            result = real_compile(pipeline_path, flow_path, workflow=workflow, **kwargs)
            run_captured["flow_doc"] = result[1]
            return result

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", side_effect=_spy),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0) as mock_run_flow,
        ):
            exit_code = run_pipeline("deploy", project_dir, user_dir, 50321)

        assert exit_code == 0

        # The run activated the default profile and rendered the workflow with
        # it: the compiled stage command is the rendered agent's wrapper.
        assert 'Pipeline running with workflow "deploy" and profile "mixa"' in capsys.readouterr().out
        compiled = run_captured["flow_doc"].stages[0]
        assert compiled.fields["command"] == "/home/goga/bin/codex-as-claude.sh"

        # The launch layer: exactly the effective profile — the engine keys
        # (GOGA_WORKFLOW, GOGA_HOME_PROFILES, ...) never enter the layer.
        launch_layer = mock_run_flow.call_args.kwargs["env"]
        assert launch_layer == {"GOGA_PROFILE": "mixa"}

        # The environment a nested goga build inherits — the overlay run_flow
        # applies over the ambient process environment. The workflow and the
        # bundle ride the ambient half; the profile rides the layer half.
        effective = {**os.environ, **launch_layer}
        assert effective["GOGA_WORKFLOW"] == "hard"
        assert effective["GOGA_PROFILE"] == "mixa"

        loaded = resolve_build_workflow(
            None,
            effective.get("GOGA_WORKFLOW"),
            None,
            effective.get("GOGA_PROFILE"),
            decode_home_profiles(effective["GOGA_HOME_PROFILES"]),
        )

        # The build side picked both channels up through the environment
        # alone: the "hard" workflow loaded with the "mixa" profile rendered
        # into its build block.
        assert loaded is not None
        assert loaded.profile is not None
        assert loaded.profile.name == "mixa"
        assert loaded.profile.source is ProfileSource.HOME
        assert loaded.document.build is not None
        assert loaded.document.build.env == {"WORKER": "sonnet"}
