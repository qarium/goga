"""Contract and logic tests of the collaboration plumbing of ``write_afm_config``.

Covers the collaboration half of the afm configuration authorship: the
section materializes only when both the compiled flow document and the
effective workflow document are given; the generated profiles exist exactly
for the flow-referenced ids (one ``goga-<name>`` profile per team member and
stage attachment, deduplicated); each profile carries exactly
``{title, command, delegate}``; an env-declaring assistant resolves to an
owner-only sh closure whose path becomes the profile's command;
``limits.max_tasks`` is written only with a delegation block; and the two
pre-run errors (an illegal env key, an unresolvable agent) fire before any
file — config or closure — is written.
"""

from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pytest
import yaml
from goga.pipeline import apply_skip_stages, write_afm_config
from goga.pipeline.compiler import (
    FlowAssistant,
    FlowDocument,
    FlowStage,
    FlowTeamMember,
    compile_flow,
    serialize_flow,
)
from goga.pipeline.workflow import (
    WorkflowAssistant,
    WorkflowDelegation,
    WorkflowDocument,
    WorkflowStage,
    parse_workflow,
)

# goga.pipeline.afm_config is shadowed in the package __init__ by the
# write_afm_config function — resolve the real module for direct attribute
# patching. Per [[feedback_mock_patch_module_shadowing]].
_afm_config_module = sys.modules["goga.pipeline.afm_config"]


def _member(name: str) -> FlowTeamMember:
    """Build one flow team member bound to its ``goga-<name>`` profile."""
    return FlowTeamMember(id=name, title=name, profile=f"goga-{name}", instruction="Do.", skills=[])


def _attachment(name: str) -> FlowAssistant:
    """Build one stage attachment entry bound to its ``goga-<name>`` profile."""
    return FlowAssistant(
        profile=f"goga-{name}",
        title=name,
        instruction="Do.",
        mode="advisory",
        trigger="checkpoints",
        skills=[],
    )


def _flow_doc(
    members: list[FlowTeamMember] | None = None,
    stage_attachments: dict[str, list[FlowAssistant]] | None = None,
) -> FlowDocument:
    """Build a compiled flow document carrying a team and per-stage attachments."""
    stages = [
        FlowStage(id=stage_id, name=stage_id.title(), depends_on=None, fields={"assistants": list(entries)})
        for stage_id, entries in (stage_attachments or {}).items()
    ]

    return FlowDocument(name="demo", description="Demo", team=list(members or []), stages=stages)


def _workflow_doc(
    catalog: dict[str, WorkflowAssistant] | None = None,
    stages: dict[str, WorkflowStage] | None = None,
    delegation: WorkflowDelegation | None = None,
) -> WorkflowDocument:
    """Build an effective workflow document with catalog, stage declarations, and delegation."""
    return WorkflowDocument(
        stages=stages or {},
        assistants=catalog or {},
        delegation=delegation,
    )


@pytest.fixture
def closure_base(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Redirect the fixed closure-base constant into the tmp tree.

    The routine generates closures under ``/tmp/goga-assistant-env`` — a
    container-only path. The fixed base constant is patched so every generated
    closure lands under pytest's tmp_path instead.
    """
    base = tmp_path / "goga-assistant-env"
    monkeypatch.setattr(_afm_config_module, "_CLOSURE_BASE", base)
    return base


class TestWriteAfmConfigCollaborationContract:
    """Contract: when the collaboration section materializes."""

    def test_write_afm_config_importable_from_facade(self) -> None:
        """write_afm_config is importable from the goga.pipeline facade."""
        assert write_afm_config is not None

    def test_collaboration_section_requires_both_flow_and_workflow(self, config_path: Path) -> None:
        """Neither document alone writes the collaboration key — the old content shape stays."""
        flow = _flow_doc(members=[_member("reviewer")])
        workflow = _workflow_doc(catalog={"reviewer": WorkflowAssistant(name="reviewer", prompt="Review.")})

        write_afm_config("claude")
        assert "collaboration" not in yaml.safe_load(config_path.read_text())

        write_afm_config("claude", flow=flow)
        assert "collaboration" not in yaml.safe_load(config_path.read_text())

        write_afm_config("claude", workflow=workflow)
        assert "collaboration" not in yaml.safe_load(config_path.read_text())

        write_afm_config("claude", flow=flow, workflow=workflow)
        assert "collaboration" in yaml.safe_load(config_path.read_text())

    def test_collaboration_free_documents_write_empty_profiles(self, config_path: Path) -> None:
        """Both documents without collaboration content write an empty profiles map."""
        write_afm_config("claude", flow=_flow_doc(), workflow=_workflow_doc())

        data = yaml.safe_load(config_path.read_text())

        assert data["collaboration"] == {"profiles": {}}


class TestWriteAfmConfigCollaborationLogic:
    """Logic: the generated profiles, closures, limits, and pre-run errors."""

    def test_afm_config_profiles_exactly_for_referenced_ids(self, config_path: Path) -> None:
        """Profiles exist exactly for the flow-referenced ids — team first, then stage entries.

        The flow references ``goga-reviewer`` twice (a team member plus a
        stage attachment) and ``goga-security`` once (an inline declaration
        attached on a stage); the catalog declares ``reviewer``, the stage
        declares ``security`` inline. The dedup collapses the double reference
        into one profile; neither assistant declares its own agent, so both
        commands resolve to the global agent's wrapper.
        """
        flow = _flow_doc(
            members=[_member("reviewer")],
            stage_attachments={"verify": [_attachment("reviewer"), _attachment("security")]},
        )
        workflow = _workflow_doc(
            catalog={"reviewer": WorkflowAssistant(name="reviewer", prompt="Review.", delegate=True)},
            stages={
                "verify": WorkflowStage(
                    assistants=[
                        WorkflowAssistant(name="reviewer"),
                        WorkflowAssistant(name="security", prompt="Audit."),
                    ]
                )
            },
        )

        write_afm_config("claude", flow, workflow)

        data = yaml.safe_load(config_path.read_text())
        profiles = data["collaboration"]["profiles"]

        assert list(profiles) == ["goga-reviewer", "goga-security"]
        assert profiles["goga-reviewer"] == {
            "title": "reviewer",
            "command": "/home/goga/bin/claude-as-claude.sh",
            "delegate": True,
        }
        assert profiles["goga-security"] == {
            "title": "security",
            "command": "/home/goga/bin/claude-as-claude.sh",
            "delegate": False,
        }
        assert "limits" not in data["collaboration"]
        assert data["client"]["command"] == "/home/goga/bin/claude-as-claude.sh"

    def test_afm_config_env_closure_delivery(self, config_path: Path, closure_base: Path) -> None:
        """An env-declaring assistant resolves to an owner-only closure as its command.

        The closure exports the authored env verbatim and execs the resolved
        wrapper (the assistant's own agent tier), created owner-accessible
        from the first byte — mode 0o700.
        """
        workflow = _workflow_doc(
            catalog={
                "reviewer": WorkflowAssistant(
                    name="reviewer", prompt="Review.", agent="codex", env={"REVIEW_MODE": "strict"}
                )
            },
        )

        write_afm_config("codex", _flow_doc(members=[_member("reviewer")]), workflow)

        closure = closure_base / "goga-reviewer"
        assert closure.exists()
        assert closure.read_text() == (
            '#!/bin/sh\nexport REVIEW_MODE=strict\nexec /home/goga/bin/codex-as-claude.sh "$@"\n'
        )
        assert closure.stat().st_mode & 0o777 == 0o700

        profiles = yaml.safe_load(config_path.read_text())["collaboration"]["profiles"]
        assert profiles["goga-reviewer"] == {
            "title": "reviewer",
            "command": str(closure),
            "delegate": False,
        }

    def test_afm_config_max_tasks_only_with_delegation(self, config_path: Path) -> None:
        """limits.max_tasks appears only with a delegation block, carrying its materialized value."""
        flow = _flow_doc(members=[_member("reviewer")])
        catalog = {"reviewer": WorkflowAssistant(name="reviewer", prompt="Review.")}

        write_afm_config("claude", flow, _workflow_doc(catalog=catalog))
        assert "limits" not in yaml.safe_load(config_path.read_text())["collaboration"]

        write_afm_config("claude", flow, _workflow_doc(catalog=catalog, delegation=WorkflowDelegation(max_tasks=7)))
        assert yaml.safe_load(config_path.read_text())["collaboration"]["limits"] == {"max_tasks": 7}

        write_afm_config("claude", flow, _workflow_doc(catalog=catalog, delegation=WorkflowDelegation()))
        assert yaml.safe_load(config_path.read_text())["collaboration"]["limits"] == {"max_tasks": 50}

    def test_afm_config_illegal_env_key_before_any_file(self, config_path: Path, closure_base: Path) -> None:
        """An illegal env key is a strict pre-run error — no config file, no closure file."""
        workflow = _workflow_doc(
            catalog={"reviewer": WorkflowAssistant(name="reviewer", prompt="Review.", env={"BAD-KEY": "v"})},
        )

        with pytest.raises(
            ValueError, match=r"invalid environment variable name in the reviewer assistant env: 'BAD-KEY'"
        ):
            write_afm_config("claude", _flow_doc(members=[_member("reviewer")]), workflow)

        assert not config_path.exists()
        assert list(closure_base.glob("*")) == []

    def test_afm_config_no_agent_pre_run_error_names_site(self, config_path: Path, closure_base: Path) -> None:
        """An assistant resolving no agent names itself and its authoring site, before any file.

        The plain variant carries the bare wording; the env-declaring variant
        carries the ``declares env but`` fragment; an inline stage declaration
        names its stage as the site.
        """
        plain = _workflow_doc(catalog={"reviewer": WorkflowAssistant(name="reviewer", prompt="Review.")})
        with pytest.raises(
            ValueError,
            match=r"assistant reviewer at workflow.assistants resolved no agent: set its agent or a global agent",
        ):
            write_afm_config(None, _flow_doc(members=[_member("reviewer")]), plain)

        env_declaring = _workflow_doc(
            catalog={"reviewer": WorkflowAssistant(name="reviewer", prompt="Review.", env={"REVIEW_MODE": "strict"})},
        )
        with pytest.raises(
            ValueError,
            match=(
                r"assistant reviewer at workflow.assistants declares env but "
                r"resolved no agent: set its agent or a global agent"
            ),
        ):
            write_afm_config(None, _flow_doc(members=[_member("reviewer")]), env_declaring)

        inline = _workflow_doc(
            stages={"verify": WorkflowStage(assistants=[WorkflowAssistant(name="security", prompt="Audit.")])},
        )
        with pytest.raises(
            ValueError,
            match=r"assistant security at workflow.stages.verify resolved no agent: set its agent or a global agent",
        ):
            write_afm_config(None, _flow_doc(stage_attachments={"verify": [_attachment("security")]}), inline)

        assert not config_path.exists()
        assert list(closure_base.glob("*")) == []

    def test_afm_config_unknown_reference_in_compiled_flow_raises(self, config_path: Path) -> None:
        """The defensive branch — a flow referencing an undeclared name is a pre-run error."""
        workflow = _workflow_doc(catalog={"reviewer": WorkflowAssistant(name="reviewer", prompt="Review.")})

        with pytest.raises(ValueError, match=r"unknown assistant reference in the compiled flow: ghost"):
            write_afm_config("claude", _flow_doc(members=[_member("ghost")]), workflow)

        assert not config_path.exists()

    def test_write_afm_config_repeated_invocation_safe(self, config_path: Path, closure_base: Path) -> None:
        """Two consecutive writes replace the document wholesale and regenerate the closures."""
        workflow = _workflow_doc(
            catalog={
                "reviewer": WorkflowAssistant(
                    name="reviewer", prompt="Review.", agent="codex", env={"REVIEW_MODE": "strict"}
                )
            },
        )
        flow = _flow_doc(members=[_member("reviewer")])

        write_afm_config("codex", flow, workflow)
        first = config_path.read_text()
        closure = closure_base / "goga-reviewer"
        first_closure = closure.read_text()

        closure.write_text(first_closure + "# stale appended content\n")

        write_afm_config("codex", flow, workflow)

        assert config_path.read_text() == first
        assert closure.read_text() == first_closure

    def test_kill_switch_never_touched(self, config_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """The collaboration kill-switch is neither read nor written."""
        monkeypatch.delenv("AFM_COLLABORATION", raising=False)

        workflow = _workflow_doc(catalog={"reviewer": WorkflowAssistant(name="reviewer", prompt="Review.")})
        write_afm_config("claude", _flow_doc(members=[_member("reviewer")]), workflow)

        collaboration = yaml.safe_load(config_path.read_text())["collaboration"]
        assert "enabled" not in collaboration

        source = inspect.getsource(_afm_config_module)
        assert "os.environ" not in source
        assert "AFM_COLLABORATION" not in source


def _write_chain_inputs(tmp_path: Path, stage_names: list[str], workflow_text: str) -> Path:
    """Write one pipeline-file (the named stages) and the workflow-file; return the workflow path."""
    body = "".join(f"{name}:\n  title: {name.title()}\n  prompt: Do {name}.\n" for name in stage_names)
    pipeline_path = tmp_path / "pipeline.yml"
    pipeline_path.write_text(f"name: demo\ndescription: Demo pipeline\n---\n{body}")

    workflow_path = tmp_path / "workflow.yml"
    workflow_path.write_text(workflow_text)

    return workflow_path


class TestCollaborationDeliveryIntegration:
    """Integration: the compile → serialize → config-write chain on real artifacts.

    Drives the pure chain exactly as ``run_pipeline`` orders it — parse the
    workflow-file, merge the CLI skip directives, compile, serialize, and hand
    BOTH compiled artifacts to the configuration write — and proves the two
    end-to-end invariants no single cell can see: a skipped stage attaches
    nothing and leaves no dead profile behind, and a cross-stage reference
    resolves to another stage's inline declaration all the way into the
    engine configuration (the no-agent error names the declaring stage).
    """

    def test_compile_skipped_stage_attaches_nothing_and_leaves_no_profile(
        self, tmp_path: Path, config_path: Path, closure_base: Path
    ) -> None:
        """A CLI-skipped stage disappears with its attachments — no dead profile remains.

        The catalog declares ``reviewer`` and BOTH stages attach it; ``build``
        is skipped. The flow-file carries no ``build`` stage and its
        ``assistants:`` entries live only under ``verify``; the configuration
        materializes exactly one profile — the team member and the surviving
        attachment collapse into the single ``goga-reviewer`` id.
        """
        workflow_path = _write_chain_inputs(
            tmp_path,
            ["build", "verify"],
            "assistants:\n"
            "  - name: reviewer\n"
            "    prompt: Review.\n"
            "    skills: [code-audit]\n"
            "stages:\n"
            "  build:\n"
            "    assistants: [reviewer]\n"
            "  verify:\n"
            "    assistants: [reviewer]\n",
        )
        workflow = parse_workflow(workflow_path.read_text())

        skipped = apply_skip_stages(workflow, ["build"])
        _pipeline_doc, flow_doc = compile_flow(tmp_path / "pipeline.yml", tmp_path / "flow.yml", workflow=skipped)
        text = serialize_flow(flow_doc)

        assert text == (tmp_path / "flow.yml").read_text()

        loaded = yaml.safe_load(text)

        assert [stage["id"] for stage in loaded["stages"]] == ["verify"]
        assert text.count("  assistants:") == 1
        assert "assistants" in loaded["stages"][0]
        assert [entry["profile"] for entry in loaded["stages"][0]["assistants"]] == ["goga-reviewer"]

        write_afm_config("claude", flow_doc, skipped)

        profiles = yaml.safe_load(config_path.read_text())["collaboration"]["profiles"]

        assert list(profiles) == ["goga-reviewer"]
        assert profiles["goga-reviewer"]["command"] == "/home/goga/bin/claude-as-claude.sh"
        assert list(closure_base.glob("*")) == []

    def test_cross_stage_namespace_resolves_through_full_chain(
        self, tmp_path: Path, config_path: Path, closure_base: Path
    ) -> None:
        """A reference to another stage's inline declaration resolves through the whole chain.

        Stage ``prepare`` declares ``security`` inline; stage ``check``
        references it. Both serialized stages carry the declaration's
        instruction, the configuration materializes exactly the one
        ``goga-security`` profile, and — with no agent resolvable — the
        pre-run error names the DECLARING stage as the site
        (``workflow.stages.prepare``).
        """
        workflow_path = _write_chain_inputs(
            tmp_path,
            ["prepare", "check"],
            "stages:\n"
            "  prepare:\n"
            "    assistants:\n"
            "      - name: security\n"
            "        prompt: Audit the diff.\n"
            "  check:\n"
            "    assistants: [security]\n",
        )
        workflow = parse_workflow(workflow_path.read_text())

        _pipeline_doc, flow_doc = compile_flow(tmp_path / "pipeline.yml", tmp_path / "flow.yml", workflow=workflow)
        text = serialize_flow(flow_doc)

        loaded = yaml.safe_load(text)

        assert [entry["profile"] for entry in loaded["stages"][0]["assistants"]] == ["goga-security"]
        assert [entry["profile"] for entry in loaded["stages"][1]["assistants"]] == ["goga-security"]
        assert all(entry["instruction"] == "Audit the diff." for entry in loaded["stages"][0]["assistants"])

        write_afm_config("claude", flow_doc, workflow)

        profiles = yaml.safe_load(config_path.read_text())["collaboration"]["profiles"]

        assert list(profiles) == ["goga-security"]
        assert profiles["goga-security"]["title"] == "security"

        config_path.unlink()

        with pytest.raises(
            ValueError,
            match=r"assistant security at workflow.stages.prepare resolved no agent: set its agent or a global agent",
        ):
            write_afm_config(None, flow_doc, workflow)

        assert not config_path.exists()
