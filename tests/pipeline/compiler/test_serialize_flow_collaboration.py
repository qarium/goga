"""Contract and logic tests for the collaboration emission of ``serialize_flow``.

Covers the collaboration half of the serializer extension: a non-``None``
``FlowDocument.collaboration`` is emitted between ``memory`` and ``team`` with
the fixed key order ``mode, max_depth`` (``max_depth`` omitted when ``None``
— the omission rule is ``is None``, never truthiness); a non-empty ``team``
list emits the ``team:`` block with each member the ordered mapping ``id,
title, profile, instruction, skills`` (a multi-line ``instruction`` wrapped in
the block-literal marker); the per-stage ``assistants`` field renders as a
list of ordered mappings ``profile, title, instruction, mode, trigger,
skills`` with the same instruction wrapping. ``collaboration=None`` /
``team=None`` / ``team=[]`` omit the keys entirely — byte-identical output for
collaboration-free documents.
"""

from __future__ import annotations

from goga.pipeline.compiler import (
    FlowAssistant,
    FlowCollaboration,
    FlowDocument,
    FlowStage,
    FlowTeamMember,
    serialize_flow,
)

# Golden byte-identity literal for a collaboration-free document — frozen from
# the serializer output BEFORE the collaboration/team branches existed. Any
# leak of the new keys into the output (a block, a key-order shift) changes
# this string.
COLLABORATION_FREE_GOLDEN = (
    "name: demo\n"
    "description: Demo pipeline\n"
    "stages:\n"
    "- id: brainstorm\n"
    "  name: Brainstorm\n"
    "  agents: [auto]\n"
    "  prompt: Think\n"
    "- id: build\n"
    "  name: Build\n"
    "  agents: [auto]\n"
    "  prompt: Make\n"
    "  depends_on:\n"
    "  - brainstorm\n"
)


def _stage(
    stage_id: str,
    name: str,
    fields: dict[str, object],
    depends_on: list[str] | None = None,
) -> FlowStage:
    """Build one ``FlowStage`` with the given fields (mirrors the compile output shape)."""
    return FlowStage(id=stage_id, name=name, depends_on=depends_on, fields=fields)


class TestSerializeFlowCollaborationContract:
    """Contract tests — the collaboration/team emission keys of the serializer."""

    def test_serialize_flow_collaboration_block_emitted_max_depth_omitted_when_none(self) -> None:
        """A ``FlowCollaboration()`` document emits the block with mode only — no ``max_depth`` key."""
        doc = FlowDocument(
            name="n",
            description="d",
            collaboration=FlowCollaboration(),
            stages=[_stage("a", "A", {"prompt": "Do"})],
        )

        text = serialize_flow(doc)

        assert "collaboration:\n  mode: assistants\n" in text
        assert "max_depth" not in text

    def test_serialize_flow_team_list_emits_team_block(self) -> None:
        """A team list emits the ``team:`` block between ``collaboration`` and ``stages``."""
        doc = FlowDocument(
            name="n",
            description="d",
            collaboration=FlowCollaboration(),
            team=[
                FlowTeamMember(
                    id="reviewer",
                    title="reviewer",
                    profile="goga-reviewer",
                    instruction="Review.",
                    skills=["code-audit"],
                ),
            ],
            stages=[_stage("a", "A", {"prompt": "Do"})],
        )

        text = serialize_flow(doc)

        idx_collaboration = text.index("collaboration:")
        idx_team = text.index("team:")
        idx_stages = text.index("stages:")
        assert idx_collaboration < idx_team < idx_stages
        assert (
            "team:\n"
            "- id: reviewer\n"
            "  title: reviewer\n"
            "  profile: goga-reviewer\n"
            "  instruction: Review.\n"
            "  skills:\n"
            "  - code-audit\n"
        ) in text

    def test_serialize_flow_collaboration_free_document_is_byte_identical(self) -> None:
        """A document without collaboration serializes to the frozen pre-change golden, byte for byte."""
        doc = FlowDocument(
            name="demo",
            description="Demo pipeline",
            stages=[
                _stage("brainstorm", "Brainstorm", {"agents": ["auto"], "prompt": "Think"}),
                _stage("build", "Build", {"agents": ["auto"], "prompt": "Make"}, depends_on=["brainstorm"]),
            ],
        )

        text = serialize_flow(doc)

        assert text == COLLABORATION_FREE_GOLDEN
        assert "collaboration" not in text
        assert "team" not in text

    def test_serialize_flow_team_none_and_empty_omit_key(self) -> None:
        """``team=None`` and ``team=[]`` both omit the ``team:`` key entirely."""
        for team in (None, []):
            doc = FlowDocument(
                name="n",
                description="d",
                collaboration=FlowCollaboration(),
                team=team,
                stages=[_stage("a", "A", {"prompt": "Do"})],
            )

            text = serialize_flow(doc)

            assert "team" not in text


class TestSerializeCollaborationStyles:
    """Behavioral tests for the collaboration/team/attachment rendering styles."""

    def test_serialize_collaboration_styles(self) -> None:
        """Multi-line instructions render block-literal; empty scalars render explicitly; key orders fixed."""
        doc = FlowDocument(
            name="n",
            description="d",
            collaboration=FlowCollaboration(max_depth=0),
            team=[
                FlowTeamMember(
                    id="reviewer",
                    title="reviewer",
                    profile="goga-reviewer",
                    instruction="Review the changes.\nBe strict.\n",
                    skills=["code-audit"],
                ),
                FlowTeamMember(
                    id="ops",
                    title="ops",
                    profile="goga-ops",
                    instruction="",
                    skills=[],
                ),
            ],
            stages=[
                _stage(
                    "build",
                    "Build",
                    {
                        "prompt": "Make",
                        "assistants": [
                            FlowAssistant(
                                profile="goga-reviewer",
                                title="reviewer",
                                instruction="Review.\nStrict.\n",
                                mode="required",
                                trigger="on_completion",
                                skills=["code-audit"],
                            ),
                            FlowAssistant(
                                profile="goga-ops",
                                title="ops",
                                instruction="",
                                mode="advisory",
                                trigger="checkpoints",
                                skills=[],
                            ),
                        ],
                    },
                ),
            ],
        )

        text = serialize_flow(doc)

        # The collaboration block — key order mode < max_depth; an authored 0
        # is KEPT (the omission rule is `is None`, never truthiness).
        assert text.index("mode: assistants") < text.index("max_depth: 0")
        assert "max_depth: 0\n" in text

        # The team block — exact golden: multi-line instruction block-literal,
        # empty instruction the plain scalar '', empty skills the explicit [].
        team_block = text[text.index("team:") : text.index("stages:")]
        assert (
            "- id: reviewer\n"
            "  title: reviewer\n"
            "  profile: goga-reviewer\n"
            "  instruction: |\n"
            "    Review the changes.\n"
            "    Be strict.\n"
            "  skills:\n"
            "  - code-audit\n"
            "- id: ops\n"
            "  title: ops\n"
            "  profile: goga-ops\n"
            "  instruction: ''\n"
            "  skills: []\n"
        ) in team_block
        # Member key order: id < title < profile < instruction < skills.
        assert (
            team_block.index("- id: reviewer")
            < team_block.index("  title: reviewer")
            < team_block.index("  profile: goga-reviewer")
            < team_block.index("  instruction: |")
            < team_block.index("  skills:")
        )

        # The stage attachments — exact golden: item keys at dash-indent + 2,
        # the nested skills items at the KEY's indentation.
        assert (
            "  assistants:\n"
            "  - profile: goga-reviewer\n"
            "    title: reviewer\n"
            "    instruction: |\n"
            "      Review.\n"
            "      Strict.\n"
            "    mode: required\n"
            "    trigger: on_completion\n"
            "    skills:\n"
            "    - code-audit\n"
            "  - profile: goga-ops\n"
            "    title: ops\n"
            "    instruction: ''\n"
            "    mode: advisory\n"
            "    trigger: checkpoints\n"
            "    skills: []\n"
        ) in text
        # Attachment key order: profile < title < instruction < mode < trigger < skills.
        stage_block = text[text.index("- id: build") :]
        assert (
            stage_block.index("  - profile: goga-reviewer")
            < stage_block.index("    title: reviewer")
            < stage_block.index("    instruction: |")
            < stage_block.index("    mode: required")
            < stage_block.index("    trigger: on_completion")
            < stage_block.index("    skills:")
        )

    def test_serialize_collaboration_stage_assistants_round_trip(self) -> None:
        """The emitted attachment list parses back into the authored mappings."""
        import yaml

        doc = FlowDocument(
            name="n",
            description="d",
            collaboration=FlowCollaboration(max_depth=2),
            team=[
                FlowTeamMember(
                    id="reviewer",
                    title="reviewer",
                    profile="goga-reviewer",
                    instruction="Review the changes.\nBe strict.\n",
                    skills=["code-audit"],
                ),
            ],
            stages=[
                _stage(
                    "build",
                    "Build",
                    {
                        "prompt": "Make",
                        "assistants": [
                            FlowAssistant(
                                profile="goga-reviewer",
                                title="reviewer",
                                instruction="Review.\nStrict.\n",
                                mode="required",
                                trigger="on_completion",
                                skills=["code-audit"],
                            ),
                        ],
                    },
                ),
            ],
        )

        loaded = yaml.safe_load(serialize_flow(doc))

        assert loaded["collaboration"] == {"mode": "assistants", "max_depth": 2}
        assert loaded["team"] == [
            {
                "id": "reviewer",
                "title": "reviewer",
                "profile": "goga-reviewer",
                "instruction": "Review the changes.\nBe strict.\n",
                "skills": ["code-audit"],
            },
        ]
        assert loaded["stages"][0]["assistants"] == [
            {
                "profile": "goga-reviewer",
                "title": "reviewer",
                "instruction": "Review.\nStrict.\n",
                "mode": "required",
                "trigger": "on_completion",
                "skills": ["code-audit"],
            },
        ]
