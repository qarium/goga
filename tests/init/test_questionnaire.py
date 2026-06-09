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
    """Logic tests for Questionnaire — mock click.prompt/click.confirm.

    Confirm consumption order matches code execution:
    1. Convention
    2. Usages (outer)
    3. Usages (inner loop — another?)
    4. Annotations
    5. Dockerfile
    6. Env suggestions
    7. Custom env (while loop)

    Prompt consumption order:
    1. Language
    2. (If usages: usage name, usage path, in loop)
    3. (If annotations: annotations text)
    4. Agent
    5. Image
    6. (If dockerfile: dockerfile path)
    7. (If env suggestions: value for each key)
    8. (If custom env: key, value, in loop)
    """

    def test_questionnaire_ask_goga_config_python_with_convention(self) -> None:
        prompts = iter([
            "python",                          # language
            "claude",                          # agent
            "qarium/goga-python-3.12:1.0",     # image
        ])
        confirms = iter([
            True,   # Download base convention?
            False,  # Add codemanifest usages?
            False,  # Add codemanifest annotations?
            False,  # Create Dockerfile?
            False,  # Set suggested env variables?
            False,  # Add custom environment variable?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert isinstance(result, GogaConfigAnswers)
        assert result.language == "python"
        assert result.agent == "claude"
        assert result.image == "qarium/goga-python-3.12:1.0"
        assert result.env is None
        assert result.dockerfile_path is None
        assert result.codemanifest_usages == {"conventions": ".goga/usages/conventions.md"}
        assert result.codemanifest_annotations == "Use `conventions` for code writing rules and testing."

    def test_questionnaire_ask_goga_config_golang_without_convention(self) -> None:
        prompts = iter([
            "golang",                          # language
            "claude",                          # agent
            "qarium/goga-golang-1.23:1.0",     # image
        ])
        confirms = iter([
            False,  # Download base convention?
            False,  # Add codemanifest usages?
            False,  # Add codemanifest annotations?
            False,  # Create Dockerfile?
            False,  # Set suggested env variables?
            False,  # Add custom environment variable?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert isinstance(result, GogaConfigAnswers)
        assert result.language == "golang"
        assert result.codemanifest_usages is None
        assert result.codemanifest_annotations is None
        assert result.dockerfile_path is None

    def test_questionnaire_ask_goga_config_with_env_vars(self) -> None:
        prompts = iter([
            "python",                          # language
            "claude",                          # agent
            "qarium/goga-python-3.12:1.0",     # image
            "API_KEY",                         # env key 1
            "secret",                          # env value 1
            "MODEL",                           # env key 2
            "gpt-4",                           # env value 2
        ])
        confirms = iter([
            False,  # Download base convention?
            False,  # Add codemanifest usages?
            False,  # Add codemanifest annotations?
            False,  # Create Dockerfile?
            False,  # Set suggested env variables?
            True,   # Add custom environment variable? (first)
            True,   # Add custom environment variable? (second)
            False,  # Add custom environment variable? (stop)
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.env == {"API_KEY": "secret", "MODEL": "gpt-4"}

    def test_questionnaire_ask_goga_config_custom_usages_merge(self) -> None:
        prompts = iter([
            "python",                          # language
            "custom",                          # usage name
            ".goga/usages/custom.md",          # usage path
            "claude",                          # agent
            "qarium/goga-python-3.12:1.0",     # image
        ])
        confirms = iter([
            True,   # Download base convention?
            True,   # Add codemanifest usages?
            False,  # Add another codemanifest usage? (stop)
            False,  # Add codemanifest annotations?
            False,  # Create Dockerfile?
            False,  # Set suggested env variables?
            False,  # Add custom environment variable?
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
            "python",                          # language
            "custom",                          # usage name
            ".goga/usages/custom.md",          # usage path
            "claude",                          # agent
            "qarium/goga-python-3.12:1.0",     # image
        ])
        confirms = iter([
            False,  # Download base convention?
            True,   # Add codemanifest usages?
            False,  # Add another codemanifest usage? (stop)
            False,  # Add codemanifest annotations?
            False,  # Create Dockerfile?
            False,  # Set suggested env variables?
            False,  # Add custom environment variable?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.codemanifest_usages == {"custom": ".goga/usages/custom.md"}

    def test_questionnaire_ask_goga_config_custom_annotations_appended(self) -> None:
        prompts = iter([
            "python",                          # language
            "Custom rule for project",         # annotations text
            "claude",                          # agent
            "qarium/goga-python-3.12:1.0",     # image
        ])
        confirms = iter([
            True,   # Download base convention?
            False,  # Add codemanifest usages?
            True,   # Add codemanifest annotations?
            False,  # Create Dockerfile?
            False,  # Set suggested env variables?
            False,  # Add custom environment variable?
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
            "golang",                          # language
            "claude",                          # agent
            "my-custom/golang:2.0",            # image (custom, not from predefined list)
        ])
        confirms = iter([
            False,  # Download base convention?
            False,  # Add codemanifest usages?
            False,  # Add codemanifest annotations?
            False,  # Create Dockerfile?
            False,  # Set suggested env variables?
            False,  # Add custom environment variable?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.language == "golang"
        assert result.image == "my-custom/golang:2.0"

    def test_questionnaire_ask_goga_config_kotlin_with_predefined_images(self) -> None:
        prompts = iter([
            "kotlin",                          # language
            "claude",                          # agent
            "qarium/goga-kotlin-2.3.21:1.0",   # image (default from predefined list)
        ])
        confirms = iter([
            False,  # Download base convention?
            False,  # Add codemanifest usages?
            False,  # Add codemanifest annotations?
            False,  # Create Dockerfile?
            False,  # Set suggested env variables?
            False,  # Add custom environment variable?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.language == "kotlin"
        assert result.image == "qarium/goga-kotlin-2.3.21:1.0"

    def test_questionnaire_ask_goga_config_swift_with_predefined_images(self) -> None:
        prompts = iter([
            "swift",                           # language
            "claude",                          # agent
            "qarium/goga-swift-6.2.4:1.0",     # image (default from predefined list)
        ])
        confirms = iter([
            False,  # Download base convention?
            False,  # Add codemanifest usages?
            False,  # Add codemanifest annotations?
            False,  # Create Dockerfile?
            False,  # Set suggested env variables?
            False,  # Add custom environment variable?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.language == "swift"
        assert result.image == "qarium/goga-swift-6.2.4:1.0"

    def test_questionnaire_ask_goga_config_javascript_with_predefined_images(self) -> None:
        prompts = iter([
            "javascript",                      # language
            "claude",                          # agent
            "qarium/goga-node-24:1.0",         # image (default from predefined list)
        ])
        confirms = iter([
            False,  # Download base convention?
            False,  # Add codemanifest usages?
            False,  # Add codemanifest annotations?
            False,  # Create Dockerfile?
            False,  # Set suggested env variables?
            False,  # Add custom environment variable?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.language == "javascript"
        assert result.image == "qarium/goga-node-24:1.0"

    def test_all_languages_have_image_map_entries(self) -> None:
        from goga.init.questionnaire import _IMAGE_MAP, _LANGUAGES

        for language in _LANGUAGES:
            assert language in _IMAGE_MAP, f"Language '{language}' missing from _IMAGE_MAP"

    def test_questionnaire_ask_goga_config_duplicate_usage_name_skipped(self) -> None:
        prompts = iter([
            "python",                          # language
            "conventions",                     # duplicate usage name (already set by convention)
            "custom",                          # usage name (new, after loop continues)
            ".goga/usages/custom.md",          # usage path
            "claude",                          # agent
            "qarium/goga-python-3.12:1.0",     # image
        ])
        confirms = iter([
            True,   # Download base convention?
            True,   # Add codemanifest usages?
            True,   # Add another codemanifest usage? (continue after duplicate skip)
            False,  # Add another codemanifest usage? (stop after custom added)
            False,  # Add codemanifest annotations?
            False,  # Create Dockerfile?
            False,  # Set suggested env variables?
            False,  # Add custom environment variable?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.echo") as mock_echo, \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.codemanifest_usages["conventions"] == ".goga/usages/conventions.md"
        assert "custom" in result.codemanifest_usages
        assert any(
            'Usage "conventions" already exists, skipping.' in str(c)
            for c in mock_echo.call_args_list
        )

    def test_questionnaire_ask_returns_init_answers(self) -> None:
        prompts = iter([
            "python",                          # language
            "claude",                          # agent
            "qarium/goga-python-3.12:1.0",     # image
        ])
        confirms = iter([
            False,  # Download base convention?
            False,  # Add codemanifest usages?
            False,  # Add codemanifest annotations?
            False,  # Create Dockerfile?
            False,  # Set suggested env variables?
            False,  # Add custom environment variable?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask()

        assert isinstance(result, InitAnswers)
        assert isinstance(result.goga_config, GogaConfigAnswers)

    # --- New tests for Dockerfile and env suggestions ---

    def test_cpp_not_in_language_choices(self) -> None:
        """cpp must not appear in language choices."""
        from goga.init.questionnaire import _LANGUAGES

        assert "cpp" not in _LANGUAGES

    def test_questionnaire_ask_goga_config_with_dockerfile(self) -> None:
        prompts = iter([
            "python",                          # language
            "claude",                          # agent
            "qarium/goga-python-3.12:1.0",     # image
            "Dockerfile",                      # dockerfile path
        ])
        confirms = iter([
            False,  # Download base convention?
            False,  # Add codemanifest usages?
            False,  # Add codemanifest annotations?
            True,   # Create Dockerfile?
            False,  # Set suggested env variables?
            False,  # Add custom environment variable?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.dockerfile_path == "Dockerfile"

    def test_questionnaire_ask_goga_config_without_dockerfile(self) -> None:
        prompts = iter([
            "python",                          # language
            "claude",                          # agent
            "qarium/goga-python-3.12:1.0",     # image
        ])
        confirms = iter([
            False,  # Download base convention?
            False,  # Add codemanifest usages?
            False,  # Add codemanifest annotations?
            False,  # Create Dockerfile?
            False,  # Set suggested env variables?
            False,  # Add custom environment variable?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.dockerfile_path is None

    def test_questionnaire_env_suggested_keys_for_claude(self) -> None:
        prompts = iter([
            "python",                          # language
            "claude",                          # agent
            "qarium/goga-python-3.12:1.0",     # image
            "glm-4.7",                         # ANTHROPIC_DEFAULT_HAIKU_MODEL
            "glm-5-turbo",                     # ANTHROPIC_DEFAULT_SONNET_MODEL
            "glm-5.1",                         # ANTHROPIC_DEFAULT_OPUS_MODEL
            "https://api.z.ai/api/anthropic",  # ANTHROPIC_BASE_URL
        ])
        confirms = iter([
            False,  # Download base convention?
            False,  # Add codemanifest usages?
            False,  # Add codemanifest annotations?
            False,  # Create Dockerfile?
            True,   # Set suggested env variables?
            False,  # Add custom environment variable?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.env == {
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-4.7",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5-turbo",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.1",
            "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic",
        }

    def test_questionnaire_ask_goga_config_codex_agent(self) -> None:
        prompts = iter([
            "python",                          # language
            "codex",                           # agent
            "qarium/goga-python-3.12:1.0",     # image
        ])
        confirms = iter([
            False,  # Download base convention?
            False,  # Add codemanifest usages?
            False,  # Add codemanifest annotations?
            False,  # Create Dockerfile?
            False,  # Set suggested env variables?
            False,  # Add custom environment variable?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.agent == "codex"
        assert result.env is None

    def test_questionnaire_codex_env_suggested_keys(self) -> None:
        prompts = iter([
            "python",                          # language
            "codex",                           # agent
            "qarium/goga-python-3.12:1.0",     # image
            "o4-mini",                         # CODEX_MODEL
        ])
        confirms = iter([
            False,  # Download base convention?
            False,  # Add codemanifest usages?
            False,  # Add codemanifest annotations?
            False,  # Create Dockerfile?
            True,   # Set suggested env variables?
            False,  # Add custom environment variable?
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.env == {"CODEX_MODEL": "o4-mini"}

    def test_agent_env_map_contains_codex(self) -> None:
        from goga.init.questionnaire import _AGENT_ENV_MAP

        assert "codex" in _AGENT_ENV_MAP
        assert _AGENT_ENV_MAP["codex"] == ["CODEX_MODEL"]

    def test_questionnaire_env_skip_suggested_custom_only(self) -> None:
        prompts = iter([
            "python",                          # language
            "claude",                          # agent
            "qarium/goga-python-3.12:1.0",     # image
            "MY_KEY",                          # custom env key
            "my_value",                        # custom env value
        ])
        confirms = iter([
            False,  # Download base convention?
            False,  # Add codemanifest usages?
            False,  # Add codemanifest annotations?
            False,  # Create Dockerfile?
            False,  # Set suggested env variables?
            True,   # Add custom environment variable?
            False,  # Add custom environment variable? (stop)
        ])

        with patch("click.prompt", side_effect=prompts), \
             patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.env == {"MY_KEY": "my_value"}
