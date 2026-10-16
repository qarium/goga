"""Logic tests of ``apply_stage_env_wrappers`` — the per-stage env delivery scenarios."""

from __future__ import annotations

import difflib
import stat
from pathlib import Path

import pytest
import yaml
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


class TestUnsafeAndQuotedStageIds:
    """Unsafe and serializer-quoted stage ids claim, wrap, and patch correctly."""

    def test_apply_stage_env_wrappers_unsafe_and_quoted_stage_ids(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """A stage id that is not a safe file name wraps under the sanitized
        plus digest name; ids the serializer had to quote ("01", "true")
        still find their flow-file block through the YAML-scalar header match."""
        pipeline_path = tmp_path / "deploy.yml"
        pipeline_path.write_text(
            """name: Deploy
description: d
---

"01":
  title: First

my stage:
  title: Has Space

"true":
  title: Boolish
""",
        )
        flow_path = tmp_path / "flow.yml"
        workflow_text = (
            'stages:\n  "01":\n    env:\n      E: "1"\n'
            '  my stage:\n    env:\n      F: "2"\n'
            '  "true":\n    env:\n      G: "3"\n'
        )
        workflow = parse_workflow(workflow_text)
        from goga.pipeline.compiler import compile_flow

        _, doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

        result = stage_env_wrappers.apply_stage_env_wrappers(doc.stages, workflow, "claude", flow_path)

        by_id = {stage.id: stage for stage in result}
        assert by_id["01"].fields["command"] == str(wrapper_base / "01")
        assert by_id["my stage"].fields["command"].startswith(str(wrapper_base / "my_stage-"))
        assert by_id["true"].fields["command"] == str(wrapper_base / "true")

        # Each patched command line lands inside its OWN stage block.
        patched_lines = flow_path.read_text().splitlines()
        header_of = {"01": "- id: '01'", "my stage": "- id: my stage", "true": "- id: 'true'"}
        for stage_id, header in header_of.items():
            header_index = patched_lines.index(header)
            command_index = patched_lines.index(f"  command: {by_id[stage_id].fields['command']}")
            assert header_index < command_index
            # The next header (or EOF) ends this block — no cross-block leak.
            following = [line for line in patched_lines[command_index + 1 :] if line.startswith("- id: ")]
            assert not following or command_index < patched_lines.index(following[0])

        assert (wrapper_base / "01").read_text().startswith("#!/bin/sh\nexport E=1\n")

    def test_select_claims_exact_id_beats_suffix_expansion(self) -> None:
        """A workflow declaring env on both the loop source ``worker`` and the
        literal ``worker-1``: the exact id claims worker-1 (its own values);
        only the unclaimed loop copies inherit the loop env."""
        workflow = parse_workflow(
            'stages:\n  worker:\n    loop: 3\n    env:\n      N: "loop"\n  worker-1:\n    env:\n      N: "exact"\n',
        )
        stages = [
            FlowStage(id=f"worker-{index}", name=f"worker-{index}", depends_on=None, fields={}) for index in (1, 2, 3)
        ]

        claims = stage_env_wrappers._select_claims(stages, workflow)

        assert claims["worker-1"] == ("worker-1", workflow.stages["worker-1"])
        assert claims["worker-2"] == ("worker", workflow.stages["worker"])
        assert claims["worker-3"] == ("worker", workflow.stages["worker"])


class TestIllegalEnvKeyRejected:
    """An env key that is not a legal variable name is a strict pre-run error."""

    def test_apply_stage_env_wrappers_rejects_illegal_env_key_writing_nothing(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """A key with shell metacharacters never reaches a generated export
        line — one strict error naming the stage and the key, no wrapper file
        written, the flow-file untouched."""
        stages, workflow, flow_path, original = _compile(
            tmp_path,
            'stages:\n  build:\n    agent: codex\n    env:\n      "BAD; KEY": "1"\n',
        )

        with pytest.raises(ValueError, match="invalid environment variable name in the build stage env") as excinfo:
            stage_env_wrappers.apply_stage_env_wrappers(stages, workflow, "claude", flow_path)

        assert "BAD; KEY" in str(excinfo.value)
        assert not wrapper_base.exists()
        assert flow_path.read_text() == original


class TestCommandInsertionAnchors:
    """The absent-command insertion picks the canonical anchor position."""

    def test_patch_stage_command_inserts_before_depends_on_tail(self) -> None:
        """A block whose only post-command field is ``depends_on`` anchors the
        insertion there (``depends_on`` serializes last)."""
        text = "stages:\n- id: lone\n  depends_on: [build]\n"

        patched = stage_env_wrappers._patch_stage_command(text, "lone", "/wrappers/lone")

        assert patched == "stages:\n- id: lone\n  command: /wrappers/lone\n  depends_on: [build]\n"

    def test_patch_stage_command_inserts_at_block_end_without_anchor(self) -> None:
        """A block with neither a canonical anchor nor ``depends_on`` takes the
        insertion at its end."""
        text = "stages:\n- id: lone\n"

        patched = stage_env_wrappers._patch_stage_command(text, "lone", "/wrappers/lone")

        assert patched == "stages:\n- id: lone\n  command: /wrappers/lone\n"

    def test_patch_stage_command_survives_blank_lines_inside_scalars(self) -> None:
        """Blank lines the serializer emits INSIDE multi-line scalars (paragraph
        breaks) do not end the block scan — the insertion lands before the
        anchor that follows the scalar, never inside the scalar text."""
        text = yaml.dump(
            {"stages": [{"id": "lone", "note": "line1\n\nline2", "depends_on": []}]},
            sort_keys=False,
        )

        patched = stage_env_wrappers._patch_stage_command(text, "lone", "/wrappers/lone")
        reparsed = yaml.safe_load(patched)

        assert reparsed["stages"][0]["command"] == "/wrappers/lone"
        assert reparsed["stages"][0]["note"] == "line1\n\nline2"
        assert reparsed["stages"][0]["depends_on"] == []


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


class TestAllDotStageIds:
    """An all-dot stage id never resolves to the wrapper base directory itself."""

    def test_apply_stage_env_wrappers_all_dot_stage_id_routes_through_sanitization(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """The ids "." and ".." fullmatch the safe-name charset but ARE the
        directory aliases — they route through the sanitize branch like any
        other unsafe id, so the closure lands in a regular digested file
        instead of an IsADirectoryError on the base directory."""
        workflow = parse_workflow('stages:\n  ".":\n    env:\n      E: "1"\n')
        stages = [FlowStage(id=".", name=".", depends_on=None, fields={})]
        flow_path = tmp_path / "flow.yml"
        flow_path.write_text('stages:\n- id: "."\n')

        result = stage_env_wrappers.apply_stage_env_wrappers(stages, workflow, "claude", flow_path)

        by_id = {stage.id: stage for stage in result}
        command = Path(by_id["."].fields["command"])
        assert str(command).startswith(str(wrapper_base / ".-"))
        assert command.is_file()

        patched_stage = yaml.safe_load(flow_path.read_text())["stages"][0]
        assert patched_stage["command"] == str(command)


class TestOwnerOnlyPermissions:
    """The exported env layer stays owner-only from the first byte."""

    def test_apply_stage_env_wrappers_creates_owner_only_closures(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """The wrapper base and every generated closure carry mode 0o700 — a
        regression to a plain write (or a widened pre-existing base) would
        leave the per-stage env values world-readable under /tmp."""
        stages, workflow, flow_path, _original = _compile(
            tmp_path,
            'stages:\n  build:\n    agent: codex\n    env:\n      E: "1"\n',
        )

        stage_env_wrappers.apply_stage_env_wrappers(stages, workflow, "claude", flow_path)

        assert stat.S_IMODE(wrapper_base.stat().st_mode) == 0o700
        assert stat.S_IMODE((wrapper_base / "build").stat().st_mode) == 0o700


class TestStageMissingFromFlowFile:
    """A claimed stage id with no serialized block is the invariant breach."""

    def test_apply_stage_env_wrappers_strict_error_when_stage_missing_from_flow_file(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """The stage list and the serialized flow-file disagree — one strict
        error naming the stage, never a silent skip or a mis-anchored patch
        that would launch the stage without its env wrapper."""
        workflow = parse_workflow('stages:\n  build:\n    agent: codex\n    env:\n      E: "1"\n')
        stages = [FlowStage(id="build", name="build", depends_on=None, fields={})]
        flow_path = tmp_path / "flow.yml"
        flow_path.write_text("stages:\n- id: other\n")

        with pytest.raises(ValueError, match="missing from the flow-file") as excinfo:
            stage_env_wrappers.apply_stage_env_wrappers(stages, workflow, "claude", flow_path)

        assert "'build'" in str(excinfo.value)


class TestExtendAgentTier:
    """The exec target resolves the extend-entry agent — the compiler's precedence."""

    def test_apply_stage_env_wrappers_extend_agent_is_the_exec_target(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """An extend-seeded stage (agent in the extend entry, env in the stages
        block) execs the extend agent — the same agent the compiler composed
        into the pre-patch command, never the global agent."""
        workflow_text = (
            "extend:\n  deploy:\n    after:\n      - build\n    agent: codex\n"
            'stages:\n  deploy:\n    env:\n      E: "1"\n'
        )
        stages, workflow, flow_path, _ = _compile(tmp_path, workflow_text)

        result = stage_env_wrappers.apply_stage_env_wrappers(stages, workflow, "claude", flow_path)

        by_id = {stage.id: stage for stage in result}
        expected = '#!/bin/sh\nexport E=1\nexec /home/goga/bin/codex-as-claude.sh "$@"\n'
        assert by_id["deploy"].fields["command"] == str(wrapper_base / "deploy")
        assert (wrapper_base / "deploy").read_text() == expected

    def test_apply_stage_env_wrappers_stages_agent_beats_extend_agent(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """An explicit stages-block agent wins over the extend-entry agent —
        the per-field overlay precedence the compiler applies."""
        workflow_text = (
            "extend:\n  deploy:\n    after:\n      - build\n    agent: codex\n"
            'stages:\n  deploy:\n    agent: gemini\n    env:\n      E: "1"\n'
        )
        stages, workflow, flow_path, _ = _compile(tmp_path, workflow_text)

        stage_env_wrappers.apply_stage_env_wrappers(stages, workflow, "claude", flow_path)

        expected = '#!/bin/sh\nexport E=1\nexec /home/goga/bin/gemini-as-claude.sh "$@"\n'
        assert (wrapper_base / "deploy").read_text() == expected

    def test_apply_stage_env_wrappers_loop_copies_inherit_extend_agent(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """Loop-expanded copies of an extend-seeded stage (loop and agent in
        the extend entry, env in the stages block) each exec the extend agent
        — the agent their compiled commands carried before the patch."""
        workflow_text = (
            "extend:\n  scan:\n    after:\n      - build\n    agent: codex\n    loop: 2\n"
            'stages:\n  scan:\n    env:\n      N: "1"\n'
        )
        stages, workflow, flow_path, _ = _compile(tmp_path, workflow_text)

        result = stage_env_wrappers.apply_stage_env_wrappers(stages, workflow, "claude", flow_path)

        by_id = {stage.id: stage for stage in result}
        expected = '#!/bin/sh\nexport N=1\nexec /home/goga/bin/codex-as-claude.sh "$@"\n'
        for index in (1, 2):
            wrapper = wrapper_base / f"scan-{index}"
            assert by_id[f"scan-{index}"].fields["command"] == str(wrapper)
            assert wrapper.read_text() == expected


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
