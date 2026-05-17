"""Integration tests for commands-split: CLI wrappers delegate to business logic cells."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest import mock

import yaml
from click.testing import CliRunner
from goga.cli import app
from goga.commands.sync import sync as sync_cli
from goga.commands.schema import schema as schema_cli
from goga.commands.build import build as build_cli
from goga.commands.install import install as install_cli

from tests.conftest import cwd as _cwd


# --- sync delegation ---


class TestSyncDelegation:
    def test_sync_delegates_to_sync_logic_with_args(self, tmp_path: Path) -> None:
        source = tmp_path / "lib"
        source.mkdir()
        (source / ".usages").mkdir()
        (source / ".usages" / "api.md").write_text("# API", encoding="utf-8")

        with (
            mock.patch("goga.commands.sync.sync_logic", return_value=0) as mock_logic,
            _cwd(tmp_path),
        ):
            runner = CliRunner()
            result = runner.invoke(sync_cli, [str(source), "--token", "ghp_x", "--branch", "main"])

        mock_logic.assert_called_once_with(str(source), "ghp_x", "main")
        assert result.exit_code == 0

    def test_sync_delegates_exit_code_1(self) -> None:
        with mock.patch("goga.commands.sync.sync_logic", return_value=1):
            runner = CliRunner()
            result = runner.invoke(sync_cli, ["/nonexistent"])

        assert result.exit_code == 1

    def test_sync_delegates_with_none_defaults(self) -> None:
        with mock.patch("goga.commands.sync.sync_logic", return_value=0) as mock_logic:
            runner = CliRunner()
            runner.invoke(sync_cli, ["https://github.com/user/repo"])

        mock_logic.assert_called_once_with("https://github.com/user/repo", None, None)

    def test_sync_cli_registered_in_app(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["sync", "--help"])
        assert result.exit_code == 0
        assert "source" in result.output.lower()


# --- schema delegation ---


class TestSchemaDelegation:
    def test_schema_delegates_to_schema_logic(self, tmp_path: Path) -> None:
        (tmp_path / "CODEMANIFEST").write_text(
            'Usages: {}\n\nAnnotations: ""\n\n---\n\n---\nAuthor: T\nCreatedAt: 01/01/01\nDescription: D\n',
            encoding="utf-8",
        )

        with (
            mock.patch(
                "goga.commands.schema.schema_logic", return_value='[{"cell": "."}]'
            ) as mock_logic,
            _cwd(tmp_path),
        ):
            runner = CliRunner()
            result = runner.invoke(schema_cli, [])

        mock_logic.assert_called_once_with([], None, [])
        assert result.exit_code == 0
        assert '"cell": "."' in result.output

    def test_schema_delegates_with_cells_and_options(self, tmp_path: Path) -> None:
        with (
            mock.patch(
                "goga.commands.schema.schema_logic", return_value='[{"cell": "pkg_a"}]'
            ) as mock_logic,
            _cwd(tmp_path),
        ):
            runner = CliRunner()
            result = runner.invoke(schema_cli, ["pkg_a", "--max-depth", "2", "--depends-on", "lib"])

        mock_logic.assert_called_once_with(["pkg_a"], 2, ["lib"])
        assert result.exit_code == 0

    def test_schema_handles_value_error_from_logic(self, tmp_path: Path) -> None:
        with (
            mock.patch(
                "goga.commands.schema.schema_logic", side_effect=ValueError("2 error(s) found")
            ),
            _cwd(tmp_path),
        ):
            runner = CliRunner()
            result = runner.invoke(schema_cli, [])

        assert result.exit_code == 1
        assert "error" in result.output.lower()

    def test_schema_cli_registered_in_app(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["schema", "--help"])
        assert result.exit_code == 0
        assert "cells" in result.output.lower()


# --- build delegation ---


def _write_goga_yml(tmp_path: Path) -> None:
    (tmp_path / ".goga").mkdir(exist_ok=True)
    (tmp_path / ".goga" / "config.yml").write_text(
        "language: python\nbuild:\n  task_executor:\n    agent: claude\n"
    )


class TestBuildDelegation:
    def test_build_delegates_to_build_logic(self, tmp_path: Path) -> None:
        _write_goga_yml(tmp_path)

        with (
            mock.patch("goga.commands.build.build_logic", return_value=0) as mock_logic,
            _cwd(tmp_path),
        ):
            runner = CliRunner()
            result = runner.invoke(
                build_cli,
                ["--skip-manifest-check", "--dry-run", "plan.md"],
            )

        assert result.exit_code == 0
        call_args = mock_logic.call_args
        assert call_args[0][0] == "plan.md"
        cli_options = call_args[0][2]
        assert cli_options["dry_run"] is True
        assert cli_options["skip_manifest_check"] is True

    def test_build_delegates_exit_code(self, tmp_path: Path) -> None:
        _write_goga_yml(tmp_path)

        with (
            mock.patch("goga.commands.build.build_logic", return_value=42),
            _cwd(tmp_path),
        ):
            runner = CliRunner()
            result = runner.invoke(build_cli, ["--skip-manifest-check", "plan.md"])

        assert result.exit_code == 42

    def test_build_config_error_raises_click_exception(self, tmp_path: Path) -> None:
        with _cwd(tmp_path):
            runner = CliRunner()
            result = runner.invoke(build_cli, ["--skip-manifest-check", "plan.md"])

        assert result.exit_code != 0
        assert "config" in result.output.lower()

    def test_build_cli_registered_in_app(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["build", "--help"])
        assert result.exit_code == 0
        assert "plan" in result.output.lower()

    def test_build_passes_all_cli_options(self, tmp_path: Path) -> None:
        _write_goga_yml(tmp_path)

        with (
            mock.patch("goga.commands.build.build_logic", return_value=0) as mock_logic,
            _cwd(tmp_path),
        ):
            runner = CliRunner()
            result = runner.invoke(
                build_cli,
                [
                    "--skip-manifest-check",
                    "--worktree",
                    "--skip-finalize",
                    "--session-timeout", "30m",
                    "--idle-timeout", "5m",
                    "--wait", "10s",
                    "--max-iterations", "5",
                    "--review-patience", "3",
                    "my-plan.md",
                ],
            )

        assert result.exit_code == 0
        cli_options = mock_logic.call_args[0][2]
        assert cli_options["worktree"] is True
        assert cli_options["skip_finalize"] is True
        assert cli_options["session_timeout"] == "30m"
        assert cli_options["idle_timeout"] == "5m"
        assert cli_options["wait"] == "10s"
        assert cli_options["max_iterations"] == 5
        assert cli_options["review_patience"] == 3


# --- install delegation ---


def _mock_urlopen_response(content: bytes = b"dsl content") -> mock.MagicMock:
    mock_response = mock.MagicMock()
    mock_response.read.return_value = content
    mock_response.__enter__.return_value = mock_response
    return mock_response


class TestInstallDelegation:
    def test_install_delegates_to_install_logic(self, tmp_path: Path) -> None:
        with (
            mock.patch("goga.commands.install.install_logic", return_value=0) as mock_logic,
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            mock.patch("urllib.request.urlopen", return_value=_mock_urlopen_response()),
            _cwd(tmp_path),
        ):
            _write_goga_yml(tmp_path)
            runner = CliRunner()
            result = runner.invoke(install_cli, [])

        assert result.exit_code == 0
        call_args = mock_logic.call_args
        assert call_args[0][0] is None  # agent=None

    def test_install_delegates_with_agent(self, tmp_path: Path) -> None:
        with (
            mock.patch("goga.commands.install.install_logic", return_value=0) as mock_logic,
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            _cwd(tmp_path),
        ):
            _write_goga_yml(tmp_path)
            runner = CliRunner()
            result = runner.invoke(install_cli, ["--agent", "claude"])

        assert result.exit_code == 0
        call_args = mock_logic.call_args
        assert call_args[0][0] == "claude"

    def test_install_delegates_exit_code_1(self, tmp_path: Path) -> None:
        with (
            mock.patch("goga.commands.install.install_logic", return_value=1) as mock_logic,
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            _cwd(tmp_path),
        ):
            _write_goga_yml(tmp_path)
            runner = CliRunner()
            result = runner.invoke(install_cli, ["--agent", "unknown"])

        assert result.exit_code == 1

    def test_install_config_error_raises_click_exception(self, tmp_path: Path) -> None:
        with (
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            _cwd(tmp_path),
        ):
            runner = CliRunner()
            result = runner.invoke(install_cli, [])

        assert result.exit_code != 0
        assert "config" in result.output.lower()

    def test_install_cli_registered_in_app(self) -> None:
        runner = CliRunner()
        result = runner.invoke(app, ["install", "--help"])
        assert result.exit_code == 0
        assert "agent" in result.output.lower()


# --- cross-cutting: all commands delegate through app ---


class TestAllCommandsDelegationViaApp:
    def test_sync_via_app_delegates(self, tmp_path: Path) -> None:
        with mock.patch("goga.commands.sync.sync_logic", return_value=0) as mock_logic:
            runner = CliRunner()
            result = runner.invoke(app, ["sync", "/some/path"])

        mock_logic.assert_called_once_with("/some/path", None, None)
        assert result.exit_code == 0

    def test_schema_via_app_delegates(self, tmp_path: Path) -> None:
        with (
            mock.patch(
                "goga.commands.schema.schema_logic", return_value="[]"
            ) as mock_logic,
            _cwd(tmp_path),
        ):
            runner = CliRunner()
            result = runner.invoke(app, ["schema"])

        mock_logic.assert_called_once_with([], None, [])
        assert result.exit_code == 0
        assert "[]" in result.output

    def test_build_via_app_delegates(self, tmp_path: Path) -> None:
        _write_goga_yml(tmp_path)

        with (
            mock.patch("goga.commands.build.build_logic", return_value=0) as mock_logic,
            _cwd(tmp_path),
        ):
            runner = CliRunner()
            result = runner.invoke(app, ["build", "--skip-manifest-check", "plan.md"])

        assert result.exit_code == 0
        assert mock_logic.call_args[0][0] == "plan.md"

    def test_install_via_app_delegates(self, tmp_path: Path) -> None:
        _write_goga_yml(tmp_path)

        with (
            mock.patch("goga.commands.install.install_logic", return_value=0) as mock_logic,
            mock.patch("pathlib.Path.home", return_value=tmp_path),
            _cwd(tmp_path),
        ):
            runner = CliRunner()
            result = runner.invoke(app, ["install"])

        assert result.exit_code == 0
        assert mock_logic.call_args[0][0] is None
