from __future__ import annotations

import dataclasses
from typing import get_type_hints

import pytest
from goga.init.answers import GogaConfigAnswers, InitAnswers


class TestContract:
    """Contract-level tests for InitAnswers and GogaConfigAnswers."""

    def test_goga_config_answers_importable_from_answers(self) -> None:
        from goga.init.answers import GogaConfigAnswers

        assert GogaConfigAnswers is not None

    def test_init_answers_importable_from_answers(self) -> None:
        from goga.init.answers import InitAnswers

        assert InitAnswers is not None

    def test_init_answers_has_goga_config_property(self) -> None:
        hints = get_type_hints(InitAnswers)
        assert "goga_config" in hints

    def test_goga_config_answers_has_all_six_properties(self) -> None:
        hints = get_type_hints(GogaConfigAnswers)
        expected = {
            "language",
            "agent",
            "image",
            "env",
            "codemanifest_usages",
            "codemanifest_annotations",
        }
        assert expected.issubset(hints.keys())

    def test_goga_config_answers_property_types(self) -> None:
        hints = get_type_hints(GogaConfigAnswers)
        assert hints["language"] is str
        assert hints["agent"] is str
        assert hints["image"] is str
        assert hints["env"] == dict | None

    def test_constructors_accept_kwargs(self) -> None:
        cfg = GogaConfigAnswers(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:0.1",
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
        )
        with pytest.raises(dataclasses.FrozenInstanceError):
            cfg.language = "go"  # type: ignore[misc]

    def test_init_answers_is_frozen(self) -> None:
        cfg = GogaConfigAnswers(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:0.1",
        )
        answers = InitAnswers(goga_config=cfg)
        with pytest.raises(dataclasses.FrozenInstanceError):
            answers.goga_config = cfg  # type: ignore[misc]

    def test_goga_config_answers_kw_only(self) -> None:
        with pytest.raises(TypeError):
            GogaConfigAnswers("python", "claude", "img")  # type: ignore[call-arg]

    def test_goga_config_answers_defaults_none(self) -> None:
        cfg = GogaConfigAnswers(
            language="go",
            agent="claude",
            image="qarium/goga-golang-1.23:0.1",
        )
        assert cfg.codemanifest_usages is None
        assert cfg.codemanifest_annotations is None

    def test_goga_config_answers_with_codemanifest(self) -> None:
        cfg = GogaConfigAnswers(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:0.1",
            codemanifest_usages={"conventions": ".goga/usages/conventions.md"},
            codemanifest_annotations="Use conventions for code rules.",
        )
        assert cfg.codemanifest_usages == {"conventions": ".goga/usages/conventions.md"}
        assert cfg.codemanifest_annotations == "Use conventions for code rules."

    def test_init_answers_kw_only(self) -> None:
        cfg = GogaConfigAnswers(
            language="python",
            agent="claude",
            image="qarium/goga-python-3.12:0.1",
        )
        with pytest.raises(TypeError):
            InitAnswers(cfg)  # type: ignore[call-arg]
