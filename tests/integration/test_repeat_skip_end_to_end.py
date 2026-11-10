"""End-to-end integration test: the authored repeat block survives the skip path.

The run path composes the resolved workflow through TWO document rebuilds
before the compiler ever sees it — ``apply_skip_stages`` (the CLI
``-s/--skip`` merge) and the ``pipeline.amend_workflow`` overlay rebuild
(``merge_workflow_overlay``, which reconstructs the document even when no
tool contributes) — and each rebuild carries the repeat block verbatim by
construction. A rebuild that dropped it would silently recompile an authored
``repeat: {max_cycles: N}`` as the scalar ``repeat: true`` on every
skip-driven run, so the composed path — not the per-cell unit suites — is
where that survival is proven: this drives the real in-container run
coordination (``run_pipeline``, only the afm launch mocked) from the
CWD-based workflow resolution through the skip merge and the amendment
delivery into the real ``compile_flow`` writing the flow-file that
``afm run`` would consume.

The byte-identity guarantee for non-repeatable pipelines (the serializer's
``None`` arm omits the key entirely) is guarded permanently by
``tests/pipeline/compiler/test_shipped_pipelines_compile.py`` plus the
serializer unit suite; the pre/post diff over the shipped assets was this
task's one-off verification (recorded in the task notes) and adds no
permanent golden fixtures here.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import pytest
import yaml
from goga.pipeline import run_pipeline

# goga.pipeline.run_pipeline is shadowed in the package __init__ by the
# run_pipeline function, so a string-based mock.patch path walking through it
# fails on Python 3.10. Resolve the real module via sys.modules and patch its
# run_flow attribute directly. Per [[feedback_mock_patch_module_shadowing]].
_run_pipeline_module = sys.modules["goga.pipeline.run_pipeline"]

# A repeatable pipeline-file: the header capability flag plus two stages —
# the skipped ``review`` and the surviving ``build``.
_HARDENING_YML = """\
name: Hardening
description: Repeatable hardening pass
repeatable: true
---

build:
  title: Build
review:
  title: Review
"""

# The project workflow (basename auto-match "hardening"): an authored repeat
# block and nothing else — the block alone is a valid non-empty workflow, so
# the scenario isolates the repeat carry from every other workflow feature.
_HARDENING_WORKFLOW_YML = "repeat:\n  max_cycles: 2\n"


class TestRepeatSkipEndToEnd:
    def test_run_pipeline_skip_path_compiles_authored_repeat(
        self,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
        in_container_pipeline_run_context: Path,
    ) -> None:
        """A skip-driven run compiles the authored ``max_cycles: 2`` and drops the skipped stage.

        The chain: ``resolve_workflow`` (basename auto-match) → ``load_workflow``
        → ``apply_skip_stages(["review"])`` → the ``amend_workflow`` overlay
        rebuild → ``compile_flow`` → the flow-file at ``<AFM_DIR>/flow.yml``.
        The flow-file must carry the authored block form (present keys only —
        ``keep_runs`` stays absent) at the canonical position right after
        ``description``, and the stage list must omit the skipped ``review``.
        """
        project_dir = tmp_path / ".goga" / "pipelines"
        project_dir.mkdir(parents=True)
        (project_dir / "hardening.yml").write_text(_HARDENING_YML)

        workflows_dir = tmp_path / ".goga" / "workflows"
        workflows_dir.mkdir(parents=True)
        (workflows_dir / "hardening.yml").write_text(_HARDENING_WORKFLOW_YML)

        user_dir = tmp_path / "user_pipelines"
        user_dir.mkdir(parents=True)

        afm_dir = (tmp_path / ".afm").resolve()
        afm_dir.mkdir(parents=True)

        monkeypatch.chdir(tmp_path)
        monkeypatch.setenv("AFM_DIR", str(afm_dir))

        # No activation channels — the ambient engine variables of a
        # goga-hosted session must not reach the loading chain.
        monkeypatch.delenv("GOGA_PROFILE", raising=False)
        monkeypatch.delenv("GOGA_HOME_PROFILES", raising=False)

        with mock.patch.object(_run_pipeline_module, "run_flow", return_value=0):
            exit_code = run_pipeline("hardening", project_dir, user_dir, 50321, skip=["review"])

        assert exit_code == 0

        text = (afm_dir / "flow.yml").read_text()

        # The authored cycle bound reached the flow-file — not the scalar default.
        assert "max_cycles: 2" in text
        assert "keep_runs" not in text

        # The canonical emission position: after ``description``, before the
        # stage list (this flow carries no memory block — memory is optional).
        assert text.index("description:") < text.index("repeat:") < text.index("stages:")

        # The skipped stage never reached the composition; the survivor did.
        flow = yaml.safe_load(text)
        assert flow["repeat"] == {"max_cycles": 2}
        assert [stage["id"] for stage in flow["stages"]] == ["build"]
