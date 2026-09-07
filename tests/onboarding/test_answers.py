from __future__ import annotations

import dataclasses
from typing import get_type_hints

import pytest
from goga.onboarding.answers import GogaConfigAnswers, InitAnswers


class TestContract:
    """Contract-level tests for InitAnswers and GogaConfigAnswers."""

    def test_goga_config_answers_importable_from_answers(self) -> None:
        from goga.onboarding.answers import GogaConfigAnswers

        assert GogaConfigAnswers is not None

    def test_init_answers_importable_from_answers(self) -> None:
        from goga.onboarding.answers import InitAnswers

        assert InitAnswers is not None

    def test_init_answers_has_goga_config_property(self) -> None:
        hints = get_type_hints(InitAnswers)
        assert "goga_config" in hints

    def test_init_answers_goga_config_is_optional(self) -> None:
        hints = get_type_hints(InitAnswers)
        assert hints["goga_config"] == GogaConfigAnswers | None

    def test_goga_config_answers_has_all_declared_properties(self) -> None:
        hints = get_type_hints(GogaConfigAnswers)
        expected = {
            "language",
            "agent",
            "image",
            "pipeline_agent",
            "pipeline_env",
            "env",
            "codemanifest_usages",
            "codemanifest_annotations",
            "dockerfile_path",
        }
        assert expected.issubset(hints.keys())

    def test_goga_config_answers_property_types(self) -> None:
        hints = get_type_hints(GogaConfigAnswers)
        assert hints["language"] is str
        assert hints["image"] is str
        assert hints["agent"] == str | None
        assert hints["pipeline_agent"] == str | None
        assert hints["pipeline_env"] == dict | None
        assert hints["env"] == dict | None

    def test_goga_config_answers_field_names_in_contract_order(self) -> None:
        names = [f.name for f in dataclasses.fields(GogaConfigAnswers)]
        assert names == [
            "language",
            "image",
            "agent",
            "pipeline_agent",
            "pipeline_env",
            "env",
            "codemanifest_usages",
            "codemanifest_annotations",
            "dockerfile_path",
            "dockerfile_base_image",
        ]

    def test_constructors_accept_kwargs(self) -> None:
        cfg = GogaConfigAnswers(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:0.1",
            pipeline_agent="claude",
        )
        answers = InitAnswers(goga_config=cfg)
        assert answers.goga_config is cfg


class TestLogic:
    """Logic tests for InitAnswers and GogaConfigAnswers."""

    def test_goga_config_answers_is_frozen(self) -> None:
        cfg = GogaConfigAnswers(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:0.1",
            pipeline_agent="claude",
        )

        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.language = "go"  # type: ignore[misc]

    def test_init_answers_is_frozen(self) -> None:
        cfg = GogaConfigAnswers(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:0.1",
            pipeline_agent="claude",
        )
        answers = InitAnswers(goga_config=cfg)

        with pytest.raises(dataclasses.FrozenInstanceError):
            answers.goga_config = cfg  # type: ignore[misc]

    def test_goga_config_answers_kw_only(self) -> None:
        with pytest.raises(TypeError):
            GogaConfigAnswers("python", "claude", "img", "claude")  # type: ignore[call-arg]

    def test_goga_config_answers_agents_default_none(self) -> None:
        cfg = GogaConfigAnswers(
            language="python",
            image="qarium/goga-python-3.12:0.1",
        )
        assert cfg.agent is None
        assert cfg.pipeline_agent is None

    def test_goga_config_answers_defaults_none(self) -> None:
        cfg = GogaConfigAnswers(
            language="go",
            agent="claude",
            image="qarium/goga-golang-1.23:0.1",
            pipeline_agent="claude",
        )
        assert cfg.pipeline_env is None
        assert cfg.env is None
        assert cfg.codemanifest_usages is None
        assert cfg.codemanifest_annotations is None
        assert cfg.dockerfile_path is None

    def test_goga_config_answers_with_codemanifest(self) -> None:
        cfg = GogaConfigAnswers(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:0.1",
            pipeline_agent="codex",
            pipeline_env={"CODEX_MODEL": "o4-mini"},
            codemanifest_usages={"conventions": ".goga/usages/conventions.md"},
            codemanifest_annotations="Use conventions for code rules.",
        )
        assert cfg.pipeline_agent == "codex"
        assert cfg.pipeline_env == {"CODEX_MODEL": "o4-mini"}
        assert cfg.codemanifest_usages == {"conventions": ".goga/usages/conventions.md"}
        assert cfg.codemanifest_annotations == "Use conventions for code rules."

    def test_init_answers_kw_only(self) -> None:
        cfg = GogaConfigAnswers(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:0.1",
            pipeline_agent="claude",
        )

        with pytest.raises(TypeError):
            InitAnswers(cfg)  # type: ignore[call-arg]

    def test_init_answers_goga_config_accepts_none(self) -> None:
        answers = InitAnswers(goga_config=None)
        assert answers.goga_config is None

    def test_init_answers_goga_config_round_trips_non_none(self) -> None:
        cfg = GogaConfigAnswers(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:0.1",
            pipeline_agent="claude",
        )
        answers = InitAnswers(goga_config=cfg)
        assert answers.goga_config is cfg
