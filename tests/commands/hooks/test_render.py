"""Contract and logic tests for the entity declared in
``goga/commands/hooks/CODEMANIFEST`` with ``location: render.py`` —
``render_hooks_tree(view: list[ToolHooks])``.

The renderer is pure output: the view prints as given — the tool entries keep
their order, the subscriptions and rejections of an entry are never touched,
and only the domain lines are ordered (alphabetically, per the documented
tree). Output is captured with ``capsys``.
"""

from __future__ import annotations

import inspect
import typing
from collections.abc import Callable

import pytest
from goga.commands.hooks import render_hooks_tree
from goga.hooks import ToolHooks
from goga.hooks.tools import RejectedRegistration, Subscription


def _hook() -> Callable[..., object]:
    """A placeholder callable — the renderer never calls a hook."""
    return lambda: None


def _subscription(
    tool: str = "mkdocs",
    domain: str = "statuses",
    action: str = "register_statuses",
    name: str = "published",
) -> Subscription:
    """One accepted subscription bound to an address."""
    return Subscription(tool=tool, domain=domain, action=action, name=name, hook=_hook())


def _rejection(
    tool: str = "mkdocs",
    domain: str = "statuses",
    action: str = "register_statuses",
    name: str = "dup",
    reason: str = "repeated name on the same address",
) -> RejectedRegistration:
    """One refused registration envelope with its reason."""
    return RejectedRegistration(tool=tool, domain=domain, action=action, name=name, reason=reason)


# --- Contract tests ---


class TestRenderContract:
    def test_render_hooks_tree_is_exported_by_the_cell_facade(self) -> None:
        """``render_hooks_tree`` is importable from the cell package."""
        import goga.commands.hooks as facade

        assert facade.render_hooks_tree is render_hooks_tree

    def test_render_hooks_tree_signature(self) -> None:
        """``render_hooks_tree(view: list[ToolHooks]) -> None``."""
        signature = inspect.signature(render_hooks_tree)
        assert list(signature.parameters) == ["view"]
        assert signature.parameters["view"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
        hints = typing.get_type_hints(render_hooks_tree)
        assert hints == {"view": list[ToolHooks], "return": type(None)}


# --- Logic tests ---


class TestRenderTreeFormat:
    def test_tool_with_subscriptions_only(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A tool line, a domain line per domain, one action line per subscription."""
        view = [
            ToolHooks(
                tool="mkdocs",
                subscriptions=[
                    _subscription(name="published"),
                    _subscription(name="sync"),
                ],
                rejections=[],
            )
        ]

        render_hooks_tree(view)

        assert capsys.readouterr().out == (
            "mkdocs\n  statuses\n    register_statuses  published\n    register_statuses  sync\n"
        )

    def test_domain_lines_are_alphabetical_per_tool(self, capsys: pytest.CaptureFixture[str]) -> None:
        """The distinct domains of one tool print sorted, whatever the entry order."""
        view = [
            ToolHooks(
                tool="t",
                subscriptions=[
                    _subscription(domain="zeta", action="a", name="n1"),
                    _subscription(domain="alpha", action="a", name="n2"),
                    _subscription(domain="zeta", action="b", name="n3"),
                ],
                rejections=[],
            )
        ]

        render_hooks_tree(view)

        assert capsys.readouterr().out == ("t\n  alpha\n    a  n2\n  zeta\n    a  n1\n    b  n3\n")

    def test_tool_with_a_rejection_only(self, capsys: pytest.CaptureFixture[str]) -> None:
        """A refusal prints under its tool with the name in double quotes."""
        view = [ToolHooks(tool="scriba", subscriptions=[], rejections=[_rejection(tool="scriba")])]

        render_hooks_tree(view)

        assert capsys.readouterr().out == (
            'scriba\n  rejected statuses/register_statuses "dup": repeated name on the same address\n'
        )

    def test_tool_without_subscriptions_and_refusals_prints_its_line_alone(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """A sliced empty entry stays in the tree — one bare tool line."""
        view = [ToolHooks(tool="ghost", subscriptions=[], rejections=[])]

        render_hooks_tree(view)

        assert capsys.readouterr().out == "ghost\n"

    def test_empty_view_prints_nothing(self, capsys: pytest.CaptureFixture[str]) -> None:
        """An empty registry renders not a single line."""
        render_hooks_tree([])
        assert capsys.readouterr().out == ""

    def test_rejections_print_after_the_domains_of_their_tool(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Subscriptions print first, the refusals of the tool after them."""
        view = [
            ToolHooks(
                tool="t",
                subscriptions=[_subscription()],
                rejections=[_rejection()],
            )
        ]

        render_hooks_tree(view)

        assert capsys.readouterr().out == (
            "t\n"
            "  statuses\n"
            "    register_statuses  published\n"
            '  rejected statuses/register_statuses "dup": repeated name on the same address\n'
        )


class TestRenderReadOnly:
    def test_render_hooks_tree_does_not_mutate_or_resort_view(self, capsys: pytest.CaptureFixture[str]) -> None:
        """The tool order and the entry contents survive the call unchanged."""
        first = ToolHooks(tool="z", subscriptions=[_subscription(tool="z", name="n1")], rejections=[])
        second = ToolHooks(tool="a", subscriptions=[], rejections=[_rejection(tool="a", name="x")])
        view = [first, second]
        snapshot = [
            (entry.tool, [s.name for s in entry.subscriptions], [r.name for r in entry.rejections]) for entry in view
        ]

        render_hooks_tree(view)
        capsys.readouterr()

        assert [entry.tool for entry in view] == ["z", "a"]
        assert [
            (entry.tool, [s.name for s in entry.subscriptions], [r.name for r in entry.rejections]) for entry in view
        ] == snapshot
        assert view[0] is first
        assert view[1] is second

    def test_render_hooks_tree_prints_tools_in_the_given_order(self, capsys: pytest.CaptureFixture[str]) -> None:
        """The renderer never re-sorts the tool entries — the caller's order holds."""
        view = [
            ToolHooks(tool="zeta", subscriptions=[_subscription(tool="zeta")], rejections=[]),
            ToolHooks(tool="alpha", subscriptions=[_subscription(tool="alpha")], rejections=[]),
        ]

        render_hooks_tree(view)

        assert capsys.readouterr().out == (
            "zeta\n  statuses\n    register_statuses  published\nalpha\n  statuses\n    register_statuses  published\n"
        )
