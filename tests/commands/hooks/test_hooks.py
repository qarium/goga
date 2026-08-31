"""Contract and logic tests for the entity declared in
``goga/commands/hooks/CODEMANIFEST`` with ``location: hooks.py`` —
``hooks(tools: tuple[str, ...])``.

The command is a thin inspection wrapper: it creates the run registry,
assembles it once, applies the ``--tool`` slice, and hands the view to the
renderer. The registry is faked at its import point in the command module, so
the tests drive the CLI surface alone; the command is invoked directly — the
root-group registration belongs to the task that follows this cell.
"""

from __future__ import annotations

import inspect
import sys
import typing
from typing import Any

import click
import pytest
from click.testing import CliRunner
from goga.commands.hooks import hooks
from goga.hooks import ToolHooks
from goga.hooks.tools import RejectedRegistration, Subscription

# The goga.commands facade re-exports the click command under the same name as
# the cell package (``from .hooks import hooks``), so attribute access through
# goga.commands gives the command for both the package and its module. Resolve
# the real objects via sys.modules (precedent: test_history_command.py).
facade = sys.modules["goga.commands.hooks"]
_hooks_module = sys.modules["goga.commands.hooks.hooks"]

_CELL_ALL = ["hooks", "render_hooks_tree"]


class _FakeRegistry:
    """Stand-in for ``HookRegistry`` answering a fixed per-tool view."""

    def __init__(self, view: list[ToolHooks]) -> None:
        self._view = view
        self.build_calls = 0

    def build_once(self) -> None:
        self.build_calls += 1

    def by_tool(self) -> list[ToolHooks]:
        return self._view


class _BrokenRegistry:
    """Stand-in for ``HookRegistry`` whose single build fails fatally."""

    def build_once(self) -> None:
        raise ImportError("package goga_tool_bad failed to import: boom")

    def by_tool(self) -> list[ToolHooks]:
        raise AssertionError("a broken build never reaches the view")


def _install_fake_registry(monkeypatch: pytest.MonkeyPatch, fake: Any) -> Any:
    """Pin the registry factory the command reads; return the fake for asserts."""
    monkeypatch.setattr(_hooks_module, "HookRegistry", lambda: fake)
    return fake


def _subscription(tool: str = "mkdocs", name: str = "published") -> Subscription:
    """One statuses-action subscription — the shape the seed catalog carries."""
    return Subscription(
        tool=tool,
        domain="statuses",
        action="register_statuses",
        name=name,
        hook=lambda: None,
    )


def _dup_rejection(tool: str = "mkdocs") -> RejectedRegistration:
    """One refused envelope with the documented repeated-name reason."""
    return RejectedRegistration(
        tool=tool,
        domain="statuses",
        action="register_statuses",
        name="dup",
        reason="repeated name on the same address",
    )


# --- Contract tests ---


class TestHooksCommandContract:
    def test_hooks_is_exported_by_the_cell_facade(self) -> None:
        """``hooks`` is importable from the package and listed in its ``__all__``."""
        assert facade.hooks is hooks
        assert list(facade.__all__) == _CELL_ALL

    def test_hooks_is_a_click_command_not_a_group(self) -> None:
        """The entity is a terminal ``click.Command`` — no subcommands."""
        assert isinstance(hooks, click.Command)
        assert not isinstance(hooks, click.Group)

    def test_hooks_carries_one_repeatable_tools_option(self) -> None:
        """``--tool``/``-t`` is the single option, repeatable, never ``None``."""
        options = [param for param in hooks.params if isinstance(param, click.Option)]
        assert len(options) == 1
        option = options[0]
        assert option.name == "tools"
        assert option.multiple is True
        assert "--tool" in option.opts
        assert "-t" in option.opts
        assert option.secondary_opts == []

    def test_hooks_callback_declares_the_empty_tuple_default(self) -> None:
        """No ``-t`` passes the empty tuple — never ``None`` (the click practice)."""
        signature = inspect.signature(inspect.unwrap(hooks.callback))
        parameter = signature.parameters["tools"]
        assert parameter.default == ()
        assert parameter.annotation in (tuple[str, ...], "tuple[str, ...]")

    def test_hooks_callback_is_annotated_none(self) -> None:
        """The callback returns nothing — the exit code is click's, not a return value."""
        hints = typing.get_type_hints(inspect.unwrap(hooks.callback))
        assert hints["tools"] == tuple[str, ...]
        assert hints["return"] is type(None)

    def test_hooks_help_text_carries_no_api_sections(self) -> None:
        """``--help`` is user-facing help: no Args/Returns/Raises blocks."""
        result = CliRunner().invoke(hooks, ["--help"])

        assert result.exit_code == 0
        assert "Usage:" in result.output
        assert "--tool" in result.output
        for forbidden in ("Args:", "Returns:", "Raises:"):
            assert forbidden not in result.output

    def test_hooks_help_summary_is_one_concise_line(self) -> None:
        """The first docstring line is the command-listing summary."""
        summary = (hooks.help or "").splitlines()[0]

        assert summary.endswith(".")
        assert len(summary) < 80


# --- Logic tests ---


class TestHooksCommandTree:
    def test_hooks_command_renders_the_tree(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """One tool line, domain lines, action lines, then the refusal with its reason."""
        view = [
            ToolHooks(
                tool="mkdocs",
                subscriptions=[_subscription()],
                rejections=[_dup_rejection()],
            )
        ]
        _install_fake_registry(monkeypatch, _FakeRegistry(view))

        result = CliRunner().invoke(hooks, [])

        assert result.exit_code == 0
        expected = (
            "mkdocs\n"
            "  statuses\n"
            "    register_statuses  published\n"
            '  rejected statuses/register_statuses "dup": repeated name on the same address\n'
        )
        assert result.output == expected

    def test_hooks_assembles_the_registry_once(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """The single build of the run — one ``build_once`` call, never two."""
        fake = _FakeRegistry([ToolHooks(tool="mkdocs", subscriptions=[_subscription()], rejections=[])])
        _install_fake_registry(monkeypatch, fake)

        result = CliRunner().invoke(hooks, [])

        assert result.exit_code == 0
        assert fake.build_calls == 1

    def test_hooks_slice_keeps_empty_entry_for_unknown_tool(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A requested name without registrations keeps its tool line alone."""
        view = [ToolHooks(tool="mkdocs", subscriptions=[_subscription()], rejections=[])]
        _install_fake_registry(monkeypatch, _FakeRegistry(view))

        result = CliRunner().invoke(hooks, ["-t", "mkdocs", "-t", "ghost"])

        assert result.exit_code == 0
        assert result.output.startswith("mkdocs\n")
        assert result.output.endswith("ghost\n")
        assert "register_statuses" in result.output

    def test_hooks_slice_deduplicates_a_repeated_request(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Asking for one tool twice yields one tool line, not two."""
        view = [ToolHooks(tool="a", subscriptions=[_subscription(tool="a")], rejections=[])]
        _install_fake_registry(monkeypatch, _FakeRegistry(view))

        result = CliRunner().invoke(hooks, ["-t", "a", "-t", "a"])

        assert result.exit_code == 0
        assert result.output.splitlines().count("a") == 1

    def test_hooks_slice_keeps_the_view_order_before_the_missing_names(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Known tools print in view order; unknown names follow in request order."""
        view = [
            ToolHooks(tool="b", subscriptions=[_subscription(tool="b")], rejections=[]),
            ToolHooks(tool="a", subscriptions=[_subscription(tool="a")], rejections=[]),
        ]
        _install_fake_registry(monkeypatch, _FakeRegistry(view))

        result = CliRunner().invoke(hooks, ["-t", "zulu", "-t", "a", "-t", "b"])

        assert result.exit_code == 0
        assert result.output.splitlines()[0] == "b"
        assert result.output.splitlines()[-1] == "zulu"


class TestHooksCommandErrors:
    def test_hooks_command_broken_import_is_clean_cli_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """A broken package import fails with stderr, exit 1, and no traceback."""
        _install_fake_registry(monkeypatch, _BrokenRegistry())

        result = CliRunner().invoke(hooks, [])

        assert result.exit_code == 1
        assert "goga_tool_bad" in result.stderr
        assert "Traceback" not in result.output
        assert "Traceback" not in result.stderr


class TestHooksCommandEdges:
    def test_hooks_empty_registry_prints_nothing_and_exits_zero(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An empty view renders not a single line and is not an error."""
        _install_fake_registry(monkeypatch, _FakeRegistry([]))

        result = CliRunner().invoke(hooks, [])

        assert result.exit_code == 0
        assert result.output == ""

    def test_hooks_never_emits_an_action(self) -> None:
        """Inspection reads the registry only — the module carries no emission."""
        assert not hasattr(_hooks_module, "emit_hook_event")
