from __future__ import annotations

from unittest.mock import patch

from goga.init.answers import GogaConfigAnswers, InitAnswers
from goga.init.questionnaire import Questionnaire


class TestContract:
    """Contract-level tests for Questionnaire."""

    def test_questionnaire_importable_from_questionnaire(self) -> None:
        from goga.init.questionnaire import Questionnaire

        assert Questionnaire is not None

    def test_questionnaire_constructor_no_args(self) -> None:
        q = Questionnaire()
        assert q is not None

    def test_questionnaire_has_ask_method(self) -> None:
        q = Questionnaire()
        assert hasattr(q, "ask")
        assert callable(q.ask)

    def test_questionnaire_has_ask_goga_config_method(self) -> None:
        q = Questionnaire()
        assert hasattr(q, "ask_goga_config")
        assert callable(q.ask_goga_config)


class TestLogic:
    """Logic tests for Questionnaire — mock click.prompt/click.confirm."""

    def test_questionnaire_ask_goga_config_python_with_convention(self) -> None:
        prompts = iter([
            "python",        # language
            "claude",        # agent
            "qarium/goga-python-3.12:1.0",  # image
        ])
        confirms = iter([
            True,   # Download base convention?
            False,  # Add environment variable?
            False,  # Add codemanifest usages?
            False,  # Add codemanifest annotations?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert isinstance(result, GogaConfigAnswers)
        assert result.language == "python"
        assert result.agent == "claude"
        assert result.image == "qarium/goga-python-3.12:1.0"
        assert result.env == {}
        assert result.codemanifest_usages == {"conventions": ".goga/usages/conventions.md"}
        assert result.codemanifest_annotations == "Use `conventions` for code writing rules and testing."

    def test_questionnaire_ask_goga_config_golang_without_convention(self) -> None:
        prompts = iter([
            "golang",                       # language
            "claude",                       # agent
            "qarium/goga-golang-1.23:1.0",  # image
        ])
        confirms = iter([
            False,  # Download base convention?
            False,  # Add environment variable?
            False,  # Add codemanifest usages?
            False,  # Add codemanifest annotations?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert isinstance(result, GogaConfigAnswers)
        assert result.language == "golang"
        assert result.codemanifest_usages is None
        assert result.codemanifest_annotations is None

    def test_questionnaire_ask_goga_config_with_env_vars(self) -> None:
        prompts = iter([
            "python",                        # language
            "claude",                        # agent
            "qarium/goga-python-3.12:1.0",   # image
            "API_KEY",                       # env key 1
            "secret",                        # env value 1
            "MODEL",                         # env key 2
            "gpt-4",                         # env value 2
        ])
        confirms = iter([
            False,  # Download base convention?
            True,   # Add environment variable? (first)
            True,   # Add environment variable? (second)
            False,  # Add environment variable? (stop)
            False,  # Add codemanifest usages?
            False,  # Add codemanifest annotations?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.env == {"API_KEY": "secret", "MODEL": "gpt-4"}

    def test_questionnaire_ask_goga_config_custom_usages_merge(self) -> None:
        prompts = iter([
            "python",                        # language
            "claude",                        # agent
            "qarium/goga-python-3.12:1.0",   # image
            "custom",                        # usage name
            ".goga/usages/custom.md",        # usage path
        ])
        confirms = iter([
            True,   # Download base convention?
            False,  # Add environment variable?
            True,   # Add codemanifest usages?
            False,  # Add another codemanifest usage? (stop)
            False,  # Add codemanifest annotations?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert "conventions" in result.codemanifest_usages
        assert "custom" in result.codemanifest_usages
        assert result.codemanifest_usages["custom"] == ".goga/usages/custom.md"

    def test_questionnaire_ask_goga_config_custom_usages_no_convention(self) -> None:
        prompts = iter([
            "python",                        # language
            "claude",                        # agent
            "qarium/goga-python-3.12:1.0",   # image
            "custom",                        # usage name
            ".goga/usages/custom.md",        # usage path
        ])
        confirms = iter([
            False,  # Download base convention?
            False,  # Add environment variable?
            True,   # Add codemanifest usages?
            False,  # Add another codemanifest usage? (stop)
            False,  # Add codemanifest annotations?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.codemanifest_usages == {"custom": ".goga/usages/custom.md"}

    def test_questionnaire_ask_goga_config_custom_annotations_appended(self) -> None:
        prompts = iter([
            "python",                        # language
            "claude",                        # agent
            "qarium/goga-python-3.12:1.0",   # image
            "Custom rule for project",       # custom annotations
        ])
        confirms = iter([
            True,   # Download base convention?
            False,  # Add environment variable?
            False,  # Add codemanifest usages?
            True,   # Add codemanifest annotations?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.codemanifest_annotations is not None
        assert result.codemanifest_annotations.startswith("Use")
        assert "Custom rule for project" in result.codemanifest_annotations
        assert "\n" in result.codemanifest_annotations

    def test_questionnaire_ask_goga_config_custom_image_with_predefined(self) -> None:
        prompts = iter([
            "golang",                       # language
            "claude",                       # agent
            "my-custom/golang:2.0",         # image (custom, not from predefined list)
        ])
        confirms = iter([
            False,  # Download base convention?
            False,  # Add environment variable?
            False,  # Add codemanifest usages?
            False,  # Add codemanifest annotations?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.language == "golang"
        assert result.image == "my-custom/golang:2.0"

    def test_questionnaire_ask_gogo_config_language_without_predefined_images(self) -> None:
        prompts = iter([
            "kotlin",                # language
            "claude",                # agent
            "custom/kotlin:1.0",    # image (free text, no predefined list)
        ])
        confirms = iter([
            False,  # Download base convention?
            False,  # Add environment variable?
            False,  # Add codemanifest usages?
            False,  # Add codemanifest annotations?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.language == "kotlin"
        assert result.image == "custom/kotlin:1.0"

    def test_questionnaire_ask_goga_config_duplicate_usage_name_skipped(self) -> None:
        prompts = iter([
            "python",                        # language
            "claude",                        # agent
            "qarium/goga-python-3.12:1.0",   # image
            "conventions",                   # duplicate usage name (already set by convention)
            "custom",                        # usage name (new, after loop continues)
            ".goga/usages/custom.md",        # usage path
        ])
        confirms = iter([
            True,   # Download base convention?
            False,  # Add environment variable?
            True,   # Add codemanifest usages?
            True,   # Add another codemanifest usage? (continue after duplicate skip)
            False,  # Add another codemanifest usage? (stop after custom added)
            False,  # Add codemanifest annotations?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.echo") as mock_echo, \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        # "conventions" key should NOT be overwritten
        assert result.codemanifest_usages["conventions"] == ".goga/usages/conventions.md"
        assert "custom" in result.codemanifest_usages
        assert any(
            'Usage "conventions" already exists, skipping.' in str(c)
            for c in mock_echo.call_args_list
        )

    def test_questionnaire_ask_returns_init_answers(self) -> None:
        prompts = iter([
            "python",                        # language
            "claude",                        # agent
            "qarium/goga-python-3.12:1.0",   # image
        ])
        confirms = iter([
            False,  # Download base convention?
            False,  # Add environment variable?
            False,  # Add codemanifest usages?
            False,  # Add codemanifest annotations?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask()

        assert isinstance(result, InitAnswers)
        assert isinstance(result.goga_config, GogaConfigAnswers)
