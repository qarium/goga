from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner
from goga.commands.config import config

_CONFIG_FILE = Path(".goga") / "config.yml"


def _run_with_config(tmp_path: Path, args: list[str]):
    """Run config command with cwd set to tmp_path."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=tmp_path.parent):
        goga_dir = Path(".goga")
        goga_dir.mkdir(exist_ok=True)
        (goga_dir / "config.yml").write_text((tmp_path / _CONFIG_FILE).read_text())
        return runner.invoke(config, args)


class TestContract:
    """Contract-level tests for config command."""

    def test_config_importable_from_facade(self) -> None:
        from goga.commands import config as facade_config

        assert facade_config is config

    def test_config_is_click_command(self) -> None:
        runner = CliRunner()
        result = runner.invoke(config, ["--help"])
        assert result.exit_code == 0
        assert "option" in result.output

    def test_config_requires_option_argument(self) -> None:
        runner = CliRunner()
        result = runner.invoke(config, [])
        assert result.exit_code != 0

    def test_config_multiple_options_output_headers_and_values(self, full_config) -> None:
        result = _run_with_config(full_config, ["language", "build.agent", "build.review.strategy"])
        assert result.exit_code == 0
        assert "# language\npython\n" in result.output
        assert "# build.agent\nclaude\n" in result.output
        assert "# build.review.strategy\nshort\n" in result.output
        # Check separators (blank lines between options)
        lines = result.output.split("\n")
        # After "python" there should be a blank line before "# build.agent"
        idx = lines.index("python")
        assert lines[idx + 1] == ""


class TestPositive:
    """Positive scenarios for config command."""

    def test_config_language_returns_str(self, full_config) -> None:
        result = _run_with_config(full_config, ["language"])
        assert result.exit_code == 0
        assert result.output == "# language\npython\n"

    def test_config_build_agent_returns_str(self, full_config) -> None:
        result = _run_with_config(full_config, ["build.agent"])
        assert result.exit_code == 0
        assert result.output == "# build.agent\nclaude\n"

    def test_config_build_returns_yaml(self, full_config) -> None:
        result = _run_with_config(full_config, ["build"])
        assert result.exit_code == 0
        assert result.output.startswith("# build\n")
        assert "review:" in result.output
        assert "agent: claude" in result.output

    def test_config_commands_returns_yaml_dict(self, full_config) -> None:
        result = _run_with_config(full_config, ["commands"])
        assert result.exit_code == 0
        assert result.output.startswith("# commands\n")
        assert "test: pytest" in result.output

    def test_config_none_value_outputs_null(self, minimal_config) -> None:
        result = _run_with_config(minimal_config, ["build.review"])
        assert result.exit_code == 0
        assert result.output == "# build.review\nnull\n"

    def test_config_bool_value_outputs_true_false(self, full_config) -> None:
        result = _run_with_config(full_config, ["build.review.skip"])
        assert result.exit_code == 0
        assert result.output == "# build.review.skip\nTrue\n"

    def test_config_build_env_returns_yaml(self, full_config) -> None:
        result = _run_with_config(full_config, ["build.env"])
        assert result.exit_code == 0
        assert result.output.startswith("# build.env\n")
        assert "API_KEY: sk-xxx" in result.output
        assert "MODEL: claude-sonnet-4-6" in result.output

    def test_config_str_optional_field_value(self, full_config) -> None:
        result = _run_with_config(full_config, ["build.session_timeout"])
        assert result.exit_code == 0
        assert result.output == "# build.session_timeout\n30m\n"

    def test_config_dict_key_traversal(self, full_config) -> None:
        result = _run_with_config(full_config, ["build.env.API_KEY"])
        assert result.exit_code == 0
        assert result.output == "# build.env.API_KEY\nsk-xxx\n"

    def test_config_dict_key_not_found(self, full_config) -> None:
        result = _run_with_config(full_config, ["build.env.NONEXISTENT"])
        assert result.exit_code == 1
        assert "Option not found" in result.output

    def test_config_commands_dict_key(self, full_config) -> None:
        result = _run_with_config(full_config, ["commands.test"])
        assert result.exit_code == 0
        assert result.output == "# commands.test\npytest\n"

    def test_config_multiple_mixed_types(self, full_config) -> None:
        result = _run_with_config(
            full_config,
            ["build.session_timeout", "build", "build.agent"],
        )
        assert result.exit_code == 0
        assert "# build.session_timeout\n30m\n" in result.output
        assert "# build\n" in result.output
        assert "# build.agent\nclaude\n" in result.output
        # Verify separators between options
        lines = result.output.split("\n")
        # Find "30m" and check blank line follows
        idx = lines.index("30m")
        assert lines[idx + 1] == ""

    def test_config_review_additional_patience_option(self, full_config) -> None:
        result = _run_with_config(full_config, ["build.review.additional.patience"])
        assert result.exit_code == 0
        assert result.output == "# build.review.additional.patience\n3\n"


class TestNegative:
    """Negative/error scenarios for config command."""

    def test_config_missing_goga_config(self, tmp_path) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(config, ["language"])
        assert result.exit_code != 0
        assert ".goga/config.yml" in result.output

    def test_config_empty_goga_config(self, tmp_path) -> None:
        goga_dir = tmp_path / ".goga"
        goga_dir.mkdir()
        config_file = goga_dir / "config.yml"
        config_file.write_text("")
        result = _run_with_config(tmp_path, ["language"])
        assert result.exit_code != 0

    def test_config_invalid_yaml(self, tmp_path) -> None:
        goga_dir = tmp_path / ".goga"
        goga_dir.mkdir()
        config_file = goga_dir / "config.yml"
        config_file.write_text("language: python\n  bad indent: oops\n")
        result = _run_with_config(tmp_path, ["language"])
        assert result.exit_code != 0

    def test_config_missing_build_section(self, tmp_path) -> None:
        """Under the optional-sections contract, a build section is NOT required;
        a language-only config is valid and introspection succeeds."""
        goga_dir = tmp_path / ".goga"
        goga_dir.mkdir()
        config_file = goga_dir / "config.yml"
        config_file.write_text("language: python\n")
        result = _run_with_config(tmp_path, ["language"])
        assert result.exit_code == 0
        assert result.output == "# language\npython\n"

    def test_config_empty_option(self, minimal_config) -> None:
        result = _run_with_config(minimal_config, [""])
        assert result.exit_code == 1

    def test_config_option_not_found_outputs_error(self, minimal_config) -> None:
        result = _run_with_config(minimal_config, ["nonexistent.path"])
        assert result.exit_code == 1
        assert "Option not found: nonexistent.path" in result.output

    def test_config_lang_alias_gone_option_not_found(self, minimal_config) -> None:
        """The alias bridge is deleted — one vocabulary: `lang` no longer resolves."""
        result = _run_with_config(minimal_config, ["lang"])
        assert result.exit_code == 1
        assert "Option not found: lang" in result.output

    def test_config_second_option_not_found_stops_after_first(self, full_config) -> None:
        result = _run_with_config(full_config, ["language", "nonexistent"])
        assert result.exit_code == 1
        assert "# language\npython" in result.output
        assert "Option not found: nonexistent" in result.output

    def test_config_first_option_not_found_stops_execution(self, full_config) -> None:
        result = _run_with_config(full_config, ["nonexistent", "language"])
        assert result.exit_code == 1
        assert "# language" not in result.output


class TestEdgeCases:
    """Edge case scenarios for config command."""

    def test_config_int_value(self, full_config) -> None:
        result = _run_with_config(full_config, ["build.max_iterations"])
        assert result.exit_code == 0
        assert result.output == "# build.max_iterations\n10\n"

    def test_config_review_strategy_str_value(self, tmp_path) -> None:
        goga_dir = tmp_path / ".goga"
        goga_dir.mkdir()
        config_file = goga_dir / "config.yml"
        config_file.write_text(
            "language: python\nbuild:\n  agent: claude\n  review:\n    strategy: short\n"
            "pipeline:\n  agent: claude\n"
        )
        result = _run_with_config(tmp_path, ["build.review.strategy"])
        assert result.exit_code == 0
        assert result.output == "# build.review.strategy\nshort\n"

    def test_config_private_attribute_rejected(self, full_config) -> None:
        result = _run_with_config(full_config, ["build._agent"])
        assert result.exit_code == 1
        assert "Option not found: build._agent" in result.output

    def test_config_scalar_traversal_returns_not_found(self, full_config) -> None:
        result = _run_with_config(full_config, ["language.foo"])
        assert result.exit_code == 1
        assert "Option not found: language.foo" in result.output

    def test_config_bool_value_output_format(self, full_config) -> None:
        result = _run_with_config(
            full_config,
            ["build.review.skip", "build.session_timeout"],
        )
        assert result.exit_code == 0
        assert "# build.review.skip\nTrue\n" in result.output
        assert "# build.session_timeout\n30m\n" in result.output
        # Verify separator
        lines = result.output.split("\n")
        idx = lines.index("True")
        assert lines[idx + 1] == ""

    def test_config_duplicate_option_outputs_each_occurrence(self, full_config) -> None:
        result = _run_with_config(full_config, ["language", "language"])
        assert result.exit_code == 0
        assert result.output == "# language\npython\n\n# language\npython\n"


class TestUsagesRendering:
    """Dataclass-aware YAML rendering for the usages section (Task 14).

    Verifies that ``DepConfig`` instances nested inside dicts (group-level and
    whole-section paths) render as clean YAML mappings instead of the default
    ``!!python/object:`` tag / ``RepresenterError``.
    """

    def test_config_usages_dot_notation_renders_depcfg(self, usages_config) -> None:
        result = _run_with_config(usages_config, ["usages.libs.click"])
        assert result.exit_code == 0
        assert "git: https://example.com/click.git" in result.output
        assert "ref: main" in result.output
        assert "!!python/object:" not in result.output

    def test_config_usages_group_renders_full_yaml(self, usages_config) -> None:
        result = _run_with_config(usages_config, ["usages.libs"])
        assert result.exit_code == 0
        assert "click:" in result.output
        assert "another:" in result.output
        assert "git:" in result.output
        assert "ref: main" in result.output
        assert "!!python/object:" not in result.output
        # None-valued fields are dropped: ``another`` has no ref → no ``ref: null``
        assert "ref: null" not in result.output

    def test_config_usages_whole_section_renders_full_yaml(self, usages_config) -> None:
        result = _run_with_config(usages_config, ["usages"])
        assert result.exit_code == 0
        assert "libs:" in result.output
        assert "click:" in result.output
        assert "another:" in result.output
        assert "git:" in result.output
        assert "ref: main" in result.output
        assert "!!python/object:" not in result.output
        # None-valued fields are dropped: ``another`` has no ref → no ``ref: null``
        assert "ref: null" not in result.output
