"""Logic tests for the ``WorkflowExtendStage`` dataclass.

Covers construction behavior beyond the contract surface: partial
construction (one of ``before``/``after`` set, the other ``None``), the
``agent``/``loop``/``approve`` default-override fields (``None`` or a value),
verbatim storage of nested ``body`` values, the ``body`` excluding
``before``/``after``/``agent``/``loop``/``approve``/``depends_on``, and
round-trip equality of identical constructions. The data Entity carries no
behavior — these tests pin its construction semantics.
"""

from __future__ import annotations

from goga.pipeline.workflow import WorkflowExtendStage


class TestWorkflowExtendStageLogic:
    """Logic tests — construction behavior of the ``WorkflowExtendStage`` dataclass."""

    def test_partial_construction_after_only(self) -> None:
        """Specifying only ``after`` leaves the other four fields at None."""
        ext = WorkflowExtendStage(after=["x"], body={})

        assert ext.before is None
        assert ext.after == ["x"]
        assert ext.agent is None
        assert ext.loop is None
        assert ext.body == {}

    def test_partial_construction_before_only(self) -> None:
        """Specifying only ``before`` leaves the other four fields at None."""
        ext = WorkflowExtendStage(before=["x"], body={})

        assert ext.before == ["x"]
        assert ext.after is None
        assert ext.agent is None
        assert ext.loop is None

    def test_partial_construction_agent_only(self) -> None:
        """Specifying only ``agent`` leaves the other four fields at None."""
        ext = WorkflowExtendStage(after=["x"], agent="codex", body={})

        assert ext.after == ["x"]
        assert ext.agent == "codex"
        assert ext.before is None
        assert ext.loop is None

    def test_partial_construction_loop_only(self) -> None:
        """Specifying only ``loop`` leaves the other four fields at None."""
        ext = WorkflowExtendStage(after=["x"], loop=3, body={})

        assert ext.after == ["x"]
        assert ext.loop == 3
        assert ext.before is None
        assert ext.agent is None

    def test_agent_defaults_to_none_when_omitted(self) -> None:
        """Omitting ``agent`` yields None — no default override."""
        ext = WorkflowExtendStage(after=["x"], body={})

        assert ext.agent is None

    def test_loop_defaults_to_none_when_omitted(self) -> None:
        """Omitting ``loop`` yields None — no expansion."""
        ext = WorkflowExtendStage(after=["x"], body={})

        assert ext.loop is None

    def test_approve_defaults_to_none_when_omitted(self) -> None:
        """Omitting ``approve`` yields None — no auto-approval directive."""
        ext = WorkflowExtendStage(after=["x"], body={})

        assert ext.approve is None

    def test_approve_accepts_auto(self) -> None:
        """approve stores ``"auto"`` verbatim (validation lives in parse_workflow)."""
        ext = WorkflowExtendStage(after=["x"], approve="auto", body={})

        assert ext.approve == "auto"

    def test_approve_field_order_before_body(self) -> None:
        """approve sits after loop and before body in the fixed field order."""
        from dataclasses import fields

        names = [field.name for field in fields(WorkflowExtendStage)]

        assert names == ["before", "after", "agent", "loop", "approve", "body"]

    def test_loop_accepts_boundary_one(self) -> None:
        """loop == 1 (the minimum) is accepted by the dataclass itself."""
        ext = WorkflowExtendStage(after=["x"], loop=1, body={})

        assert ext.loop == 1

    def test_body_stores_nested_values_verbatim(self) -> None:
        """A nested ``body`` is stored verbatim — deep structure round-trips unchanged."""
        ext = WorkflowExtendStage(body={"custom": {"deep": 1}, "list": [1, 2, 3]})

        assert ext.body == {"custom": {"deep": 1}, "list": [1, 2, 3]}

    def test_body_excludes_positioning_and_override_keys(self) -> None:
        """``body`` carries only verbatim stage content — no before/after/agent/loop/approve/depends_on.

        These keys never reach ``body``: ``parse_workflow`` extracts
        ``before``/``after``/``agent``/``loop``/``approve`` into named fields and
        rejects ``depends_on`` before the dataclass is built. The model itself
        stores whatever it is given, so this test pins that ``body`` can be
        supplied independently of the five named override/positioning fields.
        """
        ext = WorkflowExtendStage(
            before=["a"],
            after=["b"],
            agent="codex",
            loop=2,
            approve="auto",
            body={"title": "T", "prompt": "go", "skills": ["web-search"]},
        )

        assert ext.body == {"title": "T", "prompt": "go", "skills": ["web-search"]}
        assert "before" not in ext.body
        assert "after" not in ext.body
        assert "agent" not in ext.body
        assert "loop" not in ext.body
        assert "approve" not in ext.body
        assert "depends_on" not in ext.body

    def test_body_keeps_supplied_identity(self) -> None:
        """The supplied ``body`` dict is kept (the dataclass is not frozen)."""
        payload = {"title": "T", "prompt": "go"}
        ext = WorkflowExtendStage(body=payload)

        assert ext.body is payload

    def test_provided_values_round_trip_unchanged(self) -> None:
        """Provided values round-trip verbatim."""
        ext = WorkflowExtendStage(before=["a"], after=["b"], agent="codex", loop=2, body={"title": "T"})

        assert ext.before == ["a"]
        assert ext.after == ["b"]
        assert ext.agent == "codex"
        assert ext.loop == 2
        assert ext.body == {"title": "T"}

    def test_equality_of_identical_constructions(self) -> None:
        """Two extend-stages with identical fields compare equal."""
        first = WorkflowExtendStage(before=["a"], after=["b"], agent="codex", loop=2, body={"title": "T"})
        second = WorkflowExtendStage(before=["a"], after=["b"], agent="codex", loop=2, body={"title": "T"})

        assert first == second
