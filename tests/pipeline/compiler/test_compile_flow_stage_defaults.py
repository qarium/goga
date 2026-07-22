"""Behavioral tests for the default stage-field injection in ``compile_flow``.

Covers the user-requested extension: when a pipeline-DSL stage lacks a usable
``agents`` value (key absent, ``null``, or empty list), the compiler injects a
single default into the assembled ``FlowStage.fields``:

- ``agents=["auto"]``

An authored non-empty ``agents`` always wins — no injection happens.
``supervisor``/``supervisor_prompt`` are authored-only — never injected, but
they pass through the canonical slot when the source body carries them. The
injection lives in ``FlowStage`` assembly only — ``PipelineDocument.body``
returned to consumers stays a faithful mirror of the source pipeline-file.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from goga.pipeline.compiler import compile_flow
from goga.pipeline.workflow import WorkflowDocument, WorkflowStage


class TestStageDefaultsInjection:
    """When ``agents`` is missing or empty, the single default is injected."""

    def test_phases_stage_without_agents_gets_defaults(self, tmp_path: Path) -> None:
        """A PHASES stage with no ``agents`` key gets the single default field."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n  prompt: Do A\n",
        )
        flow_path = tmp_path / "flow.yml"

        _, flow_doc = compile_flow(pipeline_path, flow_path)

        fields = flow_doc.stages[0].fields
        assert fields["agents"] == ["auto"]
        assert "supervisor" not in fields
        assert "supervisor_prompt" not in fields

    def test_stages_stage_without_agents_gets_defaults(self, tmp_path: Path) -> None:
        """A STAGES stage with no ``agents`` key gets the single default field."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\na:\n  title: A\n  prompt: Do A\n",
        )
        flow_path = tmp_path / "flow.yml"

        _, flow_doc = compile_flow(pipeline_path, flow_path)

        fields = flow_doc.stages[0].fields
        assert fields["agents"] == ["auto"]
        assert "supervisor" not in fields
        assert "supervisor_prompt" not in fields

    def test_stage_with_empty_agents_gets_defaults(self, tmp_path: Path) -> None:
        """``agents: []`` triggers default injection — empty list is unusable."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n  agents: []\n",
        )
        flow_path = tmp_path / "flow.yml"

        _, flow_doc = compile_flow(pipeline_path, flow_path)

        fields = flow_doc.stages[0].fields
        assert fields["agents"] == ["auto"]
        assert "supervisor" not in fields
        assert "supervisor_prompt" not in fields

    def test_stage_with_null_agents_gets_defaults(self, tmp_path: Path) -> None:
        """``agents: null`` (explicit YAML null) triggers default injection."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n  agents: null\n",
        )
        flow_path = tmp_path / "flow.yml"

        _, flow_doc = compile_flow(pipeline_path, flow_path)

        fields = flow_doc.stages[0].fields
        assert fields["agents"] == ["auto"]
        assert "supervisor" not in fields
        assert "supervisor_prompt" not in fields

    def test_compile_flow_default_agents_is_auto_only(self, tmp_path: Path) -> None:
        """A pipeline stage without ``agents`` gets ONLY ``agents=["auto"]``.

        Pins the single-default contract: ``agents`` is ``["auto"]``, no
        ``supervisor``/``supervisor_prompt`` are injected, and the serialized
        flow-file text carries ``agents: [auto]``.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n  prompt: Do A\n",
        )
        flow_path = tmp_path / "flow.yml"

        _, flow_doc = compile_flow(pipeline_path, flow_path)

        fields = flow_doc.stages[0].fields
        assert fields["agents"] == ["auto"]
        assert "supervisor" not in fields
        assert "supervisor_prompt" not in fields
        assert "agents: [auto]" in flow_path.read_text()


class TestStageDefaultsRespectAuthored:
    """An authored non-empty ``agents`` value disables default injection."""

    def test_stage_with_single_agent_no_defaults(self, tmp_path: Path) -> None:
        """``agents: [foo]`` is preserved verbatim; no defaults are injected."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n  agents:\n    - foo\n",
        )
        flow_path = tmp_path / "flow.yml"

        _, flow_doc = compile_flow(pipeline_path, flow_path)

        fields = flow_doc.stages[0].fields
        assert fields["agents"] == ["foo"]
        assert "supervisor" not in fields
        assert "supervisor_prompt" not in fields

    def test_stage_with_multiple_agents_no_defaults(self, tmp_path: Path) -> None:
        """``agents: [planning, implementation]`` is preserved; no defaults."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n  agents:\n    - planning\n    - implementation\n",
        )
        flow_path = tmp_path / "flow.yml"

        _, flow_doc = compile_flow(pipeline_path, flow_path)

        fields = flow_doc.stages[0].fields
        assert fields["agents"] == ["planning", "implementation"]
        assert "supervisor" not in fields
        assert "supervisor_prompt" not in fields

    def test_compile_flow_authored_agents_disables_injection(self, tmp_path: Path) -> None:
        """An authored non-empty ``agents`` value disables the single injection.

        Authored input (``agents: [foo]``) is non-empty → injection does not
        fire, so the source value survives and no ``supervisor``/``agents=[auto]``
        injection appears.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n  agents:\n    - foo\n",
        )
        flow_path = tmp_path / "flow.yml"

        _, flow_doc = compile_flow(pipeline_path, flow_path)

        fields = flow_doc.stages[0].fields
        assert fields["agents"] == ["foo"]
        assert "supervisor" not in fields

    def test_compile_flow_supervisor_authored_passes_through(self, tmp_path: Path) -> None:
        """Authored ``supervisor``/``supervisor_prompt`` pass through (not injected).

        With no usable ``agents`` the single ``agents=["auto"]`` default is still
        injected, but the authored ``supervisor``/``supervisor_prompt`` are
        authored-only and pass through the canonical slot in the order
        ``agents < supervisor < supervisor_prompt < skills``.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n"
            "- name: a\n"
            "  title: A\n"
            "  skills:\n"
            "    - goga-propose\n"
            "  supervisor: true\n"
            "  supervisor_prompt: Drive this autonomously\n",
        )
        flow_path = tmp_path / "flow.yml"

        _, flow_doc = compile_flow(pipeline_path, flow_path)

        fields = flow_doc.stages[0].fields
        # Single-default injection still fires (no usable authored agents).
        assert fields["agents"] == ["auto"]
        # Authored-only fields pass through verbatim.
        assert fields["supervisor"] is True
        assert fields["supervisor_prompt"] == "Drive this autonomously"
        # Canonical order: agents < supervisor < supervisor_prompt < skills.
        assert list(fields.keys()) == [
            "agents",
            "supervisor",
            "supervisor_prompt",
            "skills",
        ]


class TestStageDefaultsCanonicalOrder:
    """The injected default lands in the canonical key order between agents and skills."""

    def test_defaults_and_skills_canonical_order(self, tmp_path: Path) -> None:
        """When the default is injected and the source carries skills, the order
        is ``agents < skills`` in the serialized flow-file."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n  skills:\n    - goga-propose\n",
        )
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)

        text = flow_path.read_text()
        idx_agents = text.index("agents:")
        idx_skills = text.index("skills:")
        assert idx_agents < idx_skills

    def test_defaults_round_trip_through_yaml(self, tmp_path: Path) -> None:
        """The injected default survives a YAML round-trip with the expected type."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n",
        )
        flow_path = tmp_path / "flow.yml"

        compile_flow(pipeline_path, flow_path)

        loaded = yaml.safe_load(flow_path.read_text())
        stage = loaded["stages"][0]
        assert stage["agents"] == ["auto"]
        assert "supervisor" not in stage
        assert "supervisor_prompt" not in stage


class TestStageDefaultsDoNotLeak:
    """The injection is local to ``FlowStage.fields`` — ``PipelineDocument.body``
    is never affected."""

    def test_pipeline_document_body_has_no_agents_when_source_had_none(self, tmp_path: Path) -> None:
        """A source stage without ``agents`` keeps the parsed body clean."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n  prompt: Do A\n",
        )
        flow_path = tmp_path / "flow.yml"

        pipeline_doc, _ = compile_flow(pipeline_path, flow_path)

        body = pipeline_doc.body.steps[0].body
        assert "agents" not in body
        assert "supervisor" not in body
        assert "supervisor_prompt" not in body

    def test_pipeline_document_body_preserves_empty_agents(self, tmp_path: Path) -> None:
        """``agents: []`` in the source stays ``[]`` in the parsed body —
        default injection does not retroactively populate it."""
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: a\n  title: A\n  agents: []\n",
        )
        flow_path = tmp_path / "flow.yml"

        pipeline_doc, _ = compile_flow(pipeline_path, flow_path)

        body = pipeline_doc.body.steps[0].body
        assert body["agents"] == []
        assert "supervisor" not in body
        assert "supervisor_prompt" not in body


class TestStageDefaultsHelper:
    """Direct unit tests for the private ``_inject_defaults`` helper."""

    def test_inject_when_agents_missing(self) -> None:
        from goga.pipeline.compiler.compile_flow import _inject_defaults

        body = {"prompt": "Do A"}
        injected = _inject_defaults(body)

        assert injected["agents"] == ["auto"]
        assert injected["prompt"] == "Do A"
        # The source body is not mutated.
        assert "agents" not in body

    def test_no_inject_when_agents_non_empty(self) -> None:
        from goga.pipeline.compiler.compile_flow import _inject_defaults

        body = {"agents": ["foo"]}
        injected = _inject_defaults(body)

        assert injected["agents"] == ["foo"]
        assert "supervisor" not in injected
        assert "supervisor_prompt" not in injected

    def test_inject_when_agents_empty_list(self) -> None:
        from goga.pipeline.compiler.compile_flow import _inject_defaults

        body = {"agents": []}
        injected = _inject_defaults(body)

        assert injected["agents"] == ["auto"]
        assert "supervisor" not in injected
        assert "supervisor_prompt" not in injected

    def test_inject_when_agents_null(self) -> None:
        from goga.pipeline.compiler.compile_flow import _inject_defaults

        body = {"agents": None}
        injected = _inject_defaults(body)

        assert injected["agents"] == ["auto"]
        assert "supervisor" not in injected
        assert "supervisor_prompt" not in injected

    def test_returns_independent_dict(self) -> None:
        """The returned dict is not aliased to the input — caller mutation is safe."""
        from goga.pipeline.compiler.compile_flow import _inject_defaults

        body = {"prompt": "Do A"}
        injected = _inject_defaults(body)
        injected["agents"].append("hacked")

        assert body == {"prompt": "Do A"}

    def test_inject_defaults_helper_returns_auto(self) -> None:
        """Direct ``_inject_defaults`` returns ONLY ``agents=["auto"]``.

        Pins the single-default contract at the helper level: no
        ``supervisor``/``supervisor_prompt`` keys appear in the injected dict,
        and the source body stays clean.
        """
        from goga.pipeline.compiler.compile_flow import _inject_defaults

        body = {"prompt": "x"}
        injected = _inject_defaults(body)

        assert injected["agents"] == ["auto"]
        assert "supervisor" not in injected
        assert "supervisor_prompt" not in injected
        # The source body is untouched.
        assert "agents" not in body


class TestStageDefaultsCoexistWithWorkflowOverride:
    """Workflow overrides and default injection coexist in the same stage."""

    def test_workflow_agent_and_prompt_coexist_with_defaults(self, tmp_path: Path) -> None:
        """A pipeline-stage without ``agents`` + workflow-stage with agent+prompt → both channels populate
        ``FlowStage.fields``.

        The workflow-override branch (step 4a in the algorithm) injects ``command``
        and ``description`` into the step body. The default-injection branch (step 5
        via ``_canonical_fields`` → ``_inject_defaults``) adds the single default
        when the body has no usable ``agents``. This test pins that the two branches
        do not interfere — both channels land in the same ``FlowStage.fields`` dict,
        and the authored body content (``prompt``) survives both.
        """
        pipeline_path = tmp_path / "pipeline.yml"
        pipeline_path.write_text(
            "name: T\ndescription: T\n---\n\n- name: propose\n  title: Propose\n  prompt: Body prompt\n",
        )
        flow_path = tmp_path / "flow.yml"
        workflow = WorkflowDocument(
            stages={"propose": WorkflowStage(agent="codex", prompt="Workflow prompt")},
        )

        _, flow_doc = compile_flow(pipeline_path, flow_path, workflow=workflow)

        fields = flow_doc.stages[0].fields
        # Workflow-override channel (step 4a).
        assert fields["command"] == "/home/goga/bin/codex-as-claude.sh"
        assert fields["description"] == "Workflow prompt"
        # Default-injection channel (step 5 — body has no usable ``agents``).
        assert fields["agents"] == ["auto"]
        assert "supervisor" not in fields
        assert "supervisor_prompt" not in fields
        # Authored body content survives both channels.
        assert fields["prompt"] == "Body prompt"
        # Canonical key order: command (workflow), prompt (authored), description
        # (workflow), then agents (injected); interactive and skills absent because
        # the source body carries neither.
        assert list(fields.keys()) == [
            "command",
            "prompt",
            "description",
            "agents",
        ]
