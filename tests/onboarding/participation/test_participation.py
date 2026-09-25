"""Contract and logic tests for the entity declared in
``goga/onboarding/participation/CODEMANIFEST`` with ``location: participation.py``:

- ``ToolParticipation(invited)`` — the mediator of both onboarding action
  moments, delivered per tool with staged control

The environment boundary is pinned by the shared fixtures of this test
directory (``conftest.py``) — the enumeration mapping and the fake
``goga_tool_*`` modules. The mediator, the registry, and the per-tool
delivery run for real; a failing hook of one tool drops that tool only, and
the single fatal case is a broken package import.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
from goga.onboarding.participation import ToolParticipation
from goga.onboarding.questions import Question, SessionAnswers

_CELL_ALL = ["ToolContribution", "ToolDeclaration", "ToolParticipation"]


def _module(tool: str) -> str:
    """Return the module name of one fake tool identity."""
    return "goga_tool_" + tool.replace("-", "_")


def _mapping(*tools: str) -> dict[str, list[str]]:
    """Build the pinned enumeration mapping carrying the given identities."""
    return {_module(tool): [f"goga-tool-{tool}"] for tool in tools}


def _registering(*envelopes: tuple[str, str, str, Callable[..., None]]) -> Callable[[Any], None]:
    """Build a facade callback subscribing the given envelopes."""

    def register_hooks(hooks: Any) -> None:
        for domain, action, name, hook in envelopes:
            hooks.subscribe(domain, action, name, hook)

    return register_hooks


def _install(
    install_tool_package: Callable[[str, Callable[[Any], None] | None], object],
    tool: str,
    *envelopes: tuple[str, str, str, Callable[..., None]],
) -> None:
    """Install one fake package whose facade subscribes the given envelopes."""
    install_tool_package(_module(tool), register_hooks=_registering(*envelopes))


# --- Contract tests ---


class TestToolParticipationContract:
    def test_entity_is_importable_from_the_package_facade(self) -> None:
        """The mediator lives on the cell package and its ``__all__`` is exact."""
        import goga.onboarding.participation as cell

        assert cell.ToolParticipation is ToolParticipation
        assert cell.__all__ == _CELL_ALL

    def test_construction_dedups_preserving_flag_order(self) -> None:
        """``invited`` is the deduplicated identity list, in flag order."""
        mediator = ToolParticipation(invited=["a", "a", "b"])

        assert mediator.invited == ["a", "b"]

    def test_both_moments_are_callable(self) -> None:
        """The two onboarding action moments are the public surface."""
        mediator = ToolParticipation(invited=[])

        assert callable(mediator.collect_declarations)
        assert callable(mediator.collect_contributions)


# --- Logic tests ---


class TestCollectDeclarations:
    def test_collect_declarations_delivers_invitation_marker(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """An invited subscribed tool receives an active surface and its declaration stands."""

        def declare_token(context: Any) -> None:
            if not context.invited:
                return
            context.declare(Question(id="token", kind="input", prompt="Service token"))

        pin_package_environment(_mapping("my-tool"))
        _install(
            install_tool_package,
            "my-tool",
            ("onboarding", "declare_session", "d1", declare_token),
        )

        declarations = ToolParticipation(invited=["my-tool"]).collect_declarations()

        assert len(declarations) == 1
        assert declarations[0].tool == "my-tool"
        assert declarations[0].invited is True
        assert declarations[0].questions[0].id == "token"

    def test_collect_declarations_warns_for_uninstalled_invited(
        self,
        pin_package_environment,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """An invited identity that is not installed warns; the session continues."""
        pin_package_environment({})

        with caplog.at_level(logging.WARNING):
            declarations = ToolParticipation(invited=["ghost"]).collect_declarations()

        assert declarations == []
        assert any("ghost" in record.message for record in caplog.records)

    def test_failing_hook_drops_whole_declaration(
        self,
        pin_package_environment,
        install_tool_package,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A crashing hook drops its tool only — the warning names the tool and the reason."""

        def declare_ok(context: Any) -> None:
            context.declare(Question(id="token", kind="input", prompt="Token"))

        def declare_boom(context: Any) -> None:
            raise RuntimeError("boom")

        pin_package_environment(_mapping("bad", "good"))
        _install(install_tool_package, "bad", ("onboarding", "declare_session", "d1", declare_boom))
        _install(install_tool_package, "good", ("onboarding", "declare_session", "d1", declare_ok))

        with caplog.at_level(logging.WARNING):
            declarations = ToolParticipation(invited=["bad", "good"]).collect_declarations()

        assert [declaration.tool for declaration in declarations] == ["good"]
        assert any("bad" in record.message and "boom" in record.message for record in caplog.records)

    def test_noninvited_subscribed_tool_is_marked_and_silent(
        self,
        pin_package_environment,
        install_tool_package,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Delivery is never filtered — the not-invited marker travels to the hook."""
        captured: dict[str, bool] = {}

        def declare_session(context: Any, self: Any) -> None:
            self.saw_invited = context.invited
            captured["declare"] = context.invited
            if not context.invited:
                return
            context.declare(Question(id="token", kind="input", prompt="Token"))

        def amend_config(context: Any, self: Any) -> None:
            self.saw_invited = context.invited
            captured["amend"] = context.invited
            if not context.invited:
                return
            context.answer("tools", {"my-tool": "latest"})

        pin_package_environment(_mapping("my-tool", "other"))
        _install(
            install_tool_package,
            "my-tool",
            ("onboarding", "declare_session", "d1", declare_session),
            ("onboarding", "amend_config", "a1", amend_config),
        )
        install_tool_package(_module("other"))  # invited, installed, subscribed to nothing

        mediator = ToolParticipation(invited=["other"])
        answers = SessionAnswers(tools=["my-tool"])

        with caplog.at_level(logging.WARNING):
            declarations = mediator.collect_declarations()
            contributions = mediator.collect_contributions(answers)

        assert declarations == []
        assert [contribution.tool for contribution in contributions] == ["my-tool"]
        assert contributions[0].amendments == []
        assert contributions[0].files == []
        assert captured["declare"] is False
        assert captured["amend"] is False
        assert "my-tool" not in answers.snapshot()
        assert not caplog.records  # silent — not a warning


class TestCollectContributions:
    def test_collect_contributions_commits_in_order(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """The committed amendments apply in enumeration order — the later wins at a leaf."""

        def amend_alpha(context: Any) -> None:
            if not context.invited:
                return
            context.answer("tools", {"alpha": "1.0"})

        def amend_beta(context: Any) -> None:
            if not context.invited:
                return
            context.answer("tools", {"beta": "2.0"})

        pin_package_environment(_mapping("alpha", "beta"))
        _install(install_tool_package, "alpha", ("onboarding", "amend_config", "a1", amend_alpha))
        _install(install_tool_package, "beta", ("onboarding", "amend_config", "a1", amend_beta))

        answers = SessionAnswers()
        contributions = ToolParticipation(invited=["alpha", "beta"]).collect_contributions(answers)

        assert [contribution.tool for contribution in contributions] == ["alpha", "beta"]
        assert answers.snapshot()["tools"] == {"alpha": "1.0", "beta": "2.0"}

    def test_amend_failure_discards_amendments_and_files(
        self,
        pin_package_environment,
        install_tool_package,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """A hook that buffers then raises loses its whole contribution — amendments and files."""

        def amend_boom(context: Any) -> None:
            context.answer("tools", {"boom": "1.0"})
            context.write_config("x.yml", {"a": 1})
            raise RuntimeError("crash")

        pin_package_environment(_mapping("boom"))
        _install(install_tool_package, "boom", ("onboarding", "amend_config", "a1", amend_boom))

        answers = SessionAnswers()

        with caplog.at_level(logging.WARNING):
            contributions = ToolParticipation(invited=["boom"]).collect_contributions(answers)

        assert contributions == []
        assert "tools" not in answers.snapshot()
        assert any("boom" in record.message and "crash" in record.message for record in caplog.records)

    def test_the_isolated_view_carries_no_other_tool(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Each hook sees the core plus its own answers — never a foreign tool's."""
        seen: dict[str, dict] = {}

        def amend_alpha(context: Any) -> None:
            seen["alpha"] = dict(context.answers)

        def amend_beta(context: Any) -> None:
            seen["beta"] = dict(context.answers)

        pin_package_environment(_mapping("alpha", "beta"))
        _install(install_tool_package, "alpha", ("onboarding", "amend_config", "a1", amend_alpha))
        _install(install_tool_package, "beta", ("onboarding", "amend_config", "a1", amend_beta))

        answers = SessionAnswers(tools=["alpha", "beta"])
        answers.record("language", "python")
        answers.record("alpha.token", "t0")
        answers.record("beta.flag", True)

        ToolParticipation(invited=["alpha", "beta"]).collect_contributions(answers)

        assert seen["alpha"] == {"language": "python", "token": "t0"}
        assert seen["beta"] == {"language": "python", "flag": True}


class TestRegistrySharing:
    def test_the_registry_is_built_once_and_shared_by_both_moments(
        self,
        pin_package_environment,
        install_tool_package,
    ) -> None:
        """Both moments read one registry — moment two reads the environment no more.

        Moment one reads the enumeration as often as it needs (the registry
        build plus the uninstalled-invited check); a moment two that rebuilt
        the registry would read it again.
        """

        def declare_session(context: Any) -> None:
            context.declare(Question(id="token", kind="input", prompt="Token"))

        def amend_config(context: Any) -> None:
            if not context.invited:
                return
            context.answer("tools", {"my-tool": "latest"})

        boundary = pin_package_environment(_mapping("my-tool"))
        _install(
            install_tool_package,
            "my-tool",
            ("onboarding", "declare_session", "d1", declare_session),
            ("onboarding", "amend_config", "a1", amend_config),
        )

        mediator = ToolParticipation(invited=["my-tool"])
        answers = SessionAnswers()

        mediator.collect_declarations()
        reads_after_moment_one = boundary.call_count

        mediator.collect_contributions(answers)
        assert boundary.call_count == reads_after_moment_one  # the shared registry — no rebuild

    def test_a_broken_package_import_is_fatal(
        self,
        pin_package_environment,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A facade that fails to import is the single fatal case — ImportError propagates."""
        package_dir = tmp_path / "goga_tool_broken"
        package_dir.mkdir()
        (package_dir / "__init__.py").write_text("import goga_missing_dependency\n")
        monkeypatch.syspath_prepend(tmp_path)
        pin_package_environment({"goga_tool_broken": ["goga-tool-broken"]})

        with pytest.raises(ImportError, match=r"package goga_tool_broken failed to import"):
            ToolParticipation(invited=["broken"]).collect_declarations()
