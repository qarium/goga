"""Logic tests of ``apply_stage_env_wrappers`` — the per-stage env delivery scenarios."""

from __future__ import annotations

import difflib
from pathlib import Path

import pytest
from goga.pipeline import stage_env_wrappers
from goga.pipeline.compiler import FlowStage, compile_flow
from goga.pipeline.workflow import parse_workflow

# A STAGES pipeline-file with an env-declaring stage, a loop-expanded stage,
# and an env-free stage — the compile substrate of the delivery scenarios.
_PIPELINE_TEXT = """name: Deploy
description: d
---

build:
  title: Build

worker:
  title: Worker

test:
  title: Test
"""


@pytest.fixture
def wrapper_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Relocate the wrapper base into the tmp tree and return its path."""
    base = tmp_path / "goga-stage-env"
    monkeypatch.setattr(stage_env_wrappers, "_WRAPPER_BASE", base)

    return base


def _compile(tmp_path: Path, workflow_text: str) -> tuple[list[FlowStage], object, Path, str]:
    """Compile the fixture pipeline under ``workflow_text``; return stages, workflow, flow path, original text."""
    pipeline_path = tmp_path / "deploy.yml"
    pipeline_path.write_text(_PIPELINE_TEXT)

    flow_path = tmp_path / "flow.yml"
    workflow = parse_workflow(workflow_text)
    _, doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

    return doc.stages, workflow, flow_path, flow_path.read_text()


class TestPatchesOnlyCommandFields:
    """The targeted patch rewrites exactly the claimed stages' command fields."""

    def test_apply_stage_env_wrappers_patches_only_command_fields(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """A claimed stage's command is patched; unclaimed stages are the SAME objects; only that line differs."""
        stages, workflow, flow_path, original = _compile(
            tmp_path,
            'stages:\n  build:\n    agent: codex\n    env:\n      E: "1"\n',
        )

        result = stage_env_wrappers.apply_stage_env_wrappers(stages, workflow, "claude", flow_path)

        by_id = {stage.id: stage for stage in result}
        wrapper = by_id["build"].fields["command"]
        assert wrapper == str(wrapper_base / "build")

        assert by_id["build"] is not {stage.id: stage for stage in stages}["build"]
        assert by_id["test"] is {stage.id: stage for stage in stages}["test"]
        assert by_id["worker"] is {stage.id: stage for stage in stages}["worker"]

        patched = flow_path.read_text()
        diff = [
            line
            for line in difflib.unified_diff(original.splitlines(), patched.splitlines(), lineterm="", n=0)
            if line[:1] in ("+", "-") and line[:3] not in ("+++", "---")
        ]

        assert diff == [
            "-  command: /home/goga/bin/codex-as-claude.sh",
            f"+  command: {wrapper}",
        ]

        assert (wrapper_base / "build").read_text() == (
            '#!/bin/sh\nexport E=1\nexec /home/goga/bin/codex-as-claude.sh "$@"\n'
        )


class TestEnvFreeRunIsByteIdentical:
    """An env-free run touches no file and returns the input list."""

    def test_apply_stage_env_wrappers_env_free_run_is_byte_identical(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """No claims → the input list identity, byte-identical file, no wrapper directory."""
        stages, workflow, flow_path, original = _compile(
            tmp_path,
            "stages:\n  build:\n    agent: codex\n",
        )

        stat_before = flow_path.stat()
        result = stage_env_wrappers.apply_stage_env_wrappers(stages, workflow, "claude", flow_path)

        assert result is stages
        assert flow_path.read_text() == original
        assert flow_path.stat().st_mtime_ns == stat_before.st_mtime_ns
        assert not wrapper_base.exists()

    def test_apply_stage_env_wrappers_none_workflow_returns_input_unchanged(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """A ``None`` workflow wraps nothing — the input list returns verbatim."""
        stages, _workflow, flow_path, original = _compile(tmp_path, "stages:\n  build:\n    agent: codex\n")

        result = stage_env_wrappers.apply_stage_env_wrappers(stages, None, "claude", flow_path)

        assert result is stages
        assert flow_path.read_text() == original
        assert not wrapper_base.exists()


class TestLoopCopiesEachGetWrapper:
    """Loop-expanded copies of an env-declaring stage each receive their own wrapper."""

    def test_apply_stage_env_wrappers_loop_copies_each_get_wrapper(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """``loop: 3`` claims worker-1..worker-3 — three wrappers, three patched commands."""
        stages, workflow, flow_path, _original = _compile(
            tmp_path,
            'stages:\n  worker:\n    loop: 3\n    env:\n      N: "9"\n',
        )

        result = stage_env_wrappers.apply_stage_env_wrappers(stages, workflow, "claude", flow_path)

        by_id = {stage.id: stage for stage in result}
        copies = [by_id[f"worker-{index}"] for index in (1, 2, 3)]
        commands = [copy.fields["command"] for copy in copies]

        assert len(set(commands)) == 3

        for command in commands:
            wrapper = Path(command)
            assert wrapper.read_text() == ('#!/bin/sh\nexport N=9\nexec /home/goga/bin/claude-as-claude.sh "$@"\n')

        patched_lines = flow_path.read_text().splitlines()

        for copy in copies:
            assert f"  command: {copy.fields['command']}" in patched_lines

        assert by_id["build"] is {stage.id: stage for stage in stages}["build"]


class TestStrictErrorWithoutAnyAgent:
    """No stage agent and no global agent fails strictly before launch."""

    def test_apply_stage_env_wrappers_strict_error_without_any_agent(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """The strict error names the stage; no wrapper is written; the flow-file is untouched."""
        stages, workflow, flow_path, original = _compile(
            tmp_path,
            'stages:\n  build:\n    env:\n      E: "1"\n',
        )

        with pytest.raises(ValueError, match="build"):
            stage_env_wrappers.apply_stage_env_wrappers(stages, workflow, None, flow_path)

        assert not wrapper_base.exists()
        assert flow_path.read_text() == original


class TestInsertsCommandWhenAbsent:
    """A claimed stage without a command line gains one at the canonical position."""

    def test_apply_stage_env_wrappers_inserts_command_when_absent(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """Env without a stage agent + ``global_agent`` inserts before the first canonical key after command."""
        stages, workflow, flow_path, original = _compile(
            tmp_path,
            'stages:\n  build:\n    env:\n      E: "1"\n',
        )

        result = stage_env_wrappers.apply_stage_env_wrappers(stages, workflow, "claude", flow_path)

        by_id = {stage.id: stage for stage in result}
        wrapper = str(wrapper_base / "build")

        assert by_id["build"].fields["command"] == wrapper

        original_lines = original.splitlines()
        patched_lines = flow_path.read_text().splitlines()
        inserted = [line for line in patched_lines if line not in original_lines]

        assert inserted == [f"  command: {wrapper}"]
        assert patched_lines.index(f"  command: {wrapper}") < patched_lines.index("  agents: [auto]")

        assert (wrapper_base / "build").read_text() == (
            '#!/bin/sh\nexport E=1\nexec /home/goga/bin/claude-as-claude.sh "$@"\n'
        )
