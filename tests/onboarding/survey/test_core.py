"""Contract and logic tests for the entity declared in
``goga/onboarding/survey/CODEMANIFEST`` with ``location: core.py``:

- ``core_questions(image_tag, project_name, convention_exists)`` — the
  core question tree builder of the session

The tree is declarative data: the eight core sections in survey order with
the image hints completed from the runtime minor tag — never a hardcoded
one. Rendering the questions belongs to the engine.
"""

from __future__ import annotations

from goga.onboarding.questions import Question, QuestionGroup
from goga.onboarding.survey import core_questions

_CELL_ALL = ["SessionPlan", "apply_skips", "assemble_session_plan", "core_questions"]

_SECTION_ORDER = ["language", "convention", "codemanifest", "build", "docker_image", "pipeline", "tools", "usages"]

# The last hint of the completed `image_defaults` list (family order:
# python, golang, javascript, kotlin, swift) — the offered base-image default.
_LAST_HINT_1_3 = "qarium/goga-swift-6.2:1.3"


def _sections(tree: QuestionGroup) -> dict[str, object]:
    """Index the core sections by id."""
    return {child.id: child for child in tree.children}


def _docker_children(tree: QuestionGroup) -> dict[str, Question]:
    """Index the docker_image section children by local name."""
    docker = _sections(tree)["docker_image"]

    return {child.id: child for child in docker.children}


# --- Contract tests ---


class TestCoreContract:
    def test_entity_is_importable_from_the_package_facade(self) -> None:
        """The builder lives on the cell package and its ``__all__`` is exact."""
        import goga.onboarding.survey as cell

        assert cell.core_questions is core_questions
        assert cell.__all__ == _CELL_ALL

    def test_builder_returns_the_core_group(self) -> None:
        """``core_questions(...)`` builds the ``core`` root group."""
        tree = core_questions("1.3", "my-app", False)

        assert isinstance(tree, QuestionGroup)
        assert tree.id == "core"
        assert tree.children is not None


# --- Logic tests ---


class TestCoreTree:
    def test_core_questions_builds_eight_sections_with_tag(self) -> None:
        """The eight sections in survey order; the tag completes every hint."""
        tree = core_questions("1.3", "my-app", False)

        assert [child.id for child in tree.children] == _SECTION_ORDER

        base_image = _docker_children(tree)["base_image"]

        assert "qarium/goga-python-3.14:1.3" in base_image.prompt
        assert base_image.default == _LAST_HINT_1_3

        assert _docker_children(tree)["image"].default == "my-app:latest"

    def test_existing_convention_drops_the_convention_section(self) -> None:
        """``convention_exists=True`` omits the gate; language stays first."""
        tree = core_questions("1.3", None, True)

        assert tree.children[0].id == "language"
        assert "convention" not in _sections(tree)

    def test_project_name_none_omits_the_image_default(self) -> None:
        """Without a project name the image question offers no default."""
        tree = core_questions("1.3", None, False)

        assert _docker_children(tree)["image"].default is None

    def test_language_is_a_choice_of_the_supported_languages(self) -> None:
        """The language section is one choice question, in the survey order."""
        language = _sections(core_questions("1.3", None, True))["language"]

        assert isinstance(language, Question)
        assert language.kind == "choice"
        assert language.choices == ["python", "golang", "kotlin", "swift", "javascript"]

    def test_convention_gate_is_a_confirm_defaulting_to_false(self) -> None:
        """The convention section carries the adopt confirm, default False."""
        convention = _sections(core_questions("1.3", None, False))["convention"]

        assert isinstance(convention, QuestionGroup)
        assert convention.prompt == "--- Base Convention ---"

        adopt = convention.children[0]

        assert adopt.id == "adopt"
        assert adopt.kind == "confirm"
        assert adopt.default is False

    def test_codemanifest_records_carry_no_tree_defaults(self) -> None:
        """Usages pairs + annotations input; the prefill is engine-side."""
        codemanifest = _sections(core_questions("1.3", None, True))["codemanifest"]

        assert [child.id for child in codemanifest.children] == ["usages", "annotations"]
        assert codemanifest.children[0].kind == "pairs"
        assert codemanifest.children[1].kind == "input"
        assert codemanifest.children[0].default is None
        assert codemanifest.children[1].default is None

    def test_executor_sections_offer_agents_and_env_pairs(self) -> None:
        """Build and pipeline carry an agent choice plus env pairs."""
        sections = _sections(core_questions("1.3", None, True))

        for section_id in ("build", "pipeline"):
            section = sections[section_id]

            assert isinstance(section, QuestionGroup)
            assert [child.id for child in section.children] == ["agent", "env"]

            agent, env = section.children

            assert agent.kind == "choice"
            assert agent.choices == ["claude", "codex", "cursor", "opencode", "qwen"]
            assert env.kind == "pairs"

    def test_docker_image_children_are_free_form_inputs(self) -> None:
        """Dockerfile, base_image, image — all kind input; the path defaults."""
        children = _docker_children(core_questions("1.3", "my-app", True))

        assert [child.id for child in children.values()] == ["dockerfile", "base_image", "image"]
        assert all(child.kind == "input" for child in children.values())
        assert children["dockerfile"].default == ".goga/Dockerfile"

    def test_tools_pairs_document_the_four_version_forms(self) -> None:
        """The tools section documents the grammar and the created files."""
        tools = _sections(core_questions("1.3", None, True))["tools"]

        assert isinstance(tools, Question)
        assert tools.kind == "pairs"
        assert "latest" in tools.prompt
        assert "N.x" in tools.prompt
        assert "N.M.x" in tools.prompt
        assert ".goga/tools/<tool>/" in tools.prompt

    def test_usages_section_is_structural(self) -> None:
        """The usages section is a heading group with no declarable children."""
        usages = _sections(core_questions("1.3", None, True))["usages"]

        assert isinstance(usages, QuestionGroup)
        assert usages.prompt == "--- Usages ---"
        assert usages.children is None

    def test_the_tag_threads_from_the_single_argument(self) -> None:
        """No hardcoded tag — every completed hint follows ``image_tag``."""
        tree = core_questions("1.4", "my-app", True)

        base_image = _docker_children(tree)["base_image"]

        assert "qarium/goga-python-3.14:1.4" in base_image.prompt
        assert base_image.default == "qarium/goga-swift-6.2:1.4"
        assert ":1.3" not in base_image.prompt
