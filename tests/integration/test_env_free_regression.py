"""The env-free regression net — unused feature surface leaves the flow output byte-identical.

The contributor-profile delivery machinery is additive by contract: the
per-stage env wrappers engage ONLY when a workflow stage declares ``env``
(``apply_stage_env_wrappers`` then neither reads nor writes the flow-file —
the env-free invariant), and the workflow ``build:`` block never participates
in flow compilation at all (it is the build side's layering input). This
module pins the regression net across compile + wrappers: a workflow carrying
NO per-stage env over a config with no workflow build interplay produces a
flow-file byte-identical BOTH to what the compiler alone wrote (the wrapper
step is a no-op) AND to the no-workflow path (the build-only workflow is
composition-neutral) — the pre-feature behavior stands unchanged when the
feature is not used.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from goga.pipeline import run_pipeline, stage_env_wrappers

# goga.pipeline.run_pipeline is shadowed in the package __init__ by the
# run_pipeline function, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules and patch its
# compile_flow / run_flow attributes directly. Per
# [[feedback_mock_patch_module_shadowing]].
_run_pipeline_module = sys.modules["goga.pipeline.run_pipeline"]

# Three chained STAGES (s1 → s2 → s3) — a nontrivial compiled flow whose
# bytes the regression net compares.
_DEPLOY_YML = """\
name: Chained
description: Three chained stages
---

s1:
  title: S1
s2:
  title: S2
  depends_on:
    - s1
s3:
  title: S3
  depends_on:
    - s2
"""

# The basename auto-match workflow: a build-only document — no stages (so no
# per-stage env anywhere) and a build block the flow compiler never consumes.
# The config of the run context carries no build section, so nothing of the
# workflow reaches the flow composition.
_BUILD_ONLY_YML = "build:\n  agent: codex\n  env:\n    B: '1'\n"


def _write_project(tmp_path: Path) -> tuple[Path, Path]:
    """Materialize the project layout: pipeline, workflow, and the afm runtime dir.

    Args:
        tmp_path: Project root used as the working directory for the test
            (workflow resolution is CWD-based — ``<cwd>/.goga/workflows``).

    Returns:
        The ``(project_dir, user_dir)`` pair the runs receive.
    """
    project_dir = tmp_path / ".goga" / "pipelines"
    project_dir.mkdir(parents=True)
    (project_dir / "deploy.yml").write_text(_DEPLOY_YML)

    workflows_dir = tmp_path / ".goga" / "workflows"
    workflows_dir.mkdir(parents=True)
    (workflows_dir / "deploy.yml").write_text(_BUILD_ONLY_YML)

    user_dir = tmp_path / "user_pipelines"
    user_dir.mkdir(parents=True)

    (tmp_path / ".afm").mkdir(parents=True)

    return project_dir, user_dir


class TestEnvFreeRegression:
    def test_env_free_workflow_produces_byte_identical_flow_output(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        in_container_pipeline_run_context: Path,
    ) -> None:
        """An env-free workflow changes no flow byte — vs the compiler alone and vs no workflow.

        Two runs of the real path (only the afm launch mocked): first the
        basename auto-match resolves the build-only workflow, then the
        disabled decision runs the no-workflow path. The flow-file bytes of
        the three observations must be identical — post-compile and post-run
        of the workflow path (the wrapper step is byte-neutral) and the full
        no-workflow run (the build-only workflow is composition-neutral).
        """
        project_dir, user_dir = _write_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("AFM_DIR", str((tmp_path / ".afm").resolve()))

        wrapper_base = tmp_path / "goga-stage-env"
        monkeypatch.setattr(stage_env_wrappers, "_WRAPPER_BASE", wrapper_base)

        # No activation of any channel — the regression net is the unused
        # feature surface, so no carriage variable may perturb it.
        for key in ("GOGA_PROFILE", "GOGA_WORKFLOW", "GOGA_HOME_PROFILES", "GOGA_EXTRA_ENV"):
            monkeypatch.delenv(key, raising=False)

        captured: dict[str, Any] = {}
        real_compile = _run_pipeline_module.compile_flow

        def _spy(pipeline_path: Path, flow_path: Path, workflow: object = None, **kwargs: object):
            result = real_compile(pipeline_path, flow_path, workflow=workflow, **kwargs)
            captured["post_compile"] = flow_path.read_bytes()
            return result

        # The workflow path — the auto-match resolves the build-only document.
        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", side_effect=_spy),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, user_dir, 50321)

        assert exit_code == 0

        flow_path = (tmp_path / ".afm").resolve() / "flow.yml"
        workflow_run_bytes = flow_path.read_bytes()

        # The wrapper machinery never engaged: no closure directory exists and
        # the run's flow-file is byte-identical to the compiler's own output.
        assert not wrapper_base.exists()
        assert workflow_run_bytes == captured["post_compile"]

        # The no-workflow path — the disabled decision over the same pipeline.
        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", side_effect=_spy),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline("deploy", project_dir, user_dir, 50321, no_workflow=True)

        assert exit_code == 0

        no_workflow_bytes = flow_path.read_bytes()

        # The byte-identity guarantee across the whole net — and the
        # non-triviality guard: the compared bytes carry the real composition.
        assert workflow_run_bytes == no_workflow_bytes
        for stage_id in ("s1", "s2", "s3"):
            assert f"- id: {stage_id}" in workflow_run_bytes.decode()
