"""Card ↔ run skip equivalence — the contract's "same flags, same composition".

The ``goga/pipeline`` CODEMANIFEST guarantees the card and the run compose
through the SAME machine: ``resolve_workflow`` → ``apply_skip_stages`` →
hooks → ``compile_flow``. The ``workflow`` decision and the ``skip`` names
arrive as explicit parameters on both paths (never from the environment), so
``describe_pipeline(..., workflow="w", skip=["s2"])`` and a
``run_pipeline(..., workflow="w", skip=["s2"])`` compile must yield the
identical stage composition — what the card shows is what the run executes.

The fixture makes the case nontrivial on both axes: the workflow ``w``
extends the chain with an ``audit`` stage (a workflow-driven composition
change) while ``skip=["s2"]`` removes the MIDDLE of three chained stages
(the compiler must reconnect ``s3`` onto ``s1``). A composition that merely
echoed the raw DSL would fail the bent-composition guard below, so the
equivalence assertion cannot hold trivially.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any
from unittest import mock

import pytest
from goga.pipeline import describe_pipeline, run_pipeline
from goga.pipeline.order_stages import order_stages

# goga.pipeline.run_pipeline is shadowed in the package __init__ by the
# run_pipeline function, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules and patch its
# run_flow / compile_flow attributes directly. Per
# [[feedback_mock_patch_module_shadowing]].
_run_pipeline_module = sys.modules["goga.pipeline.run_pipeline"]

# Three chained STAGES (s1 → s2 → s3): skipping the MIDDLE stage proves the
# compiler reconnects s3 onto s1 — observable identically in both forms.
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

# The workflow "w": an extend stage appended after s3 — a workflow-driven
# composition change the skip merge composes ON TOP OF (in memory, never by
# rewriting this file).
_W_YML = "extend:\n  audit:\n    after: [s3]\n    title: Audit\n"


def _write_project(tmp_path: Path) -> tuple[Path, Path]:
    """Materialize the project layout: pipeline, workflow, and afm runtime dir.

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

    # The run side compiles into <AFM_DIR>/flow.yml — the directory must exist
    # for the real compiler to write its output.
    afm_dir = tmp_path / ".afm"
    afm_dir.mkdir(parents=True)
    return project_dir, user_dir


class TestCardRunSkipEquivalence:
    def test_card_and_run_skip_equivalence(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The same workflow + skip flags compose identically in card and run forms.

        Card side: ``describe_pipeline("deploy", ..., workflow="w",
        skip=["s2"])`` — the ordered stage rows of the returned card. Run
        side: ``run_pipeline("deploy", ..., workflow="w", skip=["s2"])`` with
        only the external afm boundary (``run_flow``) mocked — the ordered
        stages of the ``compile_flow`` output the run actually executes. Both
        compose through ``resolve_workflow`` → ``apply_skip_stages`` → hooks
        → ``compile_flow``, and the two stage id lists must be identical.
        """
        project_dir, user_dir = _write_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("AFM_DIR", str((tmp_path / ".afm").resolve()))

        # Card side — the full composition machine for real.
        card = describe_pipeline(
            "deploy", project_dir, user_dir, workflow="w", no_workflow=False, skip=["s2"]
        )
        card_ids = [stage.id for stage in card.stages]

        # Run side — the real resolution/merge/compile; only the afm launch is
        # mocked. The spy wraps the real compiler to capture its FlowDocument.
        run_captured: dict[str, Any] = {}
        real_compile = _run_pipeline_module.compile_flow

        def _spy(pipeline_path: Path, flow_path: Path, workflow: object = None, **kwargs: object):
            result = real_compile(pipeline_path, flow_path, workflow=workflow, **kwargs)
            run_captured["flow_doc"] = result[1]
            return result

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", side_effect=_spy),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline(
                "deploy", project_dir, user_dir, 50321, workflow="w", skip=["s2"]
            )

        assert exit_code == 0
        run_ids = [stage.id for stage in order_stages(run_captured["flow_doc"].stages)]

        # The equivalence guarantee: identical stage id lists.
        assert card_ids == run_ids
        # The composition genuinely bent away from the raw DSL on BOTH axes
        # (the s2 skip reconnected s3 onto s1; the w workflow appended audit)
        # — otherwise the equivalence above would hold trivially.
        assert card_ids == ["s1", "s3", "audit"]

    def test_card_and_run_skip_equivalence_under_no_workflow(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The same guarantee holds under a disabled decision — skips still compose in both forms.

        ``no_workflow=True`` disables the workflow resolution and the
        amendment delivery, but the skip names still merge (a skip-only
        synthesis over the ``None`` resolution). The existing workflow ``w``
        proves the negative on both axes: its ``audit`` extend must not
        appear (the decision is disabled), and the ``s2`` skip must still
        remove the middle stage and reconnect ``s3`` onto ``s1`` —
        identically in the card and the run.
        """
        project_dir, user_dir = _write_project(tmp_path)
        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("AFM_DIR", str((tmp_path / ".afm").resolve()))

        card = describe_pipeline(
            "deploy", project_dir, user_dir, workflow=None, no_workflow=True, skip=["s2"]
        )
        card_ids = [stage.id for stage in card.stages]

        run_captured: dict[str, Any] = {}
        real_compile = _run_pipeline_module.compile_flow

        def _spy(pipeline_path: Path, flow_path: Path, workflow: object = None, **kwargs: object):
            result = real_compile(pipeline_path, flow_path, workflow=workflow, **kwargs)
            run_captured["flow_doc"] = result[1]
            return result

        with (
            mock.patch.object(_run_pipeline_module, "compile_flow", side_effect=_spy),
            mock.patch.object(_run_pipeline_module, "run_flow", return_value=0),
        ):
            exit_code = run_pipeline(
                "deploy", project_dir, user_dir, 50321, no_workflow=True, skip=["s2"]
            )

        assert exit_code == 0
        run_ids = [stage.id for stage in order_stages(run_captured["flow_doc"].stages)]

        # The equivalence guarantee holds under the disabled decision too.
        assert card_ids == run_ids
        # The workflow did not leak (no audit) and the skip still composed
        # (s2 gone, s3 reconnected onto s1) — the trivial-echo guard.
        assert card_ids == ["s1", "s3"]
