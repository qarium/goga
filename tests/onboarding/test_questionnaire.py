from __future__ import annotations

from typing import get_type_hints
from unittest.mock import patch

import pytest
from goga.onboarding.answers import GogaConfigAnswers, InitAnswers
from goga.onboarding.questionnaire import Questionnaire

# Apply the `_clean_cwd` fixture (tests/onboarding/conftest.py) to every test
# in this module: survey tests need a CWD without .goga/config.yml.
pytestmark = pytest.mark.usefixtures("_clean_cwd")


class TestContract:
    """Contract-level tests for Questionnaire."""

    def test_questionnaire_importable_from_questionnaire(self) -> None:
        from goga.onboarding.questionnaire import Questionnaire

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

    def test_ask_goga_config_return_annotation_is_optional(self) -> None:
        """ask_goga_config returns GogaConfigAnswers | None (skip whole survey)."""
        hints = get_type_hints(Questionnaire.ask_goga_config)
        assert hints["return"] == GogaConfigAnswers | None

    def test_ask_image_name_two_mode_signature_contract(self) -> None:
        """ask_image_name is two-mode: (language=None, default=None) both default to None."""
        import inspect

        params = inspect.signature(Questionnaire.ask_image_name).parameters

        assert "language" in params
        assert "default" in params
        assert params["language"].default is None
        assert params["default"].default is None


class TestLogic:
    """Logic tests for Questionnaire — mock click.prompt/click.confirm.

    Confirm consumption order matches code execution:
    1. Convention (download base convention?)
    2. Usages (outer: add codemanifest usages?)
    3. Usages (inner loop: add another?)
    4. Annotations (add codemanifest annotations?)
    5. Build agent (configure a build agent?) — gates the Agent prompt
    6. Dockerfile (create Dockerfile?)
    7. Env suggestions for task_executor (set suggested env variables?)
    8. Custom env for task_executor (add custom environment variable? — while loop)
    9. Pipeline agent (configure a pipeline agent?) — gates the Pipeline agent prompt
    10. Env suggestions for pipeline (set suggested env variables?)
    11. Custom env for pipeline (add custom environment variable? — while loop)

    Prompt consumption order:
    1. Language
    2. (If usages: usage name, usage path, in loop)
    3. (If annotations: annotations text)
    4. Agent (only when build-agent confirm is True)
    5. Image
    6. (If dockerfile: dockerfile path)
    7. (If task env suggestions: value for each key)
    8. (If custom task env: key, value, in loop)
    9. Pipeline agent (only when pipeline-agent confirm is True)
    10. (If pipeline env suggestions: value for each key)
    11. (If custom pipeline env: key, value, in loop)
    """

    # The `_clean_cwd` fixture lives in tests/onboarding/conftest.py and is
    # applied module-wide via `pytestmark` (see the top of this file).

    def test_questionnaire_ask_goga_config_python_with_convention(self) -> None:
        prompts = iter(
            [
                "python",  # language
                "claude",  # agent
                "qarium/goga-python-3.12:1.0",  # image
                "claude",  # pipeline agent
            ]
        )
        confirms = iter(
            [
                True,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                False,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with patch("click.prompt", side_effect=prompts), patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert isinstance(result, GogaConfigAnswers)
        assert result.language == "python"
        assert result.agent == "claude"
        assert result.image == "qarium/goga-python-3.12:1.0"
        assert result.env is None
        assert result.pipeline_agent == "claude"
        assert result.pipeline_env is None
        assert result.dockerfile_path is None
        assert result.codemanifest_usages == {"conventions": ".goga/usages/conventions.md"}
        assert result.codemanifest_annotations == "Use `conventions` for code writing rules and testing."

    def test_questionnaire_ask_goga_config_golang_without_convention(self) -> None:
        prompts = iter(
            [
                "golang",  # language
                "claude",  # agent
                "qarium/goga-golang-1.23:1.0",  # image
                "claude",  # pipeline agent
            ]
        )
        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                False,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with patch("click.prompt", side_effect=prompts), patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert isinstance(result, GogaConfigAnswers)
        assert result.language == "golang"
        assert result.codemanifest_usages is None
        assert result.codemanifest_annotations is None
        assert result.dockerfile_path is None

    def test_questionnaire_ask_goga_config_with_env_vars(self) -> None:
        prompts = iter(
            [
                "python",  # language
                "claude",  # agent
                "qarium/goga-python-3.12:1.0",  # image
                "API_KEY",  # env key 1
                "secret",  # env value 1
                "MODEL",  # env key 2
                "gpt-4",  # env value 2
                "claude",  # pipeline agent
            ]
        )
        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                False,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                True,  # Add custom task env variable? (first)
                True,  # Add custom task env variable? (second)
                False,  # Add custom task env variable? (stop)
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with patch("click.prompt", side_effect=prompts), patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.env == {"API_KEY": "secret", "MODEL": "gpt-4"}

    def test_questionnaire_ask_goga_config_custom_usages_merge(self) -> None:
        prompts = iter(
            [
                "python",  # language
                "custom",  # usage name
                ".goga/usages/custom.md",  # usage path
                "claude",  # agent
                "qarium/goga-python-3.12:1.0",  # image
                "claude",  # pipeline agent
            ]
        )
        confirms = iter(
            [
                True,  # Download base convention?
                True,  # Add codemanifest usages?
                False,  # Add another codemanifest usage? (stop)
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                False,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with patch("click.prompt", side_effect=prompts), patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert "conventions" in result.codemanifest_usages
        assert "custom" in result.codemanifest_usages
        assert result.codemanifest_usages["custom"] == ".goga/usages/custom.md"

    def test_questionnaire_ask_goga_config_custom_usages_no_convention(self) -> None:
        prompts = iter(
            [
                "python",  # language
                "custom",  # usage name
                ".goga/usages/custom.md",  # usage path
                "claude",  # agent
                "qarium/goga-python-3.12:1.0",  # image
                "claude",  # pipeline agent
            ]
        )
        confirms = iter(
            [
                False,  # Download base convention?
                True,  # Add codemanifest usages?
                False,  # Add another codemanifest usage? (stop)
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                False,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with patch("click.prompt", side_effect=prompts), patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.codemanifest_usages == {"custom": ".goga/usages/custom.md"}

    def test_questionnaire_ask_goga_config_custom_annotations_appended(self) -> None:
        prompts = iter(
            [
                "python",  # language
                "Custom rule for project",  # annotations text
                "claude",  # agent
                "qarium/goga-python-3.12:1.0",  # image
                "claude",  # pipeline agent
            ]
        )
        confirms = iter(
            [
                True,  # Download base convention?
                False,  # Add codemanifest usages?
                True,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                False,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with patch("click.prompt", side_effect=prompts), patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.codemanifest_annotations is not None
        assert result.codemanifest_annotations.startswith("Use")
        assert "Custom rule for project" in result.codemanifest_annotations
        assert "\n" in result.codemanifest_annotations

    def test_questionnaire_ask_goga_config_custom_image_with_predefined(self) -> None:
        prompts = iter(
            [
                "golang",  # language
                "claude",  # agent
                "my-custom/golang:2.0",  # image (custom, not from predefined list)
                "claude",  # pipeline agent
            ]
        )
        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                False,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with patch("click.prompt", side_effect=prompts), patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.language == "golang"
        assert result.image == "my-custom/golang:2.0"

    def test_questionnaire_ask_goga_config_kotlin_with_predefined_images(self) -> None:
        prompts = iter(
            [
                "kotlin",  # language
                "claude",  # agent
                "qarium/goga-kotlin-2.3.21:1.0",  # image (default from predefined list)
                "claude",  # pipeline agent
            ]
        )
        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                False,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with patch("click.prompt", side_effect=prompts), patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.language == "kotlin"
        assert result.image == "qarium/goga-kotlin-2.3.21:1.0"

    def test_questionnaire_ask_goga_config_swift_with_predefined_images(self) -> None:
        prompts = iter(
            [
                "swift",  # language
                "claude",  # agent
                "qarium/goga-swift-6.2.4:1.0",  # image (default from predefined list)
                "claude",  # pipeline agent
            ]
        )
        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                False,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with patch("click.prompt", side_effect=prompts), patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.language == "swift"
        assert result.image == "qarium/goga-swift-6.2.4:1.0"

    def test_questionnaire_ask_goga_config_javascript_with_predefined_images(self) -> None:
        prompts = iter(
            [
                "javascript",  # language
                "claude",  # agent
                "qarium/goga-node-24:1.0",  # image (default from predefined list)
                "claude",  # pipeline agent
            ]
        )
        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                False,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with patch("click.prompt", side_effect=prompts), patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.language == "javascript"
        assert result.image == "qarium/goga-node-24:1.0"

    def test_all_languages_have_image_map_entries(self) -> None:
        from goga.onboarding.questionnaire import _IMAGE_MAP, _LANGUAGES

        for language in _LANGUAGES:
            assert language in _IMAGE_MAP, f"Language '{language}' missing from _IMAGE_MAP"

    def test_image_map_defaults_use_version_1_2(self) -> None:
        """All suggested Docker images use the current default tag `:1.2`."""
        from goga.onboarding.questionnaire import _IMAGE_MAP

        for language, images in _IMAGE_MAP.items():
            assert images, f"Language '{language}' has no image entries"
            for image in images:
                assert image.endswith(":1.2"), f"Image '{image}' for language '{language}' must use the :1.2 tag"

    def test_questionnaire_ask_goga_config_duplicate_usage_name_skipped(self) -> None:
        prompts = iter(
            [
                "python",  # language
                "conventions",  # duplicate usage name (already set by convention)
                "custom",  # usage name (new, after loop continues)
                ".goga/usages/custom.md",  # usage path
                "claude",  # agent
                "qarium/goga-python-3.12:1.0",  # image
                "claude",  # pipeline agent
            ]
        )
        confirms = iter(
            [
                True,  # Download base convention?
                True,  # Add codemanifest usages?
                True,  # Add another codemanifest usage? (continue after duplicate skip)
                False,  # Add another codemanifest usage? (stop after custom added)
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                False,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with (
            patch("click.prompt", side_effect=prompts),
            patch("click.echo") as mock_echo,
            patch("click.confirm", side_effect=confirms),
        ):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.codemanifest_usages["conventions"] == ".goga/usages/conventions.md"
        assert "custom" in result.codemanifest_usages
        assert any('Usage "conventions" already exists, skipping.' in str(c) for c in mock_echo.call_args_list)

    def test_questionnaire_ask_returns_init_answers(self) -> None:
        prompts = iter(
            [
                "python",  # language
                "claude",  # agent
                "qarium/goga-python-3.12:1.0",  # image
                "claude",  # pipeline agent
            ]
        )
        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                False,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with patch("click.prompt", side_effect=prompts), patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask()

        assert isinstance(result, InitAnswers)
        assert isinstance(result.goga_config, GogaConfigAnswers)

    # --- New tests for Dockerfile and env suggestions ---

    def test_cpp_not_in_language_choices(self) -> None:
        """cpp must not appear in language choices."""
        from goga.onboarding.questionnaire import _LANGUAGES

        assert "cpp" not in _LANGUAGES

    def test_questionnaire_ask_goga_config_with_dockerfile(self) -> None:
        prompts = iter(
            [
                "python",  # language
                "claude",  # agent
                "Dockerfile",  # dockerfile path
                "qarium/goga-python-3.12:1.0",  # base image (FROM)
                "my-python-image:latest",  # built image name
                "claude",  # pipeline agent
            ]
        )
        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                True,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with (
            patch("click.prompt", side_effect=prompts),
            patch("click.confirm", side_effect=confirms),
            patch("goga.onboarding.questionnaire.resolve_project_name", return_value=None),
        ):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.dockerfile_path == "Dockerfile"
        assert result.dockerfile_base_image == "qarium/goga-python-3.12:1.0"
        assert result.image == "my-python-image:latest"

    def test_questionnaire_ask_goga_config_without_dockerfile_asks_pull_image(self) -> None:
        """Without a Dockerfile, only the pull image is asked (no base/name split)."""
        prompts = iter(
            [
                "python",  # language
                "claude",  # agent
                "qarium/goga-python-3.12:1.0",  # pull image
                "claude",  # pipeline agent
            ]
        )
        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                False,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with patch("click.prompt", side_effect=prompts), patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.dockerfile_path is None
        assert result.dockerfile_base_image is None
        assert result.image == "qarium/goga-python-3.12:1.0"

    def test_questionnaire_dockerfile_default_is_goga_dockerfile(self) -> None:
        """Step 7 default for Dockerfile path is `.goga/Dockerfile` (Enter accepted)."""
        other_prompts = iter(
            [
                "python",  # language
                "claude",  # agent
                "qarium/goga-python-3.12:1.0",  # base image (FROM)
                "my-python-image:latest",  # built image name
                "claude",  # pipeline agent
            ]
        )

        def fake_prompt(message, *args, **kwargs):
            # On the Dockerfile path prompt, simulate the user pressing Enter
            # (no interactive input) → click.prompt returns its `default`.
            if message == "Dockerfile path":
                return kwargs.get("default")
            return next(other_prompts)

        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                True,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with (
            patch("click.prompt", side_effect=fake_prompt),
            patch("click.confirm", side_effect=confirms),
            patch("goga.onboarding.questionnaire.resolve_project_name", return_value=None),
        ):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.dockerfile_path == ".goga/Dockerfile"

    def test_questionnaire_ask_goga_config_without_dockerfile(self) -> None:
        prompts = iter(
            [
                "python",  # language
                "claude",  # agent
                "qarium/goga-python-3.12:1.0",  # image
                "claude",  # pipeline agent
            ]
        )
        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                False,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with patch("click.prompt", side_effect=prompts), patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.dockerfile_path is None

    def test_questionnaire_env_suggested_keys_for_claude(self) -> None:
        prompts = iter(
            [
                "python",  # language
                "claude",  # agent
                "qarium/goga-python-3.12:1.0",  # image
                "https://api.z.ai/api/anthropic",  # ANTHROPIC_BASE_URL
                "glm-4.7",  # ANTHROPIC_DEFAULT_HAIKU_MODEL
                "glm-5-turbo",  # ANTHROPIC_DEFAULT_SONNET_MODEL
                "glm-5.1",  # ANTHROPIC_DEFAULT_OPUS_MODEL
                "glm-5.2",  # ANTHROPIC_MODEL
                "claude",  # pipeline agent
            ]
        )
        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                False,  # Create Dockerfile?
                True,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with patch("click.prompt", side_effect=prompts), patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.env == {
            "ANTHROPIC_BASE_URL": "https://api.z.ai/api/anthropic",
            "ANTHROPIC_DEFAULT_HAIKU_MODEL": "glm-4.7",
            "ANTHROPIC_DEFAULT_SONNET_MODEL": "glm-5-turbo",
            "ANTHROPIC_DEFAULT_OPUS_MODEL": "glm-5.1",
            "ANTHROPIC_MODEL": "glm-5.2",
        }

    def test_questionnaire_ask_goga_config_codex_agent(self) -> None:
        prompts = iter(
            [
                "python",  # language
                "codex",  # agent
                "qarium/goga-python-3.12:1.0",  # image
                "codex",  # pipeline agent
            ]
        )
        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                False,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with patch("click.prompt", side_effect=prompts), patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.agent == "codex"
        assert result.env is None

    def test_questionnaire_ask_goga_config_supports_new_agents(self) -> None:
        """The wizard accepts the full supported agent set (cursor build, qwen pipeline).

        Regression guard for the bug where build/pipeline agent selection only
        offered claude and codex despite cursor/opencode/qwen being supported.
        """
        prompts = iter(
            [
                "python",  # language
                "cursor",  # agent
                "qarium/goga-python-3.12:1.0",  # image
                "qwen",  # pipeline agent
            ]
        )
        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                False,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with patch("click.prompt", side_effect=prompts), patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.agent == "cursor"
        assert result.pipeline_agent == "qwen"
        assert result.env is None
        assert result.pipeline_env is None

    def test_questionnaire_codex_env_suggested_keys(self) -> None:
        prompts = iter(
            [
                "python",  # language
                "codex",  # agent
                "qarium/goga-python-3.12:1.0",  # image
                "o4-mini",  # CODEX_MODEL (task env)
                "codex",  # pipeline agent
            ]
        )
        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                False,  # Create Dockerfile?
                True,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with patch("click.prompt", side_effect=prompts), patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.env == {"CODEX_MODEL": "o4-mini"}

    def test_agent_env_map_contains_codex(self) -> None:
        from goga.onboarding.questionnaire import _AGENT_ENV_MAP

        assert "codex" in _AGENT_ENV_MAP
        assert _AGENT_ENV_MAP["codex"] == ["CODEX_MODEL"]

    def test_agents_choice_equals_agent_env_map_keys(self) -> None:
        """The build/pipeline agent choice list never drifts from _AGENT_ENV_MAP keys."""
        from goga.onboarding.questionnaire import _AGENT_ENV_MAP, _AGENTS

        assert list(_AGENT_ENV_MAP) == _AGENTS
        # Every previously-unselectable supported agent must now be offered.
        for agent in ("claude", "codex", "cursor", "opencode", "qwen"):
            assert agent in _AGENTS

    def test_agent_choice_accepts_all_supported_agents(self) -> None:
        """click.Choice built from _AGENTS validates every supported agent.

        Exercises the real click.Choice validation (convert raises BadParameter
        for values outside the choice set) — this is the guard that the mocked
        flow tests cannot exercise and that would have caught the original bug.
        """
        from click import Choice
        from click.exceptions import BadParameter
        from goga.onboarding.questionnaire import _AGENTS

        choice = Choice(_AGENTS)
        for agent in ("claude", "codex", "cursor", "opencode", "qwen"):
            assert choice.convert(agent, None, None) == agent

        # A value outside the supported set must still be rejected.
        with pytest.raises(BadParameter):
            choice.convert("not-a-real-agent", None, None)

    def test_questionnaire_env_skip_suggested_custom_only(self) -> None:
        prompts = iter(
            [
                "python",  # language
                "claude",  # agent
                "qarium/goga-python-3.12:1.0",  # image
                "MY_KEY",  # custom env key
                "my_value",  # custom env value
                "claude",  # pipeline agent
            ]
        )
        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                False,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                True,  # Add custom task env variable?
                False,  # Add custom task env variable? (stop)
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with patch("click.prompt", side_effect=prompts), patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.env == {"MY_KEY": "my_value"}

    # --- New tests for steps 9 (pipeline_agent) and 10 (pipeline_env) ---

    def test_questionnaire_pipeline_agent_does_not_inherit_build_agent(self) -> None:
        """The pipeline agent never defaults to the build agent — declining yields None."""
        prompts = iter(
            [
                "python",  # language
                "claude",  # agent
                "qarium/goga-python-3.12:1.0",  # image
            ]
        )
        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                False,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                False,  # Configure a pipeline agent? (decline → None)
                False,  # Add custom pipeline env variable?
            ]
        )

        with patch("click.prompt", side_effect=prompts), patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.agent == "claude"
        assert result.pipeline_agent is None

    def test_questionnaire_decline_both_agents_yields_none(self) -> None:
        """By default no agents are configured — declining both yields None for each."""
        prompts = iter(
            [
                "python",  # language
                "qarium/goga-python-3.12:1.0",  # image
            ]
        )
        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                False,  # Configure a build agent? (decline → None)
                False,  # Create Dockerfile?
                False,  # Add custom task env variable?
                False,  # Configure a pipeline agent? (decline → None)
                False,  # Add custom pipeline env variable?
            ]
        )

        with patch("click.prompt", side_effect=prompts), patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.agent is None
        assert result.pipeline_agent is None
        assert result.env is None
        assert result.pipeline_env is None

    def test_questionnaire_pipeline_agent_can_differ_from_build_agent(self) -> None:
        """The pipeline agent can be set independently and differ from the build agent."""
        prompts = iter(
            [
                "python",  # language
                "claude",  # agent
                "qarium/goga-python-3.12:1.0",  # image
                "codex",  # pipeline agent (override default)
            ]
        )
        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                False,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with patch("click.prompt", side_effect=prompts), patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.agent == "claude"
        assert result.pipeline_agent == "codex"

    def test_questionnaire_pipeline_env_collected_separately_from_task_env(self) -> None:
        """Step 10 collects pipeline env independently (codex suggested key)."""
        prompts = iter(
            [
                "python",  # language
                "claude",  # agent
                "qarium/goga-python-3.12:1.0",  # image
                "codex",  # pipeline agent
                "gpt-5",  # CODEX_MODEL (pipeline env)
            ]
        )
        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                False,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                True,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with patch("click.prompt", side_effect=prompts), patch("click.confirm", side_effect=confirms):
            q = Questionnaire()
            result = q.ask_goga_config()

        assert result.env is None
        assert result.pipeline_env == {"CODEX_MODEL": "gpt-5"}


class TestAskImageNameTwoMode:
    """Logic tests for the two-mode ask_image_name(language=None, default=None)."""

    def test_ask_image_name_accepts_default_from_resolve_project_name(self) -> None:
        """(a) positive — resolve_project_name → 'widget' → default 'widget:latest' accepted."""
        from goga.onboarding import questionnaire as qmod

        captured: dict = {}

        def fake_prompt(message, *args, **kwargs):
            # Record the default offered, then simulate the user accepting it.
            captured["default"] = kwargs.get("default")
            return kwargs.get("default")

        with (
            patch("goga.onboarding.questionnaire.resolve_project_name", return_value="widget"),
            patch("click.prompt", side_effect=fake_prompt),
            patch("click.echo"),
        ):
            # Mirror the consumer logic (ask_goga_config Dockerfile branch). Access
            # resolve_project_name through the module so the patch takes effect.
            name = qmod.resolve_project_name()
            default = f"{name}:latest" if name is not None else None
            image = qmod.Questionnaire().ask_image_name(language=None, default=default)

        assert name == "widget"
        assert captured["default"] == "widget:latest"
        assert image == "widget:latest"

    def test_ask_image_name_required_when_resolve_project_name_returns_none(self) -> None:
        """(b) negative — resolve_project_name → None → no default, image required.

        The offered default is None (click.prompt called with no default), so the
        user's first empty line is rejected and a real value is required.
        """
        from goga.onboarding import questionnaire as qmod

        captured: list[dict] = []

        def fake_prompt(message, *args, **kwargs):
            captured.append({"has_default": "default" in kwargs})
            # The implementation calls click.prompt("Built image name") (no default)
            # exactly once — return a real value.
            return "real-image:latest"

        with (
            patch("goga.onboarding.questionnaire.resolve_project_name", return_value=None),
            patch("click.prompt", side_effect=fake_prompt),
            patch("click.echo"),
        ):
            name = qmod.resolve_project_name()
            default = f"{name}:latest" if name is not None else None
            image = qmod.Questionnaire().ask_image_name(language=None, default=default)

        assert name is None
        assert default is None
        assert all(not c["has_default"] for c in captured)
        assert image == "real-image:latest"

    def test_ask_image_name_legacy_language_default_still_offered(self) -> None:
        """(c) legacy compatibility — ask_image_name(language='python') offers 'python-image:latest'."""
        captured: dict = {}

        def fake_prompt(message, *args, **kwargs):
            captured["default"] = kwargs.get("default")
            return kwargs.get("default")

        with patch("click.prompt", side_effect=fake_prompt), patch("click.echo"):
            image = Questionnaire().ask_image_name(language="python")

        assert captured["default"] == "python-image:latest"
        assert image == "python-image:latest"

    def test_ask_image_name_legacy_language_ignores_default_arg(self) -> None:
        """When language is provided, the default arg is ignored in favor of the legacy default."""
        captured: dict = {}

        def fake_prompt(message, *args, **kwargs):
            captured["default"] = kwargs.get("default")
            return "custom"

        with patch("click.prompt", side_effect=fake_prompt), patch("click.echo"):
            image = Questionnaire().ask_image_name(language="golang", default="ignored:latest")

        assert captured["default"] == "golang-image:latest"
        assert image == "custom"


class TestAskGogaConfigDockerfileBranch:
    """Logic tests for the ask_goga_config Dockerfile branch wiring of resolve_project_name."""

    def test_dockerfile_branch_uses_resolve_project_name_for_default(self) -> None:
        """(d) resolve_project_name → 'widget' → ask_image_name offered 'widget:latest'."""
        captured: dict = {}

        def fake_prompt(message, *args, **kwargs):
            if message == "Built image name":
                captured["default"] = kwargs.get("default")
                return kwargs.get("default")
            return "default-placeholder"

        prompts = iter(
            [
                "python",  # language
                "claude",  # agent
                "Dockerfile",  # dockerfile path
                "qarium/goga-python-3.12:1.0",  # base image (FROM)
                "claude",  # pipeline agent
            ]
        )

        def prompt_router(message, *args, **kwargs):
            if message == "Built image name":
                return fake_prompt(message, *args, **kwargs)
            return next(prompts)

        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                True,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with (
            patch("goga.onboarding.questionnaire.resolve_project_name", return_value="widget"),
            patch("click.prompt", side_effect=prompt_router),
            patch("click.confirm", side_effect=confirms),
        ):
            result = Questionnaire().ask_goga_config()

        assert captured["default"] == "widget:latest"
        assert result.image == "widget:latest"
        assert result.dockerfile_path == "Dockerfile"

    def test_dockerfile_branch_no_default_when_resolve_project_name_none(self) -> None:
        """(d) resolve_project_name → None → ask_image_name called with no default (image required)."""
        captured: list[dict] = []

        def fake_prompt(message, *args, **kwargs):
            if message == "Built image name":
                captured.append({"has_default": "default" in kwargs})
                return "provided-image:latest"
            return "default-placeholder"

        prompts = iter(
            [
                "python",  # language
                "claude",  # agent
                "Dockerfile",  # dockerfile path
                "qarium/goga-python-3.12:1.0",  # base image (FROM)
                "claude",  # pipeline agent
            ]
        )

        def prompt_router(message, *args, **kwargs):
            if message == "Built image name":
                return fake_prompt(message, *args, **kwargs)
            return next(prompts)

        confirms = iter(
            [
                False,  # Download base convention?
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                True,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with (
            patch("goga.onboarding.questionnaire.resolve_project_name", return_value=None),
            patch("click.prompt", side_effect=prompt_router),
            patch("click.confirm", side_effect=confirms),
        ):
            result = Questionnaire().ask_goga_config()

        assert all(not c["has_default"] for c in captured)
        assert result.image == "provided-image:latest"


class TestAskGogaConfigConditionalSkip:
    """Logic tests for the filesystem-conditional ask_goga_config behavior."""

    def test_ask_goga_config_returns_none_when_config_yml_exists(
        self,
        tmp_path,
        monkeypatch,
    ) -> None:
        """When .goga/config.yml exists, the whole config survey is skipped."""
        goga = tmp_path / ".goga"
        goga.mkdir()
        (goga / "config.yml").write_text("language: python\n")
        monkeypatch.chdir(tmp_path)

        # The survey must be fully skipped: nothing should be echoed, and no
        # prompt/confirm should fire. Patch them to raise if touched.
        with (
            patch("click.echo") as mock_echo,
            patch("click.prompt") as mock_prompt,
            patch("click.confirm") as mock_confirm,
        ):
            result = Questionnaire().ask_goga_config()

        assert result is None
        assert all("Collecting" not in str(c) for c in mock_echo.call_args_list)
        mock_prompt.assert_not_called()
        mock_confirm.assert_not_called()

    def test_ask_goga_config_skips_base_convention_when_conventions_md_exists(
        self,
        tmp_path,
        monkeypatch,
    ) -> None:
        """When conventions.md exists (config.yml absent), base convention is skipped.

        ask_base_convention must NOT be invoked — its prefill is (None, None).
        Drive the remaining survey deterministically and assert the result is
        assembled and "Base Convention" is never printed.
        """
        goga = tmp_path / ".goga"
        usages = goga / "usages"
        usages.mkdir(parents=True)
        (usages / "conventions.md").write_text("# conventions\n")
        monkeypatch.chdir(tmp_path)

        prompts = iter(
            [
                "python",  # language
                "claude",  # agent
                "qarium/goga-python-3.12:1.0",  # image
                "claude",  # pipeline agent
            ]
        )
        # No "Download base convention?" confirm — that step is skipped. The
        # confirms below follow the survey order AFTER ask_base_convention.
        confirms = iter(
            [
                False,  # Add codemanifest usages?
                False,  # Add codemanifest annotations?
                True,  # Configure a build agent?
                False,  # Create Dockerfile?
                False,  # Set suggested task env variables?
                False,  # Add custom task env variable?
                True,  # Configure a pipeline agent?
                False,  # Set suggested pipeline env variables?
                False,  # Add custom pipeline env variable?
            ]
        )

        with (
            patch("click.prompt", side_effect=prompts),
            patch("click.echo") as mock_echo,
            patch("click.confirm", side_effect=confirms),
        ):
            result = Questionnaire().ask_goga_config()

        assert result is not None
        # base convention prefill is (None, None), so no conventions entry is added
        assert result.codemanifest_usages is None
        assert result.codemanifest_annotations is None
        assert all("Base Convention" not in str(c) for c in mock_echo.call_args_list)

    def test_ask_wraps_none_into_init_answers_when_config_yml_exists(
        self,
        tmp_path,
        monkeypatch,
    ) -> None:
        """ask() wraps the Optional result (None) into InitAnswers transparently."""
        goga = tmp_path / ".goga"
        goga.mkdir()
        (goga / "config.yml").write_text("language: python\n")
        monkeypatch.chdir(tmp_path)

        with patch("click.prompt"), patch("click.confirm"):
            result = Questionnaire().ask()

        assert isinstance(result, InitAnswers)
        assert result.goga_config is None
