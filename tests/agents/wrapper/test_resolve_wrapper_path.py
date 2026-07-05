from __future__ import annotations

import pytest
from goga.agents.wrapper.resolve import resolve_wrapper_path


class TestResolveWrapperPathContract:
    def test_resolve_wrapper_path_returns_absolute_path(self) -> None:
        """resolve_wrapper_path returns an absolute path under the wrappers dir."""
        result = resolve_wrapper_path("codex")

        assert result == "/home/goga/bin/codex-as-claude.sh"
        assert result.startswith("/home/goga/bin/")
        assert result.endswith("-as-claude.sh")

    def test_resolve_wrapper_path_no_whitelist(self) -> None:
        """No whitelist: arbitrary agent names are forwarded as-is."""
        result = resolve_wrapper_path("mythical-agent")

        assert result == "/home/goga/bin/mythical-agent-as-claude.sh"

    def test_resolve_wrapper_path_no_normalization(self) -> None:
        """No case-folding or stripping: the agent value is forwarded verbatim."""
        result = resolve_wrapper_path("CodEx")

        assert result == "/home/goga/bin/CodEx-as-claude.sh"

    def test_resolve_wrapper_path_empty_string(self) -> None:
        """An empty agent name is forwarded as-is, never rejected."""
        result = resolve_wrapper_path("")

        assert result == "/home/goga/bin/-as-claude.sh"


class TestResolveWrapperPathLogic:
    @pytest.mark.parametrize(
        ("agent", "expected"),
        [
            ("claude", "/home/goga/bin/claude-as-claude.sh"),
            ("codex", "/home/goga/bin/codex-as-claude.sh"),
            ("opencode", "/home/goga/bin/opencode-as-claude.sh"),
        ],
    )
    def test_resolve_wrapper_path_known_agents(self, agent: str, expected: str) -> None:
        """Known agents resolve to the canonical wrapper path."""
        assert resolve_wrapper_path(agent) == expected

    def test_resolve_wrapper_path_is_pure_string_building(self) -> None:
        """The result is a deterministic function of the agent argument only."""
        first = resolve_wrapper_path("codex")
        second = resolve_wrapper_path("codex")

        assert first == second == "/home/goga/bin/codex-as-claude.sh"
