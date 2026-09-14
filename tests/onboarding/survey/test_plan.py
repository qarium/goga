"""Contract and logic tests for the entities declared in
``goga/onboarding/survey/CODEMANIFEST`` with ``location: plan.py``:

- ``SessionPlan(root, tools)`` — the assembled survey plan record
- ``assemble_session_plan(core, declarations)`` — the assembly of the plan
  with the tool question blocks
- ``apply_skips(plan, skips)`` — the removal of the addressed subtrees

The plan layer is pure transformation: the core tree is never mutated, the
tool blocks join the core children in enumeration order under the
reserved-name and local-name guards, and the skips resolve against the
original tree and apply as one order-independent set.
"""

from __future__ import annotations

import logging

import pytest
from goga.onboarding.participation import ToolDeclaration
from goga.onboarding.questions import Question, QuestionGroup
from goga.onboarding.survey import SessionPlan, apply_skips, assemble_session_plan

_CELL_ALL = ["Questionnaire", "SessionPlan", "apply_skips", "assemble_session_plan", "core_questions"]


def _core(*children: Question | QuestionGroup) -> QuestionGroup:
    """Build a minimal core root carrying the given sections."""
    return QuestionGroup(id="core", children=list(children))


def _declaration(
    tool: str,
    *items: Question | QuestionGroup,
    skips: list[str] | None = None,
) -> ToolDeclaration:
    """Build one delivered declaration of a tool — items declared, skips buffered."""
    surface = ToolDeclaration(tool=tool, invited=True)
    for item in items:
        surface.declare(item)
    for path in skips or []:
        surface.skip(path)
    return surface


def _child_ids(group: QuestionGroup) -> list[str]:
    """List the local names of the group's children."""
    return [child.id for child in group.children or []]


def _block(root: QuestionGroup, tool: str) -> QuestionGroup:
    """Return the tool block group of one plan root."""
    return next(child for child in root.children if child.id == tool)


def _reachable_ids(node: Question | QuestionGroup) -> set[str]:
    """Collect every id of the subtree under the node, the node's included."""
    ids = {node.id}
    if isinstance(node, QuestionGroup):
        for child in node.children or []:
            ids |= _reachable_ids(child)
    return ids


# --- Contract tests ---


class TestPlanContract:
    def test_entities_are_importable_from_the_package_facade(self) -> None:
        """The three plan names live on the cell package; ``__all__`` is exact."""
        import goga.onboarding.survey as cell

        assert cell.SessionPlan is SessionPlan
        assert cell.assemble_session_plan is assemble_session_plan
        assert cell.apply_skips is apply_skips
        assert cell.__all__ == _CELL_ALL

    def test_assemble_of_a_bare_core_returns_the_plan_record(self) -> None:
        """``assemble_session_plan(core, [])`` — the core children, no tools."""
        core = _core(Question(id="language", kind="choice", prompt="Language"))

        plan = assemble_session_plan(core, [])

        assert isinstance(plan, SessionPlan)
        assert plan.root.id == "session"
        assert _child_ids(plan.root) == ["language"]
        assert plan.root.children == core.children
        assert plan.tools == []


# --- Logic tests ---


class TestAssembleSessionPlan:
    def test_assemble_session_plan_orders_blocks_and_drops_repeats(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Blocks follow the core in enumeration order; a repeat drops singly."""
        core = _core(
            Question(id="language", kind="choice", prompt="Language"),
            Question(id="tools", kind="pairs", prompt="Tools"),
        )
        my_tool = _declaration(
            "my-tool",
            Question(id="token", kind="input", prompt="Token one"),
            Question(id="token", kind="input", prompt="Token two"),
        )
        viewer = _declaration("viewer", Question(id="flag", kind="confirm", prompt="Flag"))
        empty_tool = _declaration("empty-tool")

        with caplog.at_level(logging.WARNING):
            plan = assemble_session_plan(core, [my_tool, viewer, empty_tool])

        assert _child_ids(plan.root) == ["language", "tools", "my-tool", "viewer"]
        assert plan.tools == ["my-tool", "viewer"]
        assert _child_ids(_block(plan.root, "my-tool")) == ["token"]
        assert _block(plan.root, "my-tool").prompt == "--- Tool: my-tool ---"
        assert any("my-tool" in record.message for record in caplog.records)

    def test_assemble_reserved_name_drops_block(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A tool identity colliding with a core section name contributes no block."""
        core = _core(
            Question(id="language", kind="choice", prompt="Language"),
            Question(id="tools", kind="pairs", prompt="Tools"),
        )
        colliding = _declaration("tools", Question(id="token", kind="input", prompt="Token"))

        with caplog.at_level(logging.WARNING):
            plan = assemble_session_plan(core, [colliding])

        assert plan.tools == []
        assert _child_ids(plan.root) == ["language", "tools"]
        assert any("tools" in record.message for record in caplog.records)

    def test_reserved_names_derive_from_the_received_core(self) -> None:
        """No hardcoded name list — a core without the section admits the name."""
        core = _core(Question(id="language", kind="choice", prompt="Language"))
        named = _declaration("tools", Question(id="token", kind="input", prompt="Token"))

        plan = assemble_session_plan(core, [named])

        assert _child_ids(plan.root) == ["language", "tools"]
        assert plan.tools == ["tools"]

    def test_the_core_tree_is_never_mutated(self) -> None:
        """Assembly builds a fresh root over fresh containers; frozen records shared."""
        language = Question(id="language", kind="choice", prompt="Language")
        core = _core(language)
        declaration = _declaration("my-tool", Question(id="token", kind="input", prompt="Token"))

        plan = assemble_session_plan(core, [declaration])

        assert plan.root is not core
        assert plan.root.id == "session"
        assert _child_ids(core) == ["language"]
        assert plan.root.children[0] is language


class TestApplySkips:
    def _plan(self) -> SessionPlan:
        """Build the reference plan — core language/build, blocks my-tool/viewer."""
        core = _core(
            Question(id="language", kind="choice", prompt="Language"),
            QuestionGroup(
                id="build",
                prompt="--- Build ---",
                children=[
                    Question(id="agent", kind="choice", prompt="Build agent"),
                    Question(id="env", kind="pairs", prompt="Build environment variables"),
                ],
            ),
        )
        my_tool = _declaration(
            "my-tool",
            QuestionGroup(
                id="reporting",
                children=[Question(id="enabled", kind="confirm", prompt="Enable reporting")],
            ),
        )
        viewer = _declaration("viewer", Question(id="opt", kind="confirm", prompt="Opt in"))
        return assemble_session_plan(core, [my_tool, viewer])

    def test_apply_skips_prefixed_own_and_unknown(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Own-block, tool-prefixed, core, and unknown paths resolve per the rule."""
        skips = [
            ("my-tool", "reporting.enabled"),
            ("viewer", "my-tool.reporting.enabled"),
            ("viewer", "language"),
            ("my-tool", "no.such.path"),
        ]

        with caplog.at_level(logging.WARNING):
            pruned = apply_skips(self._plan(), skips)

        assert _child_ids(pruned.root) == ["build", "my-tool", "viewer"]
        assert pruned.tools == ["my-tool", "viewer"]

        my_tool_block = _block(pruned.root, "my-tool")

        assert _child_ids(my_tool_block) == ["reporting"]
        assert my_tool_block.children[0].children == []
        assert "enabled" not in _reachable_ids(my_tool_block)
        assert any("no.such.path" in record.message for record in caplog.records)

    def test_reversed_skip_order_yields_the_same_plan(self) -> None:
        """The skips apply as one set — the order never matters."""
        skips = [
            ("my-tool", "reporting.enabled"),
            ("viewer", "my-tool.reporting.enabled"),
            ("viewer", "language"),
            ("my-tool", "no.such.path"),
        ]

        forward = apply_skips(self._plan(), skips)
        backward = apply_skips(self._plan(), list(reversed(skips)))

        assert forward.root == backward.root
        assert forward.tools == backward.tools

    def test_an_emptied_block_stays_in_the_plan(self) -> None:
        """Skipping the whole content of a block empties it — the block stays."""
        pruned = apply_skips(self._plan(), [("my-tool", "reporting")])

        assert _child_ids(pruned.root) == ["language", "build", "my-tool", "viewer"]
        assert _block(pruned.root, "my-tool").children == []
        assert pruned.tools == ["my-tool", "viewer"]

    def test_unmodified_branches_share_the_frozen_originals(self) -> None:
        """Rebuild only along removed branches; the untouched originals are shared."""
        plan = self._plan()
        build = plan.root.children[1]
        my_tool_block = plan.root.children[2]
        viewer = plan.root.children[3]

        pruned = apply_skips(plan, [("viewer", "language")])

        assert pruned.root is not plan.root
        assert _child_ids(pruned.root) == ["build", "my-tool", "viewer"]
        assert pruned.root.children[0] is build
        assert pruned.root.children[1] is my_tool_block
        assert pruned.root.children[2] is viewer

    def test_a_core_section_name_wins_over_the_own_block_local(self) -> None:
        """The resolution order — tool identity, core section, then own block."""
        core = _core(
            Question(id="language", kind="choice", prompt="Language"),
            QuestionGroup(id="build", prompt="--- Build ---"),
        )
        my_tool = _declaration("my-tool", Question(id="language", kind="input", prompt="Local"))
        plan = assemble_session_plan(core, [my_tool])

        pruned = apply_skips(plan, [("my-tool", "language")])

        assert _child_ids(pruned.root) == ["build", "my-tool"]
        assert _child_ids(_block(pruned.root, "my-tool")) == ["language"]

    def test_a_path_into_a_pairs_question_is_a_noop_warning(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Inside a pairs question the pairs are not addressable — only the node."""
        core = _core(
            Question(id="language", kind="choice", prompt="Language"),
            Question(id="tools", kind="pairs", prompt="Tools"),
        )
        plan = assemble_session_plan(core, [])

        with caplog.at_level(logging.WARNING):
            pruned = apply_skips(plan, [("my-tool", "tools.goga-lint")])

        assert _child_ids(pruned.root) == ["language", "tools"]
        assert any("tools.goga-lint" in record.message for record in caplog.records)

    def test_a_skip_from_a_tool_without_a_block_is_a_noop_warning(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A tool that declared no questions carries no own block — no local resolves."""
        plan = assemble_session_plan(
            _core(Question(id="language", kind="choice", prompt="Language")),
            [_declaration("silent-tool"), _declaration("viewer", Question(id="opt", kind="confirm", prompt="Opt in"))],
        )

        with caplog.at_level(logging.WARNING):
            pruned = apply_skips(plan, [("silent-tool", "opt")])

        assert _child_ids(pruned.root) == ["language", "viewer"]
        assert _child_ids(_block(pruned.root, "viewer")) == ["opt"]
        assert any("opt" in record.message for record in caplog.records)
        assert any("own-block element" in record.message for record in caplog.records)

    def test_a_resolved_path_reaching_no_node_is_a_noop_warning(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A well-prefixed own-block path whose deeper segments miss warns and stands."""
        plan = self._plan()

        with caplog.at_level(logging.WARNING):
            pruned = apply_skips(plan, [("my-tool", "reporting.nonexistent")])

        assert _child_ids(pruned.root) == ["language", "build", "my-tool", "viewer"]
        assert _child_ids(_block(pruned.root, "my-tool")) == ["reporting"]
        assert any("reporting.nonexistent" in record.message for record in caplog.records)
        assert any("reaches no node" in record.message for record in caplog.records)

    def test_a_descendant_of_a_skipped_node_is_absorbed_silently(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Set semantics — the descendant resolves against the original tree."""
        with caplog.at_level(logging.WARNING):
            pruned = apply_skips(self._plan(), [("viewer", "build"), ("viewer", "build.env")])

        assert _child_ids(pruned.root) == ["language", "my-tool", "viewer"]
        assert not caplog.records
