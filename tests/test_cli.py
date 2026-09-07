from __future__ import annotations

import inspect
import json
import runpy
import sys
from importlib.metadata import PackageNotFoundError
from pathlib import Path
from types import ModuleType
from typing import Any
from unittest import mock

import click
import pytest
from click.testing import CliRunner
from goga import app, commands
from goga import cli as cli_module
from goga.cli import app as cli_app

from tests.conftest import cwd as _cwd

SIMPLE_MANIFEST = """\
Usages: {}

Annotations: ""

---
"TestEntity()":
  location: entity.py
  annotations: ""

---
Author: Test
CreatedAt: 01/01/01
Description: Integration test cell
"""


class TestFacadeAvailability:
    def test_import_app_from_goga(self) -> None:
        """The app symbol is importable from the goga package."""
        assert app is not None

    def test_import_app_from_cli_module(self) -> None:
        """The app symbol is also available from goga.cli."""
        assert cli_app is not None

    def test_both_imports_reference_same_object(self) -> None:
        """goga.app and goga.cli.app reference the same object."""
        assert app is cli_app


class TestModuleEntrypoint:
    def test_python_dash_m_goga_runs_the_root_app(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """``python -m goga`` dispatches to the root app — the workflow's entrypoint."""
        monkeypatch.setattr(sys, "argv", ["goga", "history", "path", "-f", "plan.md"])
        sys.modules.pop("goga.__main__", None)

        with mock.patch.object(cli_module, "app", return_value=0) as app_mock:
            runpy.run_module("goga", run_name="__main__")

        assert app_mock.call_args == mock.call()


class TestApiShape:
    def test_app_is_click_group(self) -> None:
        """The app object is a click Group instance."""
        assert isinstance(app, click.Group)

    def test_app_is_not_plain_command(self) -> None:
        """The app object is not a plain click Command (it is a Group)."""
        # Group is a subclass of Command, so isinstance(app, Command) is True,
        # but we specifically want it to be a Group.
        assert type(app) is click.Group or isinstance(app, click.Group)


class TestRegisteredCommands:
    def test_commands_dict_exists(self) -> None:
        """The app has a commands dictionary."""
        assert hasattr(app, "commands")
        assert isinstance(app.commands, dict)

    def test_lint_command_registered(self) -> None:
        """The 'lint' command is registered on the app group."""
        assert "lint" in app.commands

    def test_build_command_registered(self) -> None:
        """The 'build' command is registered on the app group."""
        assert "build" in app.commands

    def test_connect_command_registered(self) -> None:
        """The 'connect' command is registered on the app group."""
        assert "connect" in app.commands

    def test_both_commands_registered(self) -> None:
        """Both 'lint' and 'build' commands are present in app.commands."""
        command_names = set(app.commands.keys())
        assert {"lint", "build"}.issubset(command_names)

    def test_upgrade_command_registered(self) -> None:
        """The 'upgrade' command is registered on the app group."""
        assert "upgrade" in app.commands

    def test_uninstall_command_registered(self) -> None:
        """The 'uninstall' command is registered on the app group."""
        assert "uninstall" in app.commands

    def test_topics_command_registered(self) -> None:
        """The 'topics' command is registered on the app group (command.name)."""
        assert any(command.name == "topics" for command in app.commands.values())
        assert "topics" in app.commands

    def test_hooks_command_registered(self) -> None:
        """The 'hooks' command is registered on the app group (command.name)."""
        assert any(command.name == "hooks" for command in app.commands.values())
        assert "hooks" in app.commands


class TestHelpOutput:
    def test_help_exit_code_zero(self) -> None:
        """The --help flag on the app group exits with code 0."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0

    def test_help_contains_lint(self) -> None:
        """The --help output lists the 'lint' command."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert "lint" in result.output

    def test_help_contains_build(self) -> None:
        """The --help output lists the 'build' command."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert "build" in result.output

    def test_help_contains_connect(self) -> None:
        """The --help output lists the 'connect' command."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert "connect" in result.output

    def test_help_contains_both_commands(self) -> None:
        """The --help output contains both 'lint' and 'build'."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert "lint" in result.output
        assert "build" in result.output

    def test_help_contains_upgrade(self) -> None:
        """The --help output lists the 'upgrade' command."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert "upgrade" in result.output

    def test_help_contains_uninstall(self) -> None:
        """The --help output lists the 'uninstall' command."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert "uninstall" in result.output

    def test_help_contains_topics(self) -> None:
        """The --help output lists the 'topics' command."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert "topics" in result.output

    def test_help_contains_hooks(self) -> None:
        """The --help output lists the 'hooks' command (design checkpoint)."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert "hooks" in result.output


class TestBuildHelpOutput:
    def test_build_help_exit_code_zero(self) -> None:
        """The 'build --help' subcommand exits with code 0."""
        runner = CliRunner()
        result = runner.invoke(app, ["build", "--help"])
        assert result.exit_code == 0

    def test_build_help_contains_options(self) -> None:
        """The 'build --help' output shows build command options."""
        runner = CliRunner()
        result = runner.invoke(app, ["build", "--help"])
        assert "--dry-run" in result.output

    def test_build_help_contains_plan_argument(self) -> None:
        """The 'build --help' output shows the plan argument."""
        runner = CliRunner()
        result = runner.invoke(app, ["build", "--help"])
        assert "plan" in result.output.lower()


class TestUpgradeHelpOutput:
    def test_upgrade_help_exit_code_zero(self) -> None:
        """The 'upgrade --help' subcommand exits with code 0."""
        runner = CliRunner()
        result = runner.invoke(app, ["upgrade", "--help"])
        assert result.exit_code == 0

    def test_upgrade_help_contains_options(self) -> None:
        """The 'upgrade --help' output shows the --sudo, --user, --tools options."""
        runner = CliRunner()
        result = runner.invoke(app, ["upgrade", "--help"])
        assert "--sudo" in result.output
        assert "--user" in result.output
        assert "--tools" in result.output


class TestVersionFlagContract:
    """Contract tests — the eager --version/-v flag on the root group."""

    def test_version_flag_prints_host_version_and_exits_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The --version flag prints the host version and exits with code 0."""
        monkeypatch.setattr("goga.cli.host_goga_version", lambda: "1.2.3")
        runner = CliRunner()
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert result.output == "1.2.3\n"

    def test_version_option_listed_in_root_help(self) -> None:
        """The --version option appears in the root group help."""
        runner = CliRunner()
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "--version" in result.output

    def test_app_signature_unchanged_by_flag(self) -> None:
        """expose_value=False keeps the app() callback parameterless."""
        assert list(inspect.signature(app.callback).parameters) == []


class TestVersionFlagBehavior:
    """Logic tests — behavior of the eager --version/-v flag."""

    def test_app_version_flag_prints_host_version(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The --version flag echoes the bare host version string."""
        monkeypatch.setattr("goga.cli.host_goga_version", lambda: "1.2.3")
        runner = CliRunner()
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert result.output == "1.2.3\n"

    def test_app_version_short_flag(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The -v short spelling behaves exactly like --version."""
        monkeypatch.setattr("goga.cli.host_goga_version", lambda: "1.2.3")
        runner = CliRunner()
        result = runner.invoke(app, ["-v"])
        assert result.exit_code == 0
        assert result.output == "1.2.3\n"

    def test_app_version_flag_metadata_failure_is_clean(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An undeterminable host version surfaces as a clean error, no traceback."""
        monkeypatch.setattr("goga.cli.host_goga_version", mock.Mock(side_effect=PackageNotFoundError("goga")))
        runner = CliRunner()
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 1
        assert "cannot determine" in result.output
        assert "Traceback" not in result.output

    def test_app_subcommands_unaffected_by_version_flag(self) -> None:
        """The eager group flag never conflicts with subcommands or their options."""
        runner = CliRunner()

        root_help = runner.invoke(app, ["--help"])
        assert root_help.exit_code == 0
        assert "--version" in root_help.output

        build_help = runner.invoke(app, ["build", "--help"])
        assert build_help.exit_code == 0
        assert "--version" not in build_help.output

        install_help = runner.invoke(app, ["install", "--help"])
        assert install_help.exit_code == 0
        # install keeps its own value option of the same name — the group's
        # eager flag does not shadow it.
        assert "--version" in install_help.output

    def test_app_version_flag_before_subcommand_is_eager(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """--version ahead of a subcommand is answered before dispatch."""
        monkeypatch.setattr("goga.cli.host_goga_version", lambda: "1.2.3")
        runner = CliRunner()
        result = runner.invoke(app, ["--version", "build", "plan.md"])
        assert result.exit_code == 0
        assert result.output == "1.2.3\n"

    def test_app_install_version_value_option_not_intercepted(self) -> None:
        """install's own --version VALUE option survives the group's eager flag.

        After the subcommand token the option belongs to install: the value is
        consumed as the option argument (no option conflict, no version print)
        and --help renders install's own surface."""
        runner = CliRunner()
        result = runner.invoke(app, ["install", "--version", "9.9.9", "--help"])
        assert result.exit_code == 0
        assert "9.9.9" not in result.output
        assert "--local" in result.output


class TestSchemaLintCoexist:
    def test_cli_schema_lint_coexist(self) -> None:
        runner = CliRunner()

        with runner.isolated_filesystem() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "CODEMANIFEST").write_text(SIMPLE_MANIFEST, encoding="utf-8")

            with _cwd(tmp_path):
                schema_result = runner.invoke(app, ["schema"])

            assert schema_result.exit_code == 0
            schema_data = json.loads(schema_result.output)
            assert isinstance(schema_data, list)

            with _cwd(tmp_path):
                lint_result = runner.invoke(app, ["lint", "."])

            assert lint_result.exit_code in (0, 1)


def test_cli_registers_history_group() -> None:
    """The history group is registered on app and re-exported by the facade.

    Regression guard for the full registration chain: the group must be added
    to the root ``app`` (help surface), expose all five subcommands, and be
    re-exported through ``goga.commands.__all__`` — otherwise
    ``from goga.commands import history`` breaks on some consumer paths even
    though ``cli.py`` registered it.
    """
    runner = CliRunner()

    root_help = runner.invoke(app, ["--help"])
    assert root_help.exit_code == 0
    assert "history" in root_help.output

    history_help = runner.invoke(app, ["history", "--help"])
    assert history_help.exit_code == 0
    for subcommand in ("list", "status", "path", "ensure", "prune"):
        assert subcommand in history_help.output

    assert "history" in commands.__all__
    assert len(commands.__all__) == 16
    assert hasattr(commands, "history")


def test_cli_registers_hooks_command_and_invokes_it_through_the_root_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The hooks command is wired into the root app end-to-end.

    Registration chain plus one real dispatch: with the package enumeration
    pinned to an empty environment the registry comes up empty, the command
    prints nothing, and exits 0 — the deferred app-level invocation of the
    Task 9 suite (the command was registered on nothing back there).
    """
    monkeypatch.setattr(
        "goga.hooks.tools.packages.packages_distributions",
        lambda: {},
    )
    runner = CliRunner()

    hooks_help = runner.invoke(app, ["hooks", "--help"])
    assert hooks_help.exit_code == 0
    assert "--tool" in hooks_help.output

    result = runner.invoke(app, ["hooks"])
    assert result.exit_code == 0
    assert result.output == ""


def test_hooks_command_renders_a_real_registry_end_to_end(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The real chain — enumeration, identity, registration, view, render.

    A package named with underscores proves the composition end to end: the
    tree shows the canonical hyphen identity ``my-tool``, the slice by that
    form keeps the entry, and the underscore spelling is an unknown name that
    keeps an empty entry — not an error.
    """
    package = ModuleType("goga_tool_my_tool")

    def register_hooks(hooks: Any) -> None:
        hooks.subscribe(
            "statuses",
            "register_statuses",
            "published",
            lambda context: context.register("published", "my/published.md", after="planned"),
        )

    package.register_hooks = register_hooks
    monkeypatch.setitem(sys.modules, "goga_tool_my_tool", package)
    monkeypatch.setattr(
        "goga.hooks.tools.packages.packages_distributions",
        lambda: {"goga_tool_my_tool": ["goga-tool-my-tool"]},
    )
    runner = CliRunner()

    tree = runner.invoke(app, ["hooks"])

    assert tree.exit_code == 0
    assert tree.output == "my-tool\n  statuses\n    register_statuses  published\n"

    sliced = runner.invoke(app, ["hooks", "-t", "my-tool"])
    assert sliced.exit_code == 0
    assert sliced.output == tree.output

    underscored = runner.invoke(app, ["hooks", "-t", "my_tool"])
    assert underscored.exit_code == 0
    assert underscored.output == "my_tool\n"


def test_commands_without_hooks_never_enumerate_packages() -> None:
    """Commands that use no hooks never build the registry.

    ``--version``, ``lint --help``, and ``tool --help`` answer without ever
    reading the installed-distributions mapping: the enumeration boundary of
    the hooks platform stays untouched until a hook-consuming command
    actually assembles the registry. The mock counts, so the assertion
    covers all three invocations at once.
    """
    runner = CliRunner()

    with mock.patch("goga.hooks.tools.packages.packages_distributions") as enumeration:
        for args in (["--version"], ["lint", "--help"], ["tool", "--help"]):
            result = runner.invoke(app, args)

            assert result.exit_code == 0, args

    enumeration.assert_not_called()


def test_facades_export_topics() -> None:
    """Every facade of the feature exports its contract names.

    Design-doc scenario: ``topics`` resolves through ``goga.commands``; the
    domain entries resolve through ``goga.topics``; the history embeddings
    resolve through ``goga.history``; ``app`` registers the ``topics``
    command; the deleted single-status enum stays gone.
    """
    import goga.commands
    import goga.history
    from goga import app as root_app
    from goga.commands import topics as topics_group
    from goga.history import (
        StatusScale,
        assemble_status_scale,
        resolve_history_root,
    )
    from goga.topics import collect_topic_board, create_topic, switch_topic

    assert topics_group is not None
    assert collect_topic_board is not None
    assert switch_topic is not None
    assert create_topic is not None
    assert StatusScale is not None
    assert assemble_status_scale is not None
    assert resolve_history_root is not None

    assert "topics" in goga.commands.__all__
    assert any(command.name == "topics" for command in root_app.commands.values())
    assert "TopicStatus" not in goga.history.__all__
