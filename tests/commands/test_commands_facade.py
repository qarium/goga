from __future__ import annotations

import click
from goga import commands
from goga.commands import flow as flow_reexport
from goga.commands.flow import flow as flow_source


class TestCommandsFacade:
    def test_flow_reexported_from_facade(self) -> None:
        """flow is importable from the goga.commands facade."""
        assert flow_reexport is flow_source

    def test_flow_listed_in_all(self) -> None:
        """flow is a declared member of the goga.commands facade."""
        assert "flow" in commands.__all__

    def test_flow_is_a_click_group_via_facade(self) -> None:
        """The re-exported flow is a click.Group instance."""
        assert isinstance(flow_reexport, click.Group)

    def test_flow_exposes_ls_and_run_via_facade(self) -> None:
        """The re-exported flow group carries the ls and run subcommands."""
        assert "ls" in flow_reexport.commands
        assert "run" in flow_reexport.commands
