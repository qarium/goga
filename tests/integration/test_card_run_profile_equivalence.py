"""Card ↔ run equivalence under the profile channels — the "same flags, same composition" guarantee extended.

The card (``describe_pipeline``) and the run (``run_pipeline``) compose
through the SAME machine — ``resolve_workflow`` → ``apply_skip_stages`` →
hooks → ``compile_flow`` — and the profile activation channels (the
``profile`` parameter, the ambient ``GOGA_PROFILE``, the decoded
``GOGA_HOME_PROFILES`` bundle) feed both paths identically, so the same flags
must yield the identical stage composition. D3 makes the equivalence
STRUCTURAL: the card never applies the per-stage env wrappers (no wrapper
generation exists on the card path), so an env-declaring stage appears in the
card exactly as it composes in the run — same id, same title, same position —
while only the run's flow-file carries the wrapper command rewrite.

The fixture makes the case nontrivial on every axis: the profile content
renders into an extend stage's title (a composition value the profile
channels must reach on BOTH sides), the workflow declares per-stage env on
the middle of a chained trio (the delivery machinery the run engages and the
card must mirror structurally), and the extend entry appends a fourth stage
(a workflow-driven composition change). The templates use top-level context
keys so the no-activation counterpart renders the standard ``Undefined``
empty string instead of raising on nested access to a missing key.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, cast
from unittest import mock

import pytest
from goga.docker import encode_home_profiles
from goga.pipeline import describe_pipeline, run_pipeline, stage_env_wrappers
from goga.pipeline.compiler import FlowDocument
from goga.pipeline.order_stages import order_stages

# goga.pipeline.run_pipeline is shadowed in the package __init__ by the
# run_pipeline function, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules and patch its
# compile_flow / run_flow attributes directly. Per
# [[feedback_mock_patch_module_shadowing]].
_run_pipeline_module = sys.modules["goga.pipeline.run_pipeline"]

# Three chained STAGES (s1 → s2 → s3) plus the workflow-appended audit: the
# env claim on the middle stage and the extend entry bend the composition
# away from the raw DSL on both axes under test.
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

# The workflow "w": the middle stage declares per-stage env with its own
# agent (the delivery the run engages, the card mirrors structurally — D3)
# and the extend entry's title renders from the profile content (the
# composition value the profile channels must reach on both sides).
_W_YML = """\
stages:
  s2:
    agent: codex
    env:
      MODEL: '{{ model }}'
extend:
  audit:
    after: [s3]
    title: 'Audit {{ team }}'
"""

_BUNDLE: dict[str, dict[str, Any]] = {"mixa": {"model": "sonnet", "team": "core"}}


def _write_project(tmp_path: Path) -> tuple[Path, Path]:
    """Materialize the project layout: pipeline, workflow, and the afm runtime dir.

    Args:
        tmp_path: Project root used as the working directory for the test
            (workflow resolution is CWD-based — ``<cwd>/.goga/workflows``).

    Returns:
        The ``(project_dir, user_dir)`` pair both routines receive.
    """
    project_dir = tmp_path / ".goga" / "pipelines"
    project_dir.mkdir(parents=True)
    (project_dir / "deploy.yml").write_text(_DEPLOY_YML)

    workflows_dir = tmp_path / ".goga" / "workflows"
    workflows_dir.mkdir(parents=True)
    (workflows_dir / "w.yml").write_text(_W_YML)

    user_dir = tmp_path / "user_pipelines"
    user_dir.mkdir(parents=True)

    (tmp_path / ".afm").mkdir(parents=True)
    return project_dir, user_dir


def _run_composition(project_dir: Path, user_dir: Path, *, profile: str | None) -> tuple[list[str], str]:
    """Run the run side for real (only ``run_flow`` mocked) and capture its composition.

    The caller owns the environment setup (chdir, ``AFM_DIR``, the relocated
    wrapper base, the profile channels) so the card and the run of one
    scenario read exactly the same environment.

    Args:
        project_dir: The project pipelines directory.
        user_dir: The user pipelines directory.
        profile: The CLI activation channel value forwarded to the run.

    Returns:
        The ordered stage ids (from the compiled ``FlowDocument``) and the
        flow-file text as it stands after the whole run — the wrapper command
        rewrites of the per-stage env delivery included.
    """
    captured: dict[str, object] = {}
    real_compile = _run_pipeline_module.compile_flow

    def _spy(pipeline_path: Path, flow_path: Path, workflow: object = None, **kwargs: object):
        result = real_compile(pipeline_path, flow_path, workflow=workflow, **kwargs)
        captured["flow_doc"] = result[1]
        captured["flow_path"] = flow_path
        return result

    with (
        mock.patch.object(_run_pipeline_module, "compile_flow", side_effect=_spy),
        mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
    ):
        exit_code = run_pipeline("deploy", project_dir, user_dir, 50321, workflow="w", profile=profile)

    assert exit_code == 0

    flow_doc = cast(FlowDocument, captured["flow_doc"])

    return [stage.id for stage in order_stages(flow_doc.stages)], cast(Path, captured["flow_path"]).read_text()


class TestCardRunProfileEquivalence:
    def test_card_and_run_compose_identical_stages_with_profile_channels(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        in_container_pipeline_run_context: Path,
    ) -> None:
        """The same workflow + profile flags compose identically in card and run forms.

        Card side: ``describe_pipeline(..., workflow="w", profile="mixa")``
        with the ambient bundle decoded on both paths. Run side: the real
        resolution/render/compile with only the afm launch mocked. The stage
        id lists must be identical, the profile content must reach the card
        (the rendered extend title), and the env-declaring stage must appear
        in the card exactly as it composes in the run — while only the run's
        flow-file carries the wrapper command rewrite (D3).
        """
        project_dir, user_dir = _write_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("AFM_DIR", str((tmp_path / ".afm").resolve()))

        wrapper_base = tmp_path / "goga-stage-env"
        monkeypatch.setattr(stage_env_wrappers, "_WRAPPER_BASE", wrapper_base)

        # The profile channels: the bundle rides the ambient carriage, the CLI
        # channel rides the parameter, and no ambient profile exists — both
        # paths read exactly these.
        monkeypatch.setenv("GOGA_HOME_PROFILES", encode_home_profiles(_BUNDLE))
        monkeypatch.delenv("GOGA_PROFILE", raising=False)

        # Card side — the full composition machine for real. The card composes
        # BEFORE any run machinery engaged, so the wrapper base absence here
        # also pins that the card path generates nothing on disk (D3).
        card = describe_pipeline("deploy", project_dir, user_dir, workflow="w", no_workflow=False, profile="mixa")
        card_ids = [stage.id for stage in card.stages]

        assert not wrapper_base.exists()

        run_ids, flow_text = _run_composition(project_dir, user_dir, profile="mixa")

        # The equivalence guarantee: identical stage id lists — the
        # env-declaring s2 appears in the card exactly as it composes in the
        # run.
        assert card_ids == run_ids
        assert card_ids == ["s1", "s2", "s3", "audit"]

        # The profile channels reached the card's composition values: the
        # extend title rendered from the bundle content.
        audit = next(stage for stage in card.stages if stage.id == "audit")
        assert audit.title == "Audit core"

        # The run delivered the per-stage env (the machinery the card
        # structurally mirrors without engaging): s2's command in the written
        # flow-file points at its sh closure, which exports the rendered env
        # verbatim.
        assert f"command: {wrapper_base / 's2'}" in flow_text
        assert (wrapper_base / "s2").read_text().splitlines()[1] == "export MODEL=sonnet"

    def test_card_and_run_equivalence_holds_without_activation(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        in_container_pipeline_run_context: Path,
    ) -> None:
        """Without any activation the same equivalence holds — the channels are an overlay, not a fork.

        No bundle, no ambient profile, no ``profile`` parameter: the workflow
        renders with an empty context (the standard ``Undefined`` renders the
        missing top-level keys as empty), and the card and the run still
        compose the identical stage set. The rendered title shows the empty
        context on the card, proving neither path diverged.
        """
        project_dir, user_dir = _write_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("AFM_DIR", str((tmp_path / ".afm").resolve()))

        wrapper_base = tmp_path / "goga-stage-env"
        monkeypatch.setattr(stage_env_wrappers, "_WRAPPER_BASE", wrapper_base)

        monkeypatch.delenv("GOGA_HOME_PROFILES", raising=False)
        monkeypatch.delenv("GOGA_PROFILE", raising=False)

        card = describe_pipeline("deploy", project_dir, user_dir, workflow="w", no_workflow=False, profile=None)
        card_ids = [stage.id for stage in card.stages]

        audit = next(stage for stage in card.stages if stage.id == "audit")
        assert audit.title == "Audit "

        run_ids, flow_text = _run_composition(project_dir, user_dir, profile=None)

        assert card_ids == run_ids
        assert card_ids == ["s1", "s2", "s3", "audit"]

        # The env delivery still engaged on the run side (env is authored, not
        # profile-driven) — the wrapper exports the empty-context render
        # (shell-quoted empty string).
        assert f"command: {wrapper_base / 's2'}" in flow_text
        assert (wrapper_base / "s2").read_text().splitlines()[1] == "export MODEL=''"
