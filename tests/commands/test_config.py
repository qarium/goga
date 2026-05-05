from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner
from goga.commands.config import config


def _run_with_config(config_path: Path, args: list[str]):
    """Run config command with cwd set to config_path."""
    runner = CliRunner()
    with runner.isolated_filesystem(temp_dir=config_path.parent):
        # Copy .goga.yml into isolated filesystem
        target = Path(".goga.yml")
        target.write_text(config_path.read_text())
        return runner.invoke(config, args)


class TestContract:
    """Contract-level tests for config command."""

    def test_config_importable_from_facade(self) -> None:
        from goga.commands import config as facade_config  # noqa: PLC0415

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
        result = _run_with_config(
            full_config / ".goga.yml",
            ["language", "build.task_executor.agent", "build.worktree"],
        )
        assert result.exit_code == 0
        assert "# language\npython\n" in result.output
        assert "# build.task_executor.agent\nclaude\n" in result.output
        assert "# build.worktree\nTrue\n" in result.output
        # Check separators (blank lines between options)
        lines = result.output.split("\n")
        # After "python" there should be a blank line before "# build.task_executor.agent"
        idx = lines.index("python")
        assert lines[idx + 1] == ""


class TestPositive:
    """Positive scenarios for config command."""

    def test_config_language_returns_str(self, full_config) -> None:
        result = _run_with_config(full_config / ".goga.yml", ["language"])
        assert result.exit_code == 0
        assert result.output == "# language\npython\n"

    def test_config_build_task_executor_agent_returns_str(self, full_config) -> None:
        result = _run_with_config(full_config / ".goga.yml", ["build.task_executor.agent"])
        assert result.exit_code == 0
        assert result.output == "# build.task_executor.agent\nclaude\n"

    def test_config_build_returns_yaml(self, full_config) -> None:
        result = _run_with_config(full_config / ".goga.yml", ["build"])
        assert result.exit_code == 0
        assert result.output.startswith("# build\n")
        assert "task_executor:" in result.output
        assert "agent: claude" in result.output

    def test_config_commands_returns_yaml_dict(self, full_config) -> None:
        result = _run_with_config(full_config / ".goga.yml", ["commands"])
        assert result.exit_code == 0
        assert result.output.startswith("# commands\n")
        assert "test: pytest" in result.output

    def test_config_none_value_outputs_null(self, minimal_config) -> None:
        result = _run_with_config(minimal_config / ".goga.yml", ["build.worktree"])
        assert result.exit_code == 0
        assert result.output == "# build.worktree\nnull\n"

    def test_config_bool_value_outputs_true_false(self, full_config) -> None:
        result = _run_with_config(full_config / ".goga.yml", ["build.worktree"])
        assert result.exit_code == 0
        assert result.output == "# build.worktree\nTrue\n"

    def test_config_build_task_executor_env_returns_yaml(self, full_config) -> None:
        result = _run_with_config(full_config / ".goga.yml", ["build.task_executor.env"])
        assert result.exit_code == 0
        assert result.output.startswith("# build.task_executor.env\n")
        assert "API_KEY: sk-xxx" in result.output
        assert "MODEL: claude-sonnet-4-6" in result.output

    def test_config_str_optional_field_value(self, full_config) -> None:
        result = _run_with_config(full_config / ".goga.yml", ["build.session_timeout"])
        assert result.exit_code == 0
        assert result.output == "# build.session_timeout\n30m\n"

    def test_config_dict_key_traversal(self, full_config) -> None:
        result = _run_with_config(full_config / ".goga.yml", ["build.task_executor.env.API_KEY"])
        assert result.exit_code == 0
        assert result.output == "# build.task_executor.env.API_KEY\nsk-xxx\n"

    def test_config_dict_key_not_found(self, full_config) -> None:
        result = _run_with_config(full_config / ".goga.yml", ["build.task_executor.env.NONEXISTENT"])
        assert result.exit_code == 1
        assert "Option not found" in result.output

    def test_config_commands_dict_key(self, full_config) -> None:
        result = _run_with_config(full_config / ".goga.yml", ["commands.test"])
        assert result.exit_code == 0
        assert result.output == "# commands.test\npytest\n"

    def test_config_multiple_mixed_types(self, full_config) -> None:
        result = _run_with_config(
            full_config / ".goga.yml",
            ["build.session_timeout", "build", "build.task_executor.agent"],
        )
        assert result.exit_code == 0
        assert "# build.session_timeout\n30m\n" in result.output
        assert "# build\n" in result.output
        assert "# build.task_executor.agent\nclaude\n" in result.output
        # Verify separators between options
        lines = result.output.split("\n")
        # Find "30m" and check blank line follows
        idx = lines.index("30m")
        assert lines[idx + 1] == ""

    def test_config_skip_finalize_option(self, full_config) -> None:
        result = _run_with_config(full_config / ".goga.yml", ["build.skip_finalize"])
        assert result.exit_code == 0
        assert result.output == "# build.skip_finalize\nFalse\n"


class TestNegative:
    """Negative/error scenarios for config command."""

    def test_config_missing_goga_yml(self, tmp_path) -> None:
        runner = CliRunner()
        with runner.isolated_filesystem(temp_dir=tmp_path):
            result = runner.invoke(config, ["language"])
        assert result.exit_code != 0
        assert ".goga.yml" in result.output

    def test_config_empty_goga_yml(self, tmp_path) -> None:
        config_file = tmp_path / ".goga.yml"
        config_file.write_text("")
        result = _run_with_config(config_file, ["language"])
        assert result.exit_code != 0

    def test_config_invalid_yaml(self, tmp_path) -> None:
        config_file = tmp_path / ".goga.yml"
        config_file.write_text("language: python\n  bad indent: oops\n")
        result = _run_with_config(config_file, ["language"])
        assert result.exit_code != 0

    def test_config_missing_build_section(self, tmp_path) -> None:
        config_file = tmp_path / ".goga.yml"
        config_file.write_text("language: python\n")
        result = _run_with_config(config_file, ["language"])
        assert result.exit_code != 0

    def test_config_empty_option(self, minimal_config) -> None:
        result = _run_with_config(minimal_config / ".goga.yml", [""])
        assert result.exit_code == 1

    def test_config_option_not_found_outputs_error(self, minimal_config) -> None:
        result = _run_with_config(minimal_config / ".goga.yml", ["nonexistent.path"])
        assert result.exit_code == 1
        assert "Option not found: nonexistent.path" in result.output

    def test_config_second_option_not_found_stops_after_first(self, full_config) -> None:
        result = _run_with_config(full_config / ".goga.yml", ["language", "nonexistent"])
        assert result.exit_code == 1
        assert "# language\npython" in result.output
        assert "Option not found: nonexistent" in result.output

    def test_config_first_option_not_found_stops_execution(self, full_config) -> None:
        result = _run_with_config(full_config / ".goga.yml", ["nonexistent", "language"])
        assert result.exit_code == 1
        assert "# language" not in result.output


class TestEdgeCases:
    """Edge case scenarios for config command."""

    def test_config_int_value(self, full_config) -> None:
        result = _run_with_config(full_config / ".goga.yml", ["build.max_iterations"])
        assert result.exit_code == 0
        assert result.output == "# build.max_iterations\n10\n"

    def test_config_codex_review_false(self, tmp_path) -> None:
        config_file = tmp_path / ".goga.yml"
        config_file.write_text(
            "language: python\n"
            "build:\n"
            "  task_executor:\n"
            "    agent: claude\n"
            "  codex_review: false\n"
        )
        result = _run_with_config(config_file, ["build.codex_review"])
        assert result.exit_code == 0
        assert result.output == "# build.codex_review\nFalse\n"

    def test_config_private_attribute_rejected(self, full_config) -> None:
        result = _run_with_config(full_config / ".goga.yml", ["build._task_executor"])
        assert result.exit_code == 1
        assert "Option not found: build._task_executor" in result.output

    def test_config_scalar_traversal_returns_not_found(self, full_config) -> None:
        result = _run_with_config(full_config / ".goga.yml", ["language.foo"])
        assert result.exit_code == 1
        assert "Option not found: language.foo" in result.output

    def test_config_bool_value_output_format(self, full_config) -> None:
        result = _run_with_config(
            full_config / ".goga.yml",
            ["build.worktree", "build.codex_review"],
        )
        assert result.exit_code == 0
        assert "# build.worktree\nTrue\n" in result.output
        assert "# build.codex_review\nTrue\n" in result.output
        # Verify separator
        lines = result.output.split("\n")
        idx = lines.index("True")
        assert lines[idx + 1] == ""

    def test_config_duplicate_option_outputs_each_occurrence(self, full_config) -> None:
        result = _run_with_config(full_config / ".goga.yml", ["language", "language"])
        assert result.exit_code == 0
        assert result.output == "# language\npython\n\n# language\npython\n"
