"""Logic tests for the ``resolve_activation`` routine.

Covers behavior beyond the contract surface: the whitespace-unset rule, the
strongest-first precedence order, and the trimmed effective name.
"""

from __future__ import annotations

from goga.pipeline.workflow import resolve_activation


class TestResolveActivationLogic:
    """Logic tests — channel folding of the ``resolve_activation`` routine."""

    def test_resolve_activation_whitespace_and_precedence(self) -> None:
        """Whitespace-only channels are unset; the strongest set channel wins.

        Edge: (" ", "env", "default") -> "env"; (None, "", "  ") -> None;
        ("cli", "env", "default") -> "cli".
        """
        assert resolve_activation(" ", "env", "default") == "env"
        assert resolve_activation(None, "", "  ") is None
        assert resolve_activation("cli", "env", "default") == "cli"

    def test_resolve_activation_env_beats_default(self) -> None:
        """The environment channel beats the workflow default."""
        assert resolve_activation(None, "env", "default") == "env"

    def test_resolve_activation_default_used_when_channels_unset(self) -> None:
        """The workflow default activates when both channels are unset."""
        assert resolve_activation(None, None, "default") == "default"

    def test_resolve_activation_empty_strings_count_as_unset(self) -> None:
        """Empty strings fall through to the next channel or to None."""
        assert resolve_activation("", "env", "") == "env"
        assert resolve_activation("", "", "") is None

    def test_resolve_activation_padded_value_returned_trimmed(self) -> None:
        """A whitespace-padded value is set and resolves to its trimmed form.

        The grammar forbids whitespace inside a profile name, so the padding
        is insignificant around the value — the effective name is trimmed.
        """
        assert resolve_activation("  mixa  ", None, None) == "mixa"

    def test_resolve_activation_all_none_returns_none(self) -> None:
        """Every channel absent resolves to no activation."""
        assert resolve_activation(None, None, None) is None

    def test_resolve_activation_module_reads_no_environment(self) -> None:
        """The module is pure — its source never touches ``os.environ`` or ``getenv``."""
        import inspect
        from pathlib import Path

        source = Path(inspect.getsourcefile(resolve_activation)).read_text()  # type: ignore[arg-type]

        assert "os.environ" not in source
        assert "getenv" not in source
