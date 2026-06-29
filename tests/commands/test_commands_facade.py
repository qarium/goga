from __future__ import annotations

import click
from goga import commands
from goga.commands import pipeline as pipeline_reexport
from goga.commands.pipeline import pipeline as pipeline_source


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
