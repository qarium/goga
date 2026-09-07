from __future__ import annotations

import click
from goga import app, commands
from goga.commands import hooks as hooks_reexport
from goga.commands import install as install_reexport
from goga.commands import pipeline as pipeline_reexport
from goga.commands import topics as topics_reexport
from goga.commands import uninstall as uninstall_reexport
from goga.commands.hooks import hooks as hooks_source
from goga.commands.install import install as install_source
from goga.commands.install import uninstall as uninstall_source
from goga.commands.pipeline import pipeline as pipeline_source
from goga.commands.topics import topics as topics_source


class TestCommandsFacade:
    def test_pipeline_reexported_from_facade(self) -> None:
        """pipeline is importable from the goga.commands facade."""
        assert pipeline_reexport is pipeline_source

    def test_pipeline_listed_in_all(self) -> None:
        """pipeline is a declared member of the goga.commands facade."""
        assert "pipeline" in commands.__all__

    def test_pipeline_is_a_click_command_via_facade(self) -> None:
        """The re-exported pipeline is a click.Command (NOT a group)."""
        assert isinstance(pipeline_reexport, click.Command)
        assert not isinstance(pipeline_reexport, click.Group)

    def test_pipeline_does_not_expose_subcommands(self) -> None:
        """The re-exported pipeline command has no ls/run subcommands."""
        assert not isinstance(pipeline_reexport, click.Group)


class TestInstallFacade:
    def test_install_listed_in_all(self) -> None:
        """install is a declared member of the goga.commands facade."""
        assert "install" in commands.__all__

    def test_install_is_a_click_command_via_facade(self) -> None:
        """The re-exported install is a click.Command."""
        assert isinstance(commands.install, click.Command)
        assert install_reexport is install_source


class TestUninstallFacade:
    def test_uninstall_reexported_from_facade(self) -> None:
        """The facade re-exports the same uninstall object, not a copy."""
        assert uninstall_reexport is uninstall_source

    def test_uninstall_listed_in_all(self) -> None:
        """uninstall is a declared member of the goga.commands facade."""
        assert "uninstall" in commands.__all__

    def test_uninstall_is_a_click_command_via_facade(self) -> None:
        """The re-exported uninstall is a click.Command."""
        assert isinstance(commands.uninstall, click.Command)


class TestTopicsFacade:
    def test_topics_reexported_from_facade(self) -> None:
        """topics is importable from the goga.commands facade."""
        assert topics_reexport is topics_source

    def test_topics_listed_in_all(self) -> None:
        """topics is a declared member of the goga.commands facade."""
        assert "topics" in commands.__all__

    def test_topics_is_a_click_group_via_facade(self) -> None:
        """The re-exported topics is a click Group (a command group)."""
        assert isinstance(topics_reexport, click.Group)


class TestHooksFacade:
    def test_commands_facade_reexports_hooks_and_root_group_registers_it(self) -> None:
        """hooks is re-exported by the facade and registered on the root app group.

        The full registration chain of the hooks inspection command: the facade
        re-export carries the source object, ``__all__`` declares it, the
        re-export is a plain ``click.Command`` (not a group), and the root
        ``app`` carries it under its command name.
        """
        assert hooks_reexport is hooks_source
        assert "hooks" in commands.__all__
        assert isinstance(hooks_reexport, click.Command)
        assert any(cmd.name == "hooks" for cmd in app.commands.values())
