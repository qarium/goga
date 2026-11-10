"""Logic tests of ``apply_gate_env_wrappers`` — the per-step gate env delivery scenarios."""

from __future__ import annotations

import difflib
import stat
from pathlib import Path

import pytest
import yaml
from goga.pipeline import gate_env_wrappers
from goga.pipeline.compiler import FlowStage, FlowVerify, FlowVerifyStep, compile_flow
from goga.pipeline.gate_env_wrappers import apply_gate_env_wrappers
from goga.pipeline.workflow import parse_workflow

# A STAGES pipeline-file with a gated stage, a loop-expanded stage, a gated
# stage whose verify section precedes a depends_on list, and a plain stage —
# the compile substrate of the delivery scenarios.
_PIPELINE_TEXT = """name: Deploy
description: d
---

build:
  title: Build

worker:
  title: Worker

ship:
  title: Ship
  depends_on: [build]

audit:
  title: Audit
"""


@pytest.fixture
def wrapper_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Relocate the gate wrapper base into the tmp tree and return its path."""
    base = tmp_path / "goga-gate-env"
    monkeypatch.setattr(gate_env_wrappers, "_GATE_WRAPPER_BASE", base)

    return base


def _compile(tmp_path: Path, workflow_text: str) -> tuple[list[FlowStage], object, Path, str]:
    """Compile the fixture pipeline under ``workflow_text``; return stages, workflow, flow path, original text."""
    pipeline_path = tmp_path / "deploy.yml"
    pipeline_path.write_text(_PIPELINE_TEXT)

    flow_path = tmp_path / "flow.yml"
    workflow = parse_workflow(workflow_text)
    _, doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

    return doc.stages, workflow, flow_path, flow_path.read_text()


class TestClosureGeneration:
    """The generated sh closures carry the env layer and the authored payload."""

    def test_script_step_closure_exports_env_then_script(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """A script step's closure exports the env in authored order, then the script lines as-is."""
        stages, workflow, flow_path, _original = _compile(
            tmp_path,
            "stages:\n"
            "  build:\n"
            "    gates:\n"
            "      - name: tests\n"
            "        script: pytest -q\n"
            "        env:\n"
            "          FOO: bar\n"
            "          BAZ: qu x\n",
        )

        apply_gate_env_wrappers(stages, workflow, flow_path)

        wrapper = wrapper_base / "build-0-tests"
        assert wrapper.read_text() == "#!/bin/sh\nexport FOO=bar\nexport BAZ='qu x'\npytest -q\n"
        assert stat.S_IMODE(wrapper.stat().st_mode) == 0o700

    def test_agent_step_closure_exports_env_then_execs_wrapper(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """An agent step's closure exports the env, then execs the agent wrapper — the stage-env shape."""
        stages, workflow, flow_path, _original = _compile(
            tmp_path,
            "stages:\n"
            "  build:\n"
            "    gates:\n"
            "      - name: review\n"
            "        agent: codex\n"
            "        prompt: Review.\n"
            "        env:\n"
            "          MODEL: gpt\n",
        )

        apply_gate_env_wrappers(stages, workflow, flow_path)

        wrapper = wrapper_base / "build-0-review"
        assert wrapper.read_text() == '#!/bin/sh\nexport MODEL=gpt\nexec /home/goga/bin/codex-as-claude.sh "$@"\n'

    def test_wrapper_name_sanitized_for_unsafe_step_name(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """A step name that is not a safe file name flows through the shared sanitize helper."""
        stages, workflow, flow_path, _original = _compile(
            tmp_path,
            "stages:\n"
            "  build:\n"
            "    gates:\n"
            "      - name: unit tests\n"
            "        script: pytest\n"
            "        env:\n"
            "          E: '1'\n",
        )

        result = apply_gate_env_wrappers(stages, workflow, flow_path)

        step = result[0].fields["verify"].steps[0]
        wrapper = Path(step.run)

        assert wrapper.parent == wrapper_base
        assert wrapper.exists()
        assert "unit_tests-" in wrapper.name

    def test_two_env_steps_of_one_stage_get_distinct_wrappers(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """Steps sharing a stage never collide — the step index rides in the file name."""
        stages, workflow, flow_path, _original = _compile(
            tmp_path,
            "stages:\n"
            "  build:\n"
            "    gates:\n"
            "      - name: checks\n"
            "        script: pytest\n"
            "        env:\n"
            "          A: '1'\n"
            "      - name: checks\n"
            "        script: ruff check .\n"
            "        env:\n"
            "          B: '2'\n",
        )

        result = apply_gate_env_wrappers(stages, workflow, flow_path)

        first, second = result[0].fields["verify"].steps

        assert Path(first.run) != Path(second.run)
        assert Path(first.run).exists()
        assert Path(second.run).exists()


class TestVerifyStepPatch:
    """The targeted patch rewrites exactly the claimed steps' run/command fields."""

    def test_patches_only_the_claimed_script_step_line(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """An env step's run line is rewritten; a sibling env-free step and every other byte stay untouched."""
        stages, workflow, flow_path, original = _compile(
            tmp_path,
            "stages:\n"
            "  build:\n"
            "    gates:\n"
            "      - name: tests\n"
            "        script: pytest -q\n"
            "        env:\n"
            "          FOO: bar\n"
            "      - name: plain\n"
            "        script: echo ok\n",
        )

        apply_gate_env_wrappers(stages, workflow, flow_path)

        patched = flow_path.read_text()
        diff = [
            line
            for line in difflib.unified_diff(original.splitlines(), patched.splitlines(), lineterm="", n=0)
            if line[:1] in "+-" and line[:3] not in ("---", "+++")
        ]

        assert len(diff) == 2
        assert diff[0] == "-    run: pytest -q"
        assert diff[1].startswith("+    run: ")
        assert diff[1].endswith("/build-0-tests")

        document = yaml.safe_load(patched)
        steps = document["stages"][0]["verify"]

        assert [step["name"] for step in steps] == ["tests", "plain"]
        assert steps[0]["run"] == str(wrapper_base / "build-0-tests")
        assert steps[0]["timeout"] == "1h"
        assert steps[1]["run"] == "echo ok"

    def test_patches_agent_step_command_and_keeps_prompt_literal(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """An agent step's command line is rewritten; its prompt block literal stays byte-identical."""
        stages, workflow, flow_path, _original = _compile(
            tmp_path,
            "stages:\n"
            "  build:\n"
            "    gates:\n"
            "      - name: review\n"
            "        agent: codex\n"
            "        prompt: |\n"
            "          Review the diff.\n"
            "          run: never captures this line\n"
            "        env:\n"
            "          MODEL: gpt\n",
        )

        apply_gate_env_wrappers(stages, workflow, flow_path)

        patched = flow_path.read_text()

        assert "Review the diff.\n" in patched
        assert "run: never captures this line" in patched
        assert "/home/goga/bin/codex-as-claude.sh" not in patched

        document = yaml.safe_load(patched)
        step = document["stages"][0]["verify"][0]

        assert step["command"] == str(wrapper_base / "build-0-review")
        assert step["prompt"] == "Review the diff.\nrun: never captures this line\n"

    def test_multiline_script_value_replaced_whole(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """A block-literal run value — a paragraph break inside included — is consumed whole."""
        stages, workflow, flow_path, _original = _compile(
            tmp_path,
            "stages:\n"
            "  build:\n"
            "    gates:\n"
            "      - name: build-all\n"
            "        script: |\n"
            "          make all\n"
            "\n"
            "          make check\n"
            "        timeout: 30m\n"
            "        env:\n"
            "          MULTI: 'yes'\n",
        )

        apply_gate_env_wrappers(stages, workflow, flow_path)

        document = yaml.safe_load(flow_path.read_text())
        step = document["stages"][0]["verify"][0]

        assert step["run"] == str(wrapper_base / "build-0-build-all")
        assert step["timeout"] == "30m"
        assert "make check" not in flow_path.read_text()

    def test_container_form_entries_patched_at_deeper_indent(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """Under the container form (settings authored) the nested entries patch identically."""
        stages, workflow, flow_path, _original = _compile(
            tmp_path,
            "gates:\n"
            "  max_iterations: 2\n"
            "stages:\n"
            "  build:\n"
            "    gates:\n"
            "      - name: tests\n"
            "        script: pytest -q\n"
            "        env:\n"
            "          FOO: bar\n",
        )

        apply_gate_env_wrappers(stages, workflow, flow_path)

        document = yaml.safe_load(flow_path.read_text())
        gate = document["stages"][0]["verify"]

        assert gate["max_failures"] == 2
        assert gate["steps"][0]["run"] == str(wrapper_base / "build-0-tests")

    def test_verify_before_depends_on_tail_patches_cleanly(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """A claimed stage whose verify precedes a depends_on list patches without touching the list."""
        stages, workflow, flow_path, _original = _compile(
            tmp_path,
            "stages:\n"
            "  ship:\n"
            "    gates:\n"
            "      - name: audit\n"
            "        script: ./audit.sh\n"
            "        env:\n"
            "          AUDIT: strict\n",
        )

        apply_gate_env_wrappers(stages, workflow, flow_path)

        document = yaml.safe_load(flow_path.read_text())
        ship = next(stage for stage in document["stages"] if stage["id"] == "ship")

        assert ship["depends_on"] == ["build"]
        assert ship["verify"][0]["run"] == str(wrapper_base / "ship-0-audit")

    def test_loop_expanded_copies_each_claimed_with_own_wrapper(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """Every loop copy descended from a gated stage receives its own closure of the same env."""
        stages, workflow, flow_path, _original = _compile(
            tmp_path,
            "stages:\n"
            "  worker:\n"
            "    loop: 2\n"
            "    gates:\n"
            "      - name: tests\n"
            "        script: pytest\n"
            "        env:\n"
            "          W: '1'\n",
        )

        result = apply_gate_env_wrappers(stages, workflow, flow_path)

        document = yaml.safe_load(flow_path.read_text())
        by_id = {stage["id"]: stage for stage in document["stages"]}

        assert by_id["worker-1"]["verify"][0]["run"] == str(wrapper_base / "worker-1-0-tests")
        assert by_id["worker-2"]["verify"][0]["run"] == str(wrapper_base / "worker-2-0-tests")

        closures = {
            Path(step.run).read_text()
            for stage in result
            if "verify" in stage.fields
            for step in stage.fields["verify"].steps
        }

        assert closures == {"#!/bin/sh\nexport W=1\npytest\n"}


class TestInMemoryRebuild:
    """The returned stage list rebuilds exactly the claimed stages' verify gates."""

    def test_claimed_stage_rebuilt_others_same_objects(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """A claimed stage is a new object with a rebuilt gate; env-free stages are the SAME objects."""
        stages, workflow, flow_path, _original = _compile(
            tmp_path,
            "stages:\n"
            "  build:\n"
            "    gates:\n"
            "      - name: tests\n"
            "        script: pytest\n"
            "        env:\n"
            "          F: v\n"
            "  audit:\n"
            "    gates:\n"
            "      - name: lint\n"
            "        script: ruff check .\n",
        )

        result = apply_gate_env_wrappers(stages, workflow, flow_path)
        original_by_id = {stage.id: stage for stage in stages}
        result_by_id = {stage.id: stage for stage in result}

        assert result_by_id["build"] is not original_by_id["build"]
        assert result_by_id["audit"] is original_by_id["audit"]

        gate = result_by_id["build"].fields["verify"]

        assert isinstance(gate, FlowVerify)
        assert gate.steps[0] == FlowVerifyStep(name="tests", run=str(wrapper_base / "build-0-tests"), timeout="1h")
        assert original_by_id["build"].fields["verify"].steps[0].run == "pytest"

    def test_container_settings_carried_onto_the_rebuilt_gate(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """The rebuilt FlowVerify carries the compiled settings verbatim."""
        stages, workflow, flow_path, _original = _compile(
            tmp_path,
            "gates: {patience: 1, max_iterations: 3, fresh_correction: false}\n"
            "stages:\n"
            "  build:\n"
            "    gates:\n"
            "      - name: tests\n"
            "        script: pytest\n"
            "        env:\n"
            "          F: v\n",
        )

        result = apply_gate_env_wrappers(stages, workflow, flow_path)
        gate = result[0].fields["verify"]

        assert gate.max_failures == 3
        assert gate.review_patience == 1
        assert gate.fresh_correction is False


class TestClaimsAndInvariants:
    """The claim resolution and the env-free invariants."""

    def test_gated_but_env_free_stage_not_claimed(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """A stage with gates but no step env maps is untouched — byte-identical output, no closures."""
        stages, workflow, flow_path, original = _compile(
            tmp_path,
            "stages:\n"
            "  build:\n"
            "    gates:\n"
            "      - name: tests\n"
            "        script: pytest\n"
            "      - name: empty\n"
            "        script: echo ok\n"
            "        env: {}\n",
        )

        result = apply_gate_env_wrappers(stages, workflow, flow_path)

        assert result == stages
        assert flow_path.read_text() == original
        assert not wrapper_base.exists()

    def test_no_gate_env_workflow_never_reads_the_flow_file(self, tmp_path: Path) -> None:
        """Without claims the flow-file is neither read nor written — a missing path cannot abort the run."""
        stages, workflow, _flow_path, _original = _compile(
            tmp_path,
            "stages:\n  build:\n    prompt: x\n",
        )

        result = apply_gate_env_wrappers(stages, workflow, tmp_path / "missing.yml")

        assert result == stages

    def test_none_workflow_returns_input_unchanged(self, tmp_path: Path) -> None:
        """A None workflow (no workflow resolved) wraps nothing."""
        stages, _workflow, _flow_path, _original = _compile(tmp_path, "stages:\n  build:\n    prompt: x\n")

        result = apply_gate_env_wrappers(stages, None, tmp_path / "missing.yml")

        assert result == stages

    def test_illegal_env_name_rejected_before_any_file_written(
        self,
        tmp_path: Path,
        wrapper_base: Path,
    ) -> None:
        """A non-POSIX env key raises naming the stage, step, and key — before any wrapper file exists."""
        stages, workflow, flow_path, original = _compile(
            tmp_path,
            "stages:\n"
            "  build:\n"
            "    gates:\n"
            "      - name: good\n"
            "        script: echo ok\n"
            "        env:\n"
            "          FINE: '1'\n"
            "      - name: bad\n"
            "        script: echo bad\n"
            "        env:\n"
            "          BAD-KEY: '2'\n",
        )

        with pytest.raises(ValueError, match="invalid environment variable name in the build stage gate bad env"):
            apply_gate_env_wrappers(stages, workflow, flow_path)

        assert not wrapper_base.exists()
        assert flow_path.read_text() == original
