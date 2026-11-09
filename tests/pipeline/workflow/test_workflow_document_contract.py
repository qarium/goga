"""Contract tests for the ``WorkflowDocument`` dataclass.

Verifies the public API declared by the workflow-cell CODEMANIFEST:
importability from the facade, the declared properties (``prompt``,
``stages``, ``extend``, ``memory``, ``profile``, ``build``, ``assistants``,
and ``delegation``), the ``prompt=None`` / ``stages={}`` / ``extend={}`` /
``memory=None`` / ``profile=None`` / ``build=None`` / ``assistants={}`` /
``delegation=None`` / ``repeat=None`` / ``gates=None`` defaults (the
factories are applied at construction, so the default
``stages``/``extend``/``assistants`` are empty dicts, not None),
the fixed ten-field order with the collaboration fields followed by the
tuning blocks last, and kw_only construction with explicit stages and
extend maps. These tests pin the contract surface — behavior lives in the
logic test module.
"""

from __future__ import annotations

import dataclasses

from goga.pipeline.workflow import (
    WorkflowAssistant,
    WorkflowBuild,
    WorkflowDelegation,
    WorkflowDocument,
    WorkflowExtendStage,
    WorkflowGates,
    WorkflowMemory,
    WorkflowRepeat,
    WorkflowStage,
)


class TestWorkflowDocumentContract:
    """Contract tests — the public API declared by the workflow-cell CODEMANIFEST."""

    def test_workflow_document_importable_from_facade(self) -> None:
        """WorkflowDocument must be importable from the goga.pipeline.workflow facade."""
        assert WorkflowDocument is not None

    def test_workflow_document_has_profile_property(self) -> None:
        """WorkflowDocument exposes a ``profile`` property defaulting to None.

        The property is the parsed counterpart of the peeked workflow default —
        activation reads the raw text via the peek, not this field; ``None``
        when the workflow-file carries no top-level profile key.
        """
        assert hasattr(WorkflowDocument(), "profile")
        assert WorkflowDocument().profile is None
        assert WorkflowDocument(profile="mixa").profile == "mixa"

    def test_workflow_document_has_build_property(self) -> None:
        """WorkflowDocument exposes a ``build`` property defaulting to None.

        The property carries the six-field build block model (a
        :class:`WorkflowBuild`) consumed by the build path — ``None`` when the
        workflow-file carries no block.
        """
        assert hasattr(WorkflowDocument(), "build")
        assert WorkflowDocument().build is None
        build = WorkflowBuild(agent="codex")
        assert WorkflowDocument(build=build).build is build

    def test_workflow_document_field_order_fixed(self) -> None:
        """Field order is fixed with the gates settings block trailing after ``repeat``.

        prompt, stages, extend, memory, profile, build, assistants,
        delegation, repeat, gates — the canonical top-level key order of
        the workflow-file.
        """
        names = [field.name for field in dataclasses.fields(WorkflowDocument)]

        assert names == [
            "prompt",
            "stages",
            "extend",
            "memory",
            "profile",
            "build",
            "assistants",
            "delegation",
            "repeat",
            "gates",
        ]

    def test_workflow_document_constructible_kw_only_with_profile_and_build(self) -> None:
        """WorkflowDocument accepts profile and build as keyword-only arguments, stored verbatim."""
        build = WorkflowBuild(env={"A": "1"})
        document = WorkflowDocument(profile="mixa", build=build)

        assert document.profile == "mixa"
        assert document.build is build

    def test_workflow_document_has_prompt_property(self) -> None:
        """WorkflowDocument exposes a ``prompt`` property."""
        document = WorkflowDocument(prompt="top-level guidance")

        assert hasattr(document, "prompt")
        assert document.prompt == "top-level guidance"

    def test_workflow_document_has_stages_property(self) -> None:
        """WorkflowDocument exposes a ``stages`` property."""
        document = WorkflowDocument()

        assert hasattr(document, "stages")

    def test_workflow_document_default_prompt_is_none(self) -> None:
        """The default ``prompt`` is None when constructed with no arguments."""
        document = WorkflowDocument()

        assert document.prompt is None

    def test_workflow_document_default_stages_is_empty_dict(self) -> None:
        """The default ``stages`` is an empty dict — the factory is applied at construction."""
        document = WorkflowDocument()

        assert document.stages == {}
        # Factory default, not the None DSL representation.
        assert document.stages is not None

    def test_workflow_document_constructible_kw_only_with_explicit_stages(self) -> None:
        """WorkflowDocument accepts prompt and stages as keyword-only arguments."""
        stages = {"propose": WorkflowStage(agent="codex")}
        document = WorkflowDocument(prompt="guidance", stages=stages)

        assert document.prompt == "guidance"
        assert document.stages == stages
        assert document.stages["propose"].agent == "codex"

    def test_workflow_document_has_extend_property(self) -> None:
        """WorkflowDocument exposes an ``extend`` property."""
        document = WorkflowDocument()

        assert hasattr(document, "extend")

    def test_workflow_document_default_extend_is_empty_dict(self) -> None:
        """The default ``extend`` is an empty dict — the factory is applied at construction."""
        document = WorkflowDocument()

        assert document.extend == {}
        # Factory default, not the None DSL representation.
        assert document.extend is not None

    def test_workflow_document_constructible_kw_only_with_explicit_extend(self) -> None:
        """WorkflowDocument accepts extend as a keyword-only argument and stores the map."""
        extend = {"extra": WorkflowExtendStage(after=["review"], body={"title": "Extra"})}
        document = WorkflowDocument(prompt="guidance", stages={}, extend=extend, memory=None)

        assert set(document.extend) == {"extra"}
        assert document.extend["extra"].after == ["review"]
        assert document.extend["extra"].body == {"title": "Extra"}
        assert document.memory is None

    def test_workflow_document_has_memory_property(self) -> None:
        """WorkflowDocument exposes a ``memory`` property defaulting to None."""
        assert hasattr(WorkflowDocument(), "memory")
        assert WorkflowDocument().memory is None
        assert WorkflowDocument(memory=WorkflowMemory()).memory == WorkflowMemory()

    def test_workflow_document_memory_defaults_to_none(self) -> None:
        """The default ``memory`` is None — no workflow-memory block was authored."""
        document = WorkflowDocument()

        assert document.memory is None
        # A document built with stages/extend and no memory keeps the default.
        assert WorkflowDocument(stages={"build": WorkflowStage()}).memory is None
        assert WorkflowDocument(extend={"x": WorkflowExtendStage(body={})}).memory is None

    def test_workflow_document_constructible_kw_only_with_memory(self) -> None:
        """WorkflowDocument accepts memory as a keyword-only argument, stored verbatim."""
        memory = WorkflowMemory(method="alignment", path="goga-development")
        document = WorkflowDocument(memory=memory)

        assert document.memory is memory
        assert document.memory == WorkflowMemory(method="alignment", path="goga-development")

    def test_workflow_document_has_assistants_property(self) -> None:
        """WorkflowDocument exposes an ``assistants`` property defaulting to an empty dict.

        The property carries the assistant catalog (a map of assistant name →
        :class:`WorkflowAssistant`, authored order) extracted from the
        top-level ``assistants`` block; the default is an empty dict applied
        by the factory at construction, not ``None``.
        """
        assert hasattr(WorkflowDocument(), "assistants")
        assert WorkflowDocument().assistants == {}
        assert WorkflowDocument().assistants is not None

        catalog = {"reviewer": WorkflowAssistant(name="reviewer", prompt="Review.")}
        assert WorkflowDocument(assistants=catalog).assistants is catalog

    def test_workflow_document_has_delegation_property(self) -> None:
        """WorkflowDocument exposes a ``delegation`` property defaulting to None.

        The property carries the delegation block (a
        :class:`WorkflowDelegation` with materialized defaults) or ``None``
        when the workflow-file carries no block.
        """
        assert hasattr(WorkflowDocument(), "delegation")
        assert WorkflowDocument().delegation is None
        delegation = WorkflowDelegation(depth=2)
        assert WorkflowDocument(delegation=delegation).delegation is delegation

    def test_workflow_document_has_repeat_property(self) -> None:
        """WorkflowDocument exposes a ``repeat`` property defaulting to None.

        The property carries the run-cycle tuning block (a
        :class:`WorkflowRepeat` with authored values only) or ``None`` when
        the workflow-file carries no block or authors an empty block.
        """
        assert hasattr(WorkflowDocument(), "repeat")
        assert WorkflowDocument().repeat is None
        repeat = WorkflowRepeat(max_cycles=2)
        assert WorkflowDocument(repeat=repeat).repeat is repeat

    def test_workflow_document_has_gates_property(self) -> None:
        """WorkflowDocument exposes a ``gates`` property defaulting to None.

        The property carries the workflow quality-gate settings block (a
        :class:`WorkflowGates` with authored values only) or ``None`` when
        the workflow-file carries no block or authors an empty block; it is
        the LAST field of the fixed canonical order and is stored verbatim.
        """
        assert hasattr(WorkflowDocument(), "gates")
        assert WorkflowDocument().gates is None
        gates = WorkflowGates(max_iterations=1)
        assert WorkflowDocument(gates=gates).gates is gates
